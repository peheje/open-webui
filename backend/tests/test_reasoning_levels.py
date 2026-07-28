from open_webui.utils.reasoning_levels import (
    get_reasoning_control,
    merge_reasoning_params,
    resolve_reasoning_level,
)


CONTROL = {
    'reasoning_control': {
        'default_level': 'r1',
        'levels': {
            'r0': {
                'label': 'Instant',
                'params': {
                    'reasoning_effort': None,
                    'custom_params': {'thinking': {'type': 'disabled'}},
                },
            },
            'r1': {
                'label': 'Balanced',
                'params': {
                    'reasoning_effort': 'high',
                    'custom_params': {'thinking': {'type': 'enabled'}},
                },
            },
            'r2': {
                'label': 'Deep',
                'params': {
                    'reasoning_effort': 'max',
                    'custom_params': {'thinking': {'type': 'enabled'}},
                },
            },
        },
    }
}


def test_control_resolves_default_and_requested_levels():
    assert get_reasoning_control(CONTROL)['default_level'] == 'r1'
    assert resolve_reasoning_level(CONTROL) == 'r1'
    assert resolve_reasoning_level(CONTROL, 'r2') == 'r2'
    assert resolve_reasoning_level(CONTROL, 'invalid') == 'r1'


def test_reasoning_preset_wins_and_nested_custom_params_are_preserved():
    params, level = merge_reasoning_params(
        {'temperature': 0.4},
        {
            'reasoning_level': 'r0',
            'reasoning_effort': 'high',
            'custom_params': {'provider_flag': True},
        },
        CONTROL,
    )

    assert level == 'r0'
    assert params == {
        'temperature': 0.4,
        'reasoning_effort': None,
        'custom_params': {
            'provider_flag': True,
            'thinking': {'type': 'disabled'},
        },
    }


def test_unsupported_models_strip_internal_level_without_changing_params():
    params, level = merge_reasoning_params(
        {'temperature': 0.2},
        {'reasoning_level': 'r2', 'top_p': 0.9},
        {},
    )
    assert level is None
    assert params == {'temperature': 0.2, 'top_p': 0.9}
