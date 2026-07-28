from __future__ import annotations

from copy import deepcopy
from typing import Any

from open_webui.utils.misc import deep_update


REASONING_LEVELS = ('r0', 'r1', 'r2')


def _as_dict(value: Any) -> dict:
    if hasattr(value, 'model_dump'):
        value = value.model_dump()
    return value if isinstance(value, dict) else {}


def get_reasoning_control(model_meta: Any) -> dict | None:
    meta = _as_dict(model_meta)
    control = _as_dict(meta.get('reasoning_control'))
    raw_levels = _as_dict(control.get('levels'))

    levels = {
        level: _as_dict(raw_levels.get(level))
        for level in REASONING_LEVELS
        if isinstance(raw_levels.get(level), dict)
    }
    if not levels:
        return None

    default_level = control.get('default_level')
    if default_level not in levels:
        default_level = 'r1' if 'r1' in levels else next(iter(levels))

    return {
        **control,
        'default_level': default_level,
        'levels': levels,
    }


def resolve_reasoning_level(model_meta: Any, requested_level: Any = None) -> str | None:
    control = get_reasoning_control(model_meta)
    if not control:
        return None

    if isinstance(requested_level, str) and requested_level in control['levels']:
        return requested_level
    return control['default_level']


def merge_reasoning_params(
    model_params: Any,
    request_params: Any,
    model_meta: Any,
) -> tuple[dict, str | None]:
    """Merge params and translate OWUI's r0/r1/r2 control into provider params.

    Request parameters normally override model defaults. The selected reasoning
    preset is applied last so global advanced settings cannot accidentally
    contradict the visible reasoning level. Nested custom_params are merged
    instead of replacing unrelated provider options.
    """

    merged = deepcopy(_as_dict(model_params))
    requested = deepcopy(_as_dict(request_params))
    requested_level = requested.pop('reasoning_level', None)
    deep_update(merged, requested)

    control = get_reasoning_control(model_meta)
    if not control:
        return merged, None

    resolved_level = resolve_reasoning_level(model_meta, requested_level)
    level_config = control['levels'][resolved_level]
    reasoning_params = deepcopy(_as_dict(level_config.get('params')))
    deep_update(merged, reasoning_params)
    return merged, resolved_level
