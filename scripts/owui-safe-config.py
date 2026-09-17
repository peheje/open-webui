#!/usr/bin/env python3
"""Export and restore a deliberately small, secret-free Open WebUI config."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1

# Exact keys only. Connection details, URLs, prompts, headers, and credentials are
# intentionally absent even when they might appear harmless in one installation.
SAFE_CONFIG_KEYS = frozenset(
    {
        "auth.api_key.allowed_endpoints",
        "auth.api_key.endpoint_restrictions",
        "auth.enable_api_keys",
        "auth.jwt_expiry",
        "automations.enable",
        "automations.max_count",
        "automations.min_interval",
        "calendar.enable",
        "channels.enable",
        "channels.model_response_mode",
        "chat.context_compaction.enable",
        "chat.context_compaction.model",
        "chat.context_compaction.retention_percentage",
        "chat.context_compaction.token_cap",
        "chat.context_compaction.token_threshold",
        "chat.tool_permissions.enable",
        "code_execution.enable",
        "code_execution.engine",
        "code_interpreter.enable",
        "code_interpreter.engine",
        "direct.enable",
        "evaluation.arena.enable",
        "evaluation.arena.models",
        "file.image_compression_height",
        "file.image_compression_width",
        "folders.enable",
        "folders.max_file_count",
        "image_generation.enable",
        "image_generation.engine",
        "image_generation.model",
        "image_generation.prompt.enable",
        "image_generation.size",
        "image_generation.steps",
        "images.edit.enable",
        "images.edit.engine",
        "images.edit.model",
        "images.edit.size",
        "memories.background_review.enable",
        "memories.context_char_limit",
        "memories.enable",
        "memories.review_interval_turns",
        "memories.system_context.enable",
        "memories.user_char_limit",
        "models.base_models_cache",
        "models.default_metadata",
        "models.default_params",
        "notes.enable",
        "subagents.background_enabled",
        "subagents.enable",
        "subagents.max_async",
        "subagents.max_concurrent",
        "subagents.max_iterations",
        "subagents.max_output",
        "task.autocomplete.enable",
        "task.autocomplete.input_max_length",
        "task.follow_up.enable",
        "task.model.default",
        "task.model.external",
        "task.query.retrieval.enable",
        "task.query.search.enable",
        "task.tags.enable",
        "task.title.enable",
        "task.voice.prompt.enable",
        "ui.default_locale",
        "ui.default_models",
        "ui.default_pinned_models",
        "ui.default_user_role",
        "ui.enable_community_sharing",
        "ui.enable_login_form",
        "ui.enable_message_rating",
        "ui.enable_password_change_form",
        "ui.enable_signup",
        "ui.enable_user_webhooks",
        "ui.model_order_list",
        "users.enable_status",
        "web.loader.concurrent_requests",
        "web.loader.engine",
        "web.loader.ssl_verification",
        "web.loader.timeout",
        "web.search.brave_search_context_tokens",
        "web.search.bypass_embedding_and_retrieval",
        "web.search.bypass_web_loader",
        "web.search.concurrent_requests",
        "web.search.confirmation.enable",
        "web.search.ddgs_backend",
        "web.search.domain.filter_list",
        "web.search.enable",
        "web.search.engine",
        "web.search.result_count",
        "web.search.searxng_language",
        "web.search.trust_env",
    }
)

PARAMS_POLICY: dict[str, Any] = {
    "compact_token_threshold": True,
    "function_calling": True,
    "reasoning_effort": True,
    "custom_params": {
        "provider": {
            "allow_fallbacks": True,
            "only": True,
            "require_parameters": True,
        },
        "thinking": {"type": True},
    },
}

META_POLICY: dict[str, Any] = {
    "builtinTools": {"code_interpreter": True, "web_search": True},
    "capabilities": {
        "code_interpreter": True,
        "file_upload": True,
        "vision": True,
        "web_search": True,
    },
    "defaultFeatureIds": True,
    "hidden": True,
    "openrouter": {
        "always_web_search": True,
        "byok_provider": True,
        "cache_mode": True,
        "default_routing_mode": True,
        "official_provider": True,
        "routing_modes": True,
        "search_defaults": {
            "engine": True,
            "max_characters": True,
            "max_results": True,
            "max_total_results": True,
            "max_uses": True,
        },
        "web_search": True,
    },
    "quantization": {"detail": True, "label": True},
}

REASONING_LEVEL_POLICY: dict[str, Any] = {
    "description": True,
    "label": True,
    "params": {
        "custom_params": {
            "reasoning": {"effort": True, "exclude": True},
            "thinking": {"type": True},
        },
        "reasoning_effort": True,
    },
}

SAFE_CONFIG_POLICIES: dict[str, dict[str, Any]] = {
    "models.default_metadata": META_POLICY,
    "models.default_params": PARAMS_POLICY,
}

FORBIDDEN_KEY = re.compile(
    r"(?:^|[_.-])(api[_-]?key|authentication|cookie|credential|password|secret|(?:access|auth|id|refresh)[_-]?token|webhook)(?:$|[_.-])",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b"),
)


class SafeConfigError(ValueError):
    pass


def decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def select_fields(value: Any, policy: Any) -> Any:
    if policy is True:
        return copy.deepcopy(value)
    if not isinstance(value, dict) or not isinstance(policy, dict):
        return None
    selected = {}
    for key, child_policy in policy.items():
        if key in value:
            child = select_fields(value[key], child_policy)
            if child is not None:
                selected[key] = child
    return selected


def select_reasoning_control(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    if "default_level" in value:
        result["default_level"] = copy.deepcopy(value["default_level"])
    levels = value.get("levels")
    if isinstance(levels, dict):
        safe_levels = {
            name: select_fields(level, REASONING_LEVEL_POLICY)
            for name, level in levels.items()
            if isinstance(name, str) and re.fullmatch(r"r\d+", name)
        }
        safe_levels = {key: val for key, val in safe_levels.items() if val}
        if safe_levels:
            result["levels"] = safe_levels
    return result


def select_model_settings(params: Any, meta: Any) -> dict[str, Any]:
    safe_params = select_fields(params, PARAMS_POLICY) or {}
    safe_meta = select_fields(meta, META_POLICY) or {}
    tags = meta.get("tags") if isinstance(meta, dict) else None
    if isinstance(tags, list):
        safe_tags = [
            {"name": tag["name"]}
            for tag in tags
            if isinstance(tag, dict) and isinstance(tag.get("name"), str)
        ]
        if safe_tags:
            safe_meta["tags"] = safe_tags
    reasoning_control = select_reasoning_control(
        meta.get("reasoning_control") if isinstance(meta, dict) else None
    )
    if reasoning_control:
        safe_meta["reasoning_control"] = reasoning_control
    result = {}
    if safe_params:
        result["params"] = safe_params
    if safe_meta:
        result["meta"] = safe_meta
    return result


def scan_for_secrets(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if FORBIDDEN_KEY.search(str(key)):
                raise SafeConfigError(f"forbidden key at {path}.{key}")
            scan_for_secrets(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_for_secrets(child, f"{path}[{index}]")
    elif isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                raise SafeConfigError(f"secret-like value at {path}")


def scan_backup_values(config: dict[str, Any], models: dict[str, Any]) -> None:
    # Config key names are already constrained by the exact allowlist. Scan their
    # values independently so safe names such as "api_key.endpoint_restrictions"
    # and "token_cap" are not mistaken for credential fields.
    for key, value in config.items():
        scan_for_secrets(value, f"$.config[{key!r}]")
    scan_for_secrets(models, "$.models")


def connect_read_only(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise SafeConfigError(f"database does not exist: {database}")
    return sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)


def build_backup(database: Path) -> dict[str, Any]:
    with connect_read_only(database) as connection:
        rows = connection.execute("SELECT key, value FROM config ORDER BY key")
        config = {}
        for key, value in rows:
            if key not in SAFE_CONFIG_KEYS:
                continue
            decoded = decode_json(value)
            if key in SAFE_CONFIG_POLICIES:
                decoded = select_fields(decoded, SAFE_CONFIG_POLICIES[key]) or {}
            config[key] = decoded

        models = {}
        rows = connection.execute("SELECT id, params, meta FROM model ORDER BY id")
        for model_id, params, meta in rows:
            selected = select_model_settings(
                decode_json(params) or {}, decode_json(meta) or {}
            )
            if selected:
                models[model_id] = selected

    backup = {
        "schema_version": SCHEMA_VERSION,
        "config": config,
        "models": models,
    }
    scan_backup_values(config, models)
    return backup


def atomic_json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def validate_backup(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "config", "models"}:
        raise SafeConfigError("backup must contain only schema_version, config, and models")
    if value["schema_version"] != SCHEMA_VERSION:
        raise SafeConfigError(f"unsupported schema_version: {value['schema_version']!r}")
    config = value["config"]
    models = value["models"]
    if not isinstance(config, dict) or not isinstance(models, dict):
        raise SafeConfigError("config and models must be JSON objects")
    unknown_config = sorted(set(config) - SAFE_CONFIG_KEYS)
    if unknown_config:
        raise SafeConfigError(f"non-allowlisted config keys: {', '.join(unknown_config)}")
    for key, policy in SAFE_CONFIG_POLICIES.items():
        if key in config and select_fields(config[key], policy) != config[key]:
            raise SafeConfigError(f"non-allowlisted nested setting for {key}")
    for model_id, settings in models.items():
        if not isinstance(model_id, str) or not isinstance(settings, dict):
            raise SafeConfigError("model entries must be objects keyed by string IDs")
        params = settings.get("params", {})
        meta = settings.get("meta", {})
        if set(settings) - {"params", "meta"}:
            raise SafeConfigError(f"unknown section for model {model_id}")
        selected = select_model_settings(params, meta)
        if selected != settings:
            raise SafeConfigError(f"non-allowlisted model setting for {model_id}")
    scan_backup_values(config, models)
    return value


def deep_merge(target: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(target)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def restore_backup(database: Path, backup: dict[str, Any], apply: bool) -> tuple[int, int, list[str]]:
    if not database.is_file():
        raise SafeConfigError(f"database does not exist: {database}")
    connection = sqlite3.connect(database)
    try:
        existing_models = {
            model_id: (decode_json(params) or {}, decode_json(meta) or {})
            for model_id, params, meta in connection.execute(
                "SELECT id, params, meta FROM model"
            )
        }
        found_models = sorted(set(backup["models"]) & set(existing_models))
        missing_models = sorted(set(backup["models"]) - set(existing_models))
        if not apply:
            return len(backup["config"]), len(found_models), missing_models

        connection.execute("BEGIN IMMEDIATE")
        now = int(time.time())
        for key, value in backup["config"].items():
            connection.execute(
                """
                INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, json.dumps(value, separators=(",", ":")), now),
            )
        for model_id in found_models:
            params, meta = existing_models[model_id]
            settings = backup["models"][model_id]
            merged_params = deep_merge(params, settings.get("params", {}))
            merged_meta = deep_merge(meta, settings.get("meta", {}))
            connection.execute(
                "UPDATE model SET params = ?, meta = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(merged_params, separators=(",", ":")),
                    json.dumps(merged_meta, separators=(",", ":")),
                    now,
                    model_id,
                ),
            )
        connection.commit()
        return len(backup["config"]), len(found_models), missing_models
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def load_backup(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            return validate_backup(json.load(handle))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafeConfigError(f"cannot read backup {path}: {exc}") from exc


def command_backup(args: argparse.Namespace) -> int:
    backup = build_backup(args.database)
    atomic_json_write(args.output, backup)
    print(
        f"Wrote {len(backup['config'])} config keys and "
        f"{len(backup['models'])} model entries to {args.output}"
    )
    return 0


def command_restore(args: argparse.Namespace) -> int:
    backup = load_backup(args.input)
    config_count, model_count, missing_models = restore_backup(
        args.database, backup, args.apply
    )
    action = "Restored" if args.apply else "Validated (dry run)"
    print(f"{action}: {config_count} config keys and {model_count} existing models")
    if missing_models:
        print(
            f"Skipped {len(missing_models)} missing model IDs: " + ", ".join(missing_models),
            file=sys.stderr,
        )
    if not args.apply:
        print("No database changes made; pass --apply to restore")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="write a deterministic safe JSON backup")
    backup.add_argument("--database", required=True, type=Path)
    backup.add_argument("--output", required=True, type=Path)
    backup.set_defaults(func=command_backup)

    restore = subparsers.add_parser("restore", help="validate or restore a safe JSON backup")
    restore.add_argument("--database", required=True, type=Path)
    restore.add_argument("--input", required=True, type=Path)
    restore.add_argument(
        "--apply",
        action="store_true",
        help="apply changes; without this flag restore is a dry run",
    )
    restore.set_defaults(func=command_restore)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return args.func(args)
    except (SafeConfigError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
