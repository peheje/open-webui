"""Per-request web-search controls with server-enforced limits."""

from typing import Any

WEB_SEARCH_DEPTH_PRESETS = {
    'quick': {'max_queries': 1, 'max_sources': 3},
    'normal': {'max_queries': 2, 'max_sources': 6},
    'deep': {'max_queries': 4, 'max_sources': 12},
}

WEB_SEARCH_SELECTABLE_ENGINES = {'brave', 'serper'}
DEFAULT_WEB_SEARCH_DEPTH = 'normal'


def resolve_web_search_options(
    options: dict[str, Any] | None,
    default_engine: str,
) -> dict[str, Any]:
    """Resolve user-selectable options without accepting arbitrary limits."""
    options = options if isinstance(options, dict) else {}

    engine = options.get('engine')
    if engine not in WEB_SEARCH_SELECTABLE_ENGINES:
        engine = default_engine

    depth = options.get('depth')
    if depth not in WEB_SEARCH_DEPTH_PRESETS:
        depth = DEFAULT_WEB_SEARCH_DEPTH

    return {
        'engine': engine,
        'depth': depth,
        **WEB_SEARCH_DEPTH_PRESETS[depth],
    }


def cap_search_queries(queries: list[Any], max_queries: int) -> list[str]:
    """Strip, deduplicate, and cap generated search queries."""
    capped = []
    seen = set()

    for query in queries:
        if not isinstance(query, str):
            continue
        query = query.strip()
        if not query or query in seen:
            continue
        seen.add(query)
        capped.append(query)
        if len(capped) >= max_queries:
            break

    return capped


def cap_unique_urls(urls: list[str], max_sources: int) -> list[str]:
    """Keep URL order while deduplicating and applying the source cap."""
    return list(dict.fromkeys(urls))[:max_sources]
