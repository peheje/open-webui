import asyncio
from types import SimpleNamespace

from open_webui.utils import middleware as middleware_utils
from open_webui.routers import images as image_router
from open_webui.utils.openrouter import (
    apply_openrouter_request,
    finalize_openrouter_request,
    is_openrouter_model,
    model_supports_web_search,
    resolve_openrouter_image_parameters,
    resolve_openrouter_search_parameters,
    should_use_openrouter_search,
)
from open_webui.utils.payload import apply_model_params_to_body_openai
from open_webui.utils.reasoning_levels import merge_reasoning_params
from open_webui.utils.response import merge_usage


OPENROUTER_MODEL = {
    "id": "or.grok45",
    "info": {
        "meta": {
            "openrouter": {
                "official_provider": "xai",
                "web_search": True,
                "cache_mode": "smart",
            }
        }
    },
}

ANTHROPIC_MODEL = {
    "id": "or.sonnet5",
    "info": {
        "meta": {
            "openrouter": {
                "official_provider": "anthropic",
                "web_search": True,
                "cache_mode": "smart",
            }
        }
    },
}


def test_only_curated_openrouter_models_activate_gateway_features():
    assert is_openrouter_model(OPENROUTER_MODEL)
    assert not is_openrouter_model({"id": "di.sonnet5"})
    assert should_use_openrouter_search({"web_search": True}, OPENROUTER_MODEL)
    assert not should_use_openrouter_search({"web_search": False}, OPENROUTER_MODEL)


def test_explicit_model_capability_disables_stale_search_requests():
    model = {
        "id": "or.gemini3.6f",
        "info": {
            "meta": {
                "capabilities": {"web_search": False},
                "openrouter": {
                    "official_provider": "google-ai-studio",
                    "web_search": True,
                },
            }
        },
    }
    form_data = {"tools": []}

    assert not model_supports_web_search(model)
    assert not should_use_openrouter_search({"web_search": True}, model)
    assert not apply_openrouter_request(
        form_data,
        {"web_search": True, "web_search_config": {"engine": "native"}},
        model,
        "chat-123",
    )
    assert form_data["tools"] == []
    assert form_data["session_id"].startswith("owui-")


def test_image_model_is_allowlisted_with_balanced_fallback():
    assert resolve_openrouter_image_parameters(
        {"model": "openai/gpt-image-2"}
    ) == {"model": "openai/gpt-image-2"}
    assert resolve_openrouter_image_parameters(
        {"model": "unknown/vendor-model"}
    ) == {"model": "google/gemini-3.1-flash-image"}


def test_openrouter_webp_image_is_persisted_before_display(monkeypatch):
    stored = []

    async def fake_store(request, image_url, metadata, user):
        stored.append(image_url)
        return "/api/v1/files/test/content"

    monkeypatch.setattr(
        middleware_utils,
        "get_image_url_from_base64",
        fake_store,
    )
    result = asyncio.run(
        middleware_utils.get_image_urls(
            [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/webp;base64,UklGRg=="},
                }
            ],
            request=None,
            metadata={"chat_id": "chat-image"},
            user=None,
        )
    )

    assert stored == ["data:image/webp;base64,UklGRg=="]
    assert result == ["/api/v1/files/test/content"]


def test_direct_openrouter_image_route_persists_the_provider_result(monkeypatch):
    one_pixel_png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    posted = {}

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def json(self, content_type=None):
            return {
                "data": [{"b64_json": one_pixel_png}],
                "usage": {"cost": 0.001},
            }

    class FakeSession:
        def post(self, **kwargs):
            posted.update(kwargs)
            return FakeResponse()

    async def fake_config_get(key):
        return {}

    async def fake_connection():
        return "test-key", {}

    async def fake_session():
        return FakeSession()

    async def fake_upload(request, image_data, content_type, metadata, user, db=None):
        assert image_data.startswith(b"\x89PNG")
        assert content_type == "image/png"
        assert metadata == {
            "provider": "openrouter",
            "model": "google/gemini-3.1-flash-image",
        }
        return SimpleNamespace(id="file-1", filename="generated-image.png"), "/api/v1/files/file-1/content"

    async def fake_publish(*args, **kwargs):
        return None

    monkeypatch.setattr(image_router.Config, "get", fake_config_get)
    monkeypatch.setattr(image_router, "get_openrouter_image_connection", fake_connection)
    monkeypatch.setattr(image_router, "get_session", fake_session)
    monkeypatch.setattr(image_router, "upload_image", fake_upload)
    monkeypatch.setattr(image_router, "publish_event", fake_publish)

    result = asyncio.run(
        image_router.generate_openrouter_images(
            request=SimpleNamespace(),
            form_data=image_router.OpenRouterCreateImageForm(
                model="google/gemini-3.1-flash-image",
                prompt="A blue circle",
            ),
            user=SimpleNamespace(id="user-1", role="admin"),
        )
    )

    assert posted["url"] == "https://openrouter.ai/api/v1/images"
    assert posted["json"] == {
        "model": "google/gemini-3.1-flash-image",
        "prompt": "A blue circle",
        "n": 1,
    }
    assert result == {
        "model": "google/gemini-3.1-flash-image",
        "images": [
            {
                "id": "file-1",
                "type": "image",
                "url": "/api/v1/files/file-1/content",
                "name": "generated-image.png",
                "content_type": "image/png",
            }
        ],
        "usage": {"cost": 0.001},
    }


