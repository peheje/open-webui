import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from open_webui.utils.web_search_config import (
    resolve_web_search_engine,
    resolve_web_search_engine_from_features,
)


def test_valid_per_request_engine_overrides_default():
    assert resolve_web_search_engine({'engine': 'brave'}, 'serper') == 'brave'
    assert resolve_web_search_engine({'engine': 'serper'}, 'brave') == 'serper'


def test_invalid_or_missing_engine_falls_back_safely():
    assert resolve_web_search_engine({'engine': 'other'}, 'brave') == 'brave'
    assert resolve_web_search_engine(None, 'serper') == 'serper'


def test_native_tool_features_use_per_chat_engine():
    features = {
        'web_search': True,
        'web_search_config': {'engine': 'serper'},
    }
    assert resolve_web_search_engine_from_features(features, 'brave') == 'serper'
    assert resolve_web_search_engine_from_features({}, 'brave') == 'brave'


def test_removed_depth_setting_has_no_effect():
    assert (
        resolve_web_search_engine(
            {'engine': 'serper', 'depth': 'quick'},
            'brave',
        )
        == 'serper'
    )


def test_native_builtin_routes_search_to_per_chat_engine():
    """Guard the complete native-tool path, not only the config resolver."""
    from open_webui.tools import builtin

    async def run():
        captured = {}

        async def fake_config(key, *args):
            return {
                'web.search.engine': 'brave',
                'web.search.result_count': 5,
            }[key]

        async def fake_search(request, engine, query, user):
            captured.update(engine=engine, query=query)
            return [
                SimpleNamespace(
                    title='Result',
                    link='https://example.com',
                    snippet='Example',
                )
            ]

        with (
            patch.object(builtin.Config, 'get', side_effect=fake_config),
            patch.object(builtin, '_search_web', side_effect=fake_search),
        ):
            result = await builtin.search_web(
                'routing probe',
                __request__=object(),
                __features__={'web_search_config': {'engine': 'serper'}},
            )

        assert captured == {'engine': 'serper', 'query': 'routing probe'}
        assert 'https://example.com' in result

    asyncio.run(run())
