"""Configuration API for CONFIG.1/CONFIG.2 backend base."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import HTTPException

from backend.config.Apps import SubApp
from backend.apps.configuration.models import default_global_config, sanitize_global_config_payload, sanitize_project_config_payload
from backend.apps.configuration.resolver import resolve_effective_config
from backend.apps.configuration.store import (
    global_config_path,
    load_global_config,
    load_project_config,
    project_config_path,
    sanitize_project_id,
    save_global_config,
    save_project_config,
)


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
    return _resolution_payload(resolution)


@configuration.router.get("/projects/{project_id}")
async def get_project_configuration(project_id: str):
    safe_project_id = _safe_project_id_or_400(project_id)
    config = load_project_config(safe_project_id, create_if_missing=True)
    return {
        "ok": True,
        "config": config.model_dump(),
        "path": project_config_path(safe_project_id),
    }


@configuration.router.post("/projects/{project_id}")
async def update_project_configuration(project_id: str, body: dict[str, Any]):
    safe_project_id = _safe_project_id_or_400(project_id)
    body_project_id = body.get("project_id") if isinstance(body, dict) else None
    if body_project_id is not None:
        try:
            body_safe_project_id = sanitize_project_id(str(body_project_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if body_safe_project_id != safe_project_id:
            raise HTTPException(status_code=400, detail="project_id in body must match project_id in path")
    sanitized = sanitize_project_config_payload(body, project_id=safe_project_id)
    config = save_project_config(safe_project_id, sanitized)
    return {
        "ok": True,
        "config": config.model_dump(),
        "path": project_config_path(safe_project_id),
    }


@configuration.router.get("/projects/{project_id}/effective")
async def get_project_effective_configuration(project_id: str):
    safe_project_id = _safe_project_id_or_400(project_id)
    system_defaults = default_global_config().to_user_global_config()
    user_global = load_global_config(create_if_missing=True).to_user_global_config()
    project_config = load_project_config(safe_project_id, create_if_missing=True).to_project_config()
    resolution = resolve_effective_config(
        system_default=system_defaults,
        user_global=user_global,
        project_config=project_config,
    )
    return _resolution_payload(resolution)


def _safe_project_id_or_400(project_id: str) -> str:
    try:
        return sanitize_project_id(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolution_payload(resolution: Any) -> dict[str, Any]:
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
