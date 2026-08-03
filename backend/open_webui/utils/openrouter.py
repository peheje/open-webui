"""OpenRouter-specific request shaping for curated Open WebUI models.

OpenRouter deliberately exposes gateway features that are not part of the
generic OpenAI-compatible schema.  Keep those translations at the final chat
request boundary so the UI stores provider-neutral choices and other
connections never receive OpenRouter-only fields.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any


OPENROUTER_SEARCH_ENGINES = {
    "auto",
    "native",
    "exa",
    "firecrawl",
    "parallel",
    "perplexity",
}
OPENROUTER_SEARCH_CONTEXT_SIZES = {"low", "medium", "high"}
OPENROUTER_CACHE_MODES = {"smart", "long", "provider_default"}
OPENROUTER_IMAGE_MODELS = {
    "google/gemini-3.1-flash-lite-image",
    "google/gemini-3.1-flash-image",
    "google/gemini-3-pro-image",
    "openai/gpt-image-2",
    "bytedance-seed/seedream-4.5",
    "x-ai/grok-imagine-image-quality",
    "black-forest-labs/flux.2-max",
}
DEFAULT_OPENROUTER_IMAGE_MODEL = "google/gemini-3.1-flash-image"


def _as_dict(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return value if isinstance(value, dict) else {}


def get_openrouter_control(model: Any) -> dict | None:
    """Return curated OpenRouter metadata from an app-state model."""

    model = _as_dict(model)
    info = _as_dict(model.get("info"))
    meta = _as_dict(info.get("meta"))
    control = _as_dict(meta.get("openrouter"))
    return control or None


def is_openrouter_model(model: Any) -> bool:
    return get_openrouter_control(model) is not None


def model_supports_web_search(model: Any) -> bool:
    """Honor an explicit model capability opt-out for every search path.

    The UI normally prevents unsupported models from enabling web search, but
    old chats and a user's global default can still submit ``web_search=true``.
    Treat the curated capability as the provider-boundary safety contract too.
    """

    model = _as_dict(model)
    info = _as_dict(model.get("info"))
    meta = _as_dict(info.get("meta"))
    capabilities = _as_dict(meta.get("capabilities"))
    return capabilities.get("web_search") is not False


def should_use_openrouter_search(features: Any, model: Any) -> bool:
    features = _as_dict(features)
    control = get_openrouter_control(model)
    return bool(
        control
        and model_supports_web_search(model)
        and control.get("web_search", True)
        and features.get("web_search")
    )


def _bounded_int(value: Any, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, parsed))


def _domain_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None

    domains: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        domain = item.strip().lower()
        if domain and domain not in domains:
            domains.append(domain)
        if len(domains) >= 20:
            break
    return domains or None


def resolve_openrouter_search_parameters(options: Any) -> dict:
    """Validate UI search options against OpenRouter's server-tool schema."""

    options = _as_dict(options)
    engine = options.get("engine")
    if engine not in OPENROUTER_SEARCH_ENGINES:
        engine = "auto"

    parameters: dict[str, Any] = {"engine": engine}

    max_results_limit = 20 if engine == "perplexity" else 25
    numeric_fields = {
        "max_results": (1, max_results_limit),
        "max_total_results": (1, 250),
        "max_uses": (1, 30),
        "max_characters": (1, 100_000),
    }
    for field, bounds in numeric_fields.items():
        value = _bounded_int(options.get(field), *bounds)
        if value is not None:
            parameters[field] = value

    context_size = options.get("search_context_size")
    if context_size in OPENROUTER_SEARCH_CONTEXT_SIZES:
        parameters["search_context_size"] = context_size

    allowed_domains = _domain_list(options.get("allowed_domains"))
    excluded_domains = _domain_list(options.get("excluded_domains"))

    if allowed_domains:
        parameters["allowed_domains"] = allowed_domains
    # Exa permits both lists. The other selectable engines either reject the
    # combination or silently ignore part of it, so prefer the allow-list.
    if excluded_domains and (not allowed_domains or engine == "exa"):
        parameters["excluded_domains"] = excluded_domains

    return parameters


def resolve_openrouter_image_parameters(options: Any) -> dict:
    """Validate the selected OpenRouter image service model.

    Image endpoints expose different size, quality, and aspect-ratio controls.
    Keep the first UI iteration deliberately portable and let each provider use
    its own defaults; the selected model is the only universal parameter.
    """

    options = _as_dict(options)
    model = options.get("model")
    if model not in OPENROUTER_IMAGE_MODELS:
        model = DEFAULT_OPENROUTER_IMAGE_MODEL
    return {"model": model}


