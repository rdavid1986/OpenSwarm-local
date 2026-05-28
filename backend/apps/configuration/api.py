"""Configuration API for CONFIG.1 backend base."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from backend.config.Apps import SubApp
from backend.apps.configuration.models import default_global_config, sanitize_global_config_payload
from backend.apps.configuration.resolver import resolve_effective_config
from backend.apps.configuration.store import global_config_path, load_global_config, save_global_config


@asynccontextmanager
async def configuration_lifespan():
    yield


configuration = SubApp("configuration", configuration_lifespan)


@configuration.router.get("/global")
async def get_global_configuration():
    config = load_global_config(create_if_missing=True)
    return {
        "ok": True,
        "config": config.model_dump(),
        "path": global_config_path(),
    }


@configuration.router.post("/global")
async def update_global_configuration(body: dict[str, Any]):
    sanitized = sanitize_global_config_payload(body)
    config = save_global_config(sanitized)
    return {
        "ok": True,
        "config": config.model_dump(),
        "path": global_config_path(),
    }


@configuration.router.get("/effective")
async def get_effective_configuration():
    system_defaults = default_global_config().to_user_global_config()
    user_global = load_global_config(create_if_missing=True).to_user_global_config()
    resolution = resolve_effective_config(
        system_default=system_defaults,
        user_global=user_global,
    )
    return {
        "ok": True,
        "effective_config": resolution.effective_config.values,
        "source_map": _stringify_source_map(resolution.source_map),
        "sources": _stringify_source_map(resolution.sources),
        "overrides": [_stringify_sources(item) for item in resolution.overrides],
        "conflicts": [_conflict_to_dict(item) for item in resolution.conflicts],
        "blocked_entries": [_stringify_sources(item) for item in resolution.blocked_entries],
        "required_user_actions": [_required_action_to_dict(item) for item in resolution.required_user_actions],
        "safety_notes": [_safety_note_to_dict(item) for item in resolution.safety_notes],
        "effective_config_hash": resolution.effective_config_hash,
    }


def _stringify_source_map(source_map: dict[str, Any]) -> dict[str, str]:
    return {key: getattr(value, "value", str(value)) for key, value in source_map.items()}


def _stringify_sources(item: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for key, value in item.items():
        converted[key] = getattr(value, "value", value)
    return converted


def _conflict_to_dict(conflict: Any) -> dict[str, Any]:
    return {
        "key": conflict.key,
        "existing_source": getattr(conflict.existing_source, "value", conflict.existing_source),
        "incoming_source": getattr(conflict.incoming_source, "value", conflict.incoming_source),
        "reason": conflict.reason,
        "blocked": conflict.blocked,
    }


def _required_action_to_dict(action: Any) -> dict[str, Any]:
    return {
        "code": action.code,
        "message": action.message,
        "key": action.key,
        "source": getattr(action.source, "value", action.source),
    }


def _safety_note_to_dict(note: Any) -> dict[str, Any]:
    return {
        "code": note.code,
        "message": note.message,
        "key": note.key,
        "source": getattr(note.source, "value", note.source),
        "scope": getattr(note.scope, "value", note.scope),
    }
