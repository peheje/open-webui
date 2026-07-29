"""Validated per-request web-search provider selection."""

from typing import Any

WEB_SEARCH_SELECTABLE_ENGINES = {'brave', 'serper'}


def resolve_web_search_engine(
    options: dict[str, Any] | None,
    default_engine: str,
) -> str:
    """Return an allowed per-request engine or the configured default."""
    options = options if isinstance(options, dict) else {}

    engine = options.get('engine')
    if engine not in WEB_SEARCH_SELECTABLE_ENGINES:
        engine = default_engine

    return engine


def resolve_web_search_engine_from_features(
    features: dict[str, Any] | None,
    default_engine: str,
) -> str:
    """Resolve the UI's per-chat engine for a native tool call."""
    features = features if isinstance(features, dict) else {}
    return resolve_web_search_engine(
        features.get('web_search_config'),
        default_engine,
    )