def _openrouter_session_id(chat_id: Any) -> str | None:
    if not isinstance(chat_id, str) or not chat_id:
        return None
    digest = hashlib.sha256(chat_id.encode("utf-8")).hexdigest()
    return f"owui-{digest[:40]}"


def _apply_prompt_caching(
    form_data: dict,
    features: dict,
    control: dict,
) -> None:
    cache_options = _as_dict(features.get("openrouter_cache_config"))
    mode = cache_options.get("mode", control.get("cache_mode", "smart"))
    if mode not in OPENROUTER_CACHE_MODES:
        mode = "smart"

    # OpenAI and xAI prompt caching is automatic. Claude benefits from an
    # explicit moving breakpoint; the one-hour TTL is an intentional opt-in
    # because its cache writes cost more.
    if control.get("official_provider") == "anthropic" and mode in {"smart", "long"}:
        cache_control = {"type": "ephemeral"}
        if mode == "long":
            cache_control["ttl"] = "1h"
        form_data["cache_control"] = cache_control
    elif mode == "provider_default":
        form_data.pop("cache_control", None)


def _relax_external_search_provider_routing(form_data: dict) -> None:
    """Keep the provider allow-list while relaxing server-tool compatibility.

    Curated model parameters still live under ``params.custom_params`` while
    middleware is assembling tools. Direct API callers may already have a
    top-level provider object, so handle both forms.
    """

    providers: list[dict] = []
    top_level = form_data.get("provider")
    if isinstance(top_level, dict):
        providers.append(top_level)

    params = form_data.get("params")
    custom_params = params.get("custom_params") if isinstance(params, dict) else None
    nested = custom_params.get("provider") if isinstance(custom_params, dict) else None
    if isinstance(nested, dict):
        providers.append(nested)

    for provider in providers:
        provider.pop("require_parameters", None)


def finalize_openrouter_request(form_data: dict) -> None:
    """Apply compatibility changes after model parameters reach the payload.

    Open WebUI promotes curated model parameters more than once. This final
    provider-boundary pass prevents the strict flag from being reintroduced
    after the server tool was assembled.
    """

    tools = form_data.get("tools")
    if not isinstance(tools, list):
        return
    search_tool = next(
        (
            tool
            for tool in tools
            if isinstance(tool, dict) and tool.get("type") == "openrouter:web_search"
        ),
        None,
    )
    if not search_tool:
        return
    parameters = _as_dict(search_tool.get("parameters"))
    if parameters.get("engine", "auto") not in {"auto", "native"}:
        _relax_external_search_provider_routing(form_data)


def apply_openrouter_request(
    form_data: dict,
    features: Any,
    model: Any,
    chat_id: Any,
) -> bool:
    """Apply gateway features and return whether OR web search was injected."""

    control = get_openrouter_control(model)
    if not control:
        return False

    features = _as_dict(features)
    session_id = _openrouter_session_id(chat_id)
    if session_id:
        form_data["session_id"] = session_id

    _apply_prompt_caching(form_data, features, control)

    if not should_use_openrouter_search(features, model):
        return False

    search_parameters = resolve_openrouter_search_parameters(
        features.get("web_search_config")
    )
    # OpenRouter's external search engines currently fail before provider
    # selection when strict parameter compatibility is requested. Keep the
    # official-provider allow-list and disabled fallbacks, but let the gateway
    # own its server-tool parameter for non-native engines. Native search can
    # retain the stricter compatibility filter.
    if search_parameters["engine"] not in {"auto", "native"}:
        _relax_external_search_provider_routing(form_data)

    web_search_tool = {
        "type": "openrouter:web_search",
        "parameters": search_parameters,
    }

    tools = deepcopy(form_data.get("tools"))
    if not isinstance(tools, list):
        tools = []
    tools = [
        tool
        for tool in tools
        if not (
            isinstance(tool, dict)
            and tool.get("type") == "openrouter:web_search"
        )
    ]
    tools.append(web_search_tool)
    form_data["tools"] = tools

    # OpenRouter counts all server-tool calls against this shared budget. A
    # pre-existing lower value remains authoritative.
    max_uses = search_parameters.get("max_uses")
    if max_uses is not None:
        existing_budget = _bounded_int(form_data.get("max_tool_calls"), 1, 30)
        form_data["max_tool_calls"] = (
            min(existing_budget, max_uses) if existing_budget else max_uses
        )

    return True
