from open_webui.utils.web_search_limits import (
    cap_search_queries,
    cap_unique_urls,
    resolve_web_search_options,
)


def test_depth_presets_are_server_enforced():
    assert resolve_web_search_options(
        {'engine': 'brave', 'depth': 'quick', 'max_queries': 99, 'max_sources': 99},
        'serper',
    ) == {
        'engine': 'brave',
        'depth': 'quick',
        'max_queries': 1,
        'max_sources': 3,
    }
    assert resolve_web_search_options({'engine': 'serper', 'depth': 'deep'}, 'brave') == {
        'engine': 'serper',
        'depth': 'deep',
        'max_queries': 4,
        'max_sources': 12,
    }


def test_invalid_options_fall_back_safely():
    assert resolve_web_search_options({'engine': 'other', 'depth': 'unlimited'}, 'brave') == {
        'engine': 'brave',
        'depth': 'normal',
        'max_queries': 2,
        'max_sources': 6,
    }


def test_queries_are_stripped_deduplicated_and_capped():
    assert cap_search_queries([' alpha ', 'alpha', '', None, 'beta', 'gamma'], 2) == [
        'alpha',
        'beta',
    ]


def test_urls_are_deduplicated_and_capped():
    assert cap_unique_urls(['a', 'b', 'a', 'c', 'd'], 3) == ['a', 'b', 'c']