def test_search_options_are_validated_and_bounded():
    assert resolve_openrouter_search_parameters(
        {
            "engine": "perplexity",
            "max_results": 99,
            "max_total_results": "12",
            "max_uses": 3,
            "max_characters": 200_000,
            "search_context_size": "medium",
            "allowed_domains": [" Example.com ", "example.com", "openrouter.ai"],
            "excluded_domains": ["reddit.com"],
        }
    ) == {
        "engine": "perplexity",
        "max_results": 20,
        "max_total_results": 12,
        "max_uses": 3,
        "max_characters": 100_000,
        "search_context_size": "medium",
        "allowed_domains": ["example.com", "openrouter.ai"],
    }


def test_exa_allows_both_domain_lists():
    assert resolve_openrouter_search_parameters(
        {
            "engine": "exa",
            "allowed_domains": ["nature.com"],
            "excluded_domains": ["example.com"],
        }
    ) == {
        "engine": "exa",
        "allowed_domains": ["nature.com"],
        "excluded_domains": ["example.com"],
    }


def test_openrouter_request_adds_agentic_search_and_sticky_session():
    form_data = {
        "tools": [{"type": "function", "function": {"name": "calculator"}}],
        "max_tool_calls": 8,
        "provider": {
            "only": ["xai"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
        "params": {
            "custom_params": {
                "provider": {
                    "only": ["xai"],
                    "allow_fallbacks": False,
                    "require_parameters": True,
                }
            }
        },
    }
    injected = apply_openrouter_request(
        form_data,
        {
            "web_search": True,
            "web_search_config": {
                "engine": "parallel",
                "max_results": 5,
                "max_total_results": 12,
                "max_uses": 3,
            },
        },
        OPENROUTER_MODEL,
        "chat-123",
    )

    assert injected is True
    assert form_data["session_id"].startswith("owui-")
    assert form_data["session_id"] != "chat-123"
    assert form_data["max_tool_calls"] == 3
    assert form_data["provider"] == {
        "only": ["xai"],
        "allow_fallbacks": False,
    }
    assert form_data["params"]["custom_params"]["provider"] == {
        "only": ["xai"],
        "allow_fallbacks": False,
    }
    assert form_data["tools"] == [
        {"type": "function", "function": {"name": "calculator"}},
        {
            "type": "openrouter:web_search",
            "parameters": {
                "engine": "parallel",
                "max_results": 5,
                "max_total_results": 12,
            },
        },
    ]


def test_hidden_model_managed_search_uses_curated_external_engine():
    model = {
        "id": "or.gemini3.6f",
        "info": {
            "meta": {
                "capabilities": {"web_search": False},
                "openrouter": {
                    "official_provider": "google-ai-studio",
                    "web_search": True,
                    "always_web_search": True,
                    "search_defaults": {
                        "engine": "exa",
                        "max_results": 3,
                        "max_total_results": 6,
                        "max_characters": 2000,
                        "max_uses": 2,
                    },
                },
            }
        },
    }
    form_data = {
        "tools": [],
        "provider": {
            "only": ["google-ai-studio"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    }

    assert should_use_openrouter_search({"web_search": False}, model)
    assert apply_openrouter_request(
        form_data,
        {
            "web_search": True,
            "web_search_config": {"engine": "native", "max_uses": 9},
        },
        model,
        "chat-123",
    )
    assert form_data["tools"] == [
        {
            "type": "openrouter:web_search",
            "parameters": {
                "engine": "exa",
                "max_results": 3,
                "max_total_results": 6,
                "max_characters": 2000,
            },
        }
    ]
    assert form_data["max_tool_calls"] == 2
    assert form_data["provider"] == {
        "only": ["google-ai-studio"],
        "allow_fallbacks": False,
    }


def test_openrouter_search_tool_is_replaced_not_duplicated():
    form_data = {
        "tools": [{"type": "openrouter:web_search"}],
        "provider": {
            "only": ["xai"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
        "params": {
            "custom_params": {
                "provider": {
                    "only": ["xai"],
                    "allow_fallbacks": False,
                    "require_parameters": True,
                }
            }
        },
    }
    apply_openrouter_request(
        form_data,
        {"web_search": True, "web_search_config": {"engine": "native"}},
        OPENROUTER_MODEL,
        "chat-123",
    )
    assert form_data["tools"] == [
        {
            "type": "openrouter:web_search",
            "parameters": {"engine": "native"},
        }
    ]
    assert form_data["provider"]["require_parameters"] is True
    assert (
        form_data["params"]["custom_params"]["provider"]["require_parameters"]
        is True
    )


def test_provider_boundary_relaxes_external_search_after_model_params_reapply():
    payload = {
        "tools": [
            {
                "type": "openrouter:web_search",
                "parameters": {"engine": "exa", "max_uses": 1},
            }
        ],
        "provider": {
            "only": ["openai"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    }

    finalize_openrouter_request(payload)

    assert payload["provider"] == {
        "only": ["openai"],
        "allow_fallbacks": False,
    }


def test_anthropic_smart_and_long_caching_are_explicit():
    smart = {}
    apply_openrouter_request(smart, {}, ANTHROPIC_MODEL, "chat-123")
    assert smart["cache_control"] == {"type": "ephemeral"}

    long_session = {}
    apply_openrouter_request(
        long_session,
        {"openrouter_cache_config": {"mode": "long"}},
        ANTHROPIC_MODEL,
        "chat-123",
    )
    assert long_session["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    provider_default = {"cache_control": {"type": "ephemeral"}}
    apply_openrouter_request(
        provider_default,
        {"openrouter_cache_config": {"mode": "provider_default"}},
        ANTHROPIC_MODEL,
        "chat-123",
    )
    assert "cache_control" not in provider_default


def test_non_openrouter_request_is_unchanged():
    form_data = {"model": "di.sonnet5", "tools": []}
    original = form_data.copy()
    assert not apply_openrouter_request(
        form_data,
        {"web_search": True},
        {"id": "di.sonnet5"},
        "chat-123",
    )
    assert form_data == original


def test_curated_routing_and_reasoning_reach_the_provider_payload_together():
    model_params = {
        "custom_params": {
            "provider": {
                "only": ["xai"],
                "allow_fallbacks": False,
                "require_parameters": True,
            }
        }
    }
    model_meta = {
        "reasoning_control": {
            "default_level": "r1",
            "levels": {
                "r0": {
                    "params": {
                        "custom_params": {
                            "reasoning": {"effort": "low", "exclude": False}
                        }
                    }
                },
                "r1": {
                    "params": {
                        "custom_params": {
                            "reasoning": {"effort": "medium", "exclude": False}
                        }
                    }
                },
                "r2": {
                    "params": {
                        "custom_params": {
                            "reasoning": {"effort": "high", "exclude": False}
                        }
                    }
                },
            },
        }
    }

    params, resolved = merge_reasoning_params(
        model_params,
        {"reasoning_level": "r2"},
        model_meta,
    )
    payload = apply_model_params_to_body_openai(
        params,
        {"model": "x-ai/grok-4.5", "messages": []},
    )

    assert resolved == "r2"
    assert payload["provider"] == {
        "only": ["xai"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert payload["reasoning"] == {"effort": "high", "exclude": False}
    assert "reasoning_level" not in payload


def test_openrouter_search_and_prompt_cache_usage_is_accumulated():
    usage = merge_usage(
        {
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_creation_input_tokens": 80,
            "server_tool_use": {"web_search_requests": 1},
        },
        {
            "input_tokens": 50,
            "output_tokens": 10,
            "cache_read_input_tokens": 40,
            "server_tool_use": {"web_search_requests": 2},
        },
    )

    assert usage["input_tokens"] == 150
    assert usage["output_tokens"] == 30
    assert usage["cache_creation_input_tokens"] == 80
    assert usage["cache_read_input_tokens"] == 40
    assert usage["server_tool_use"] == {"web_search_requests": 3}


def test_openrouter_server_tool_usage_details_are_normalized_and_accumulated():
    usage = merge_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "server_tool_use_details": {
                "web_search_requests": 1,
                "tool_calls_executed": 1,
            },
        },
        {
            "prompt_tokens": 50,
            "completion_tokens": 5,
            "server_tool_use_details": {
                "web_search_requests": 2,
                "tool_calls_executed": 2,
            },
        },
    )

    assert usage["server_tool_use"] == {
        "web_search_requests": 3,
        "tool_calls_executed": 3,
    }
    assert usage["server_tool_use_details"] == {
        "web_search_requests": 3,
        "tool_calls_executed": 3,
    }
