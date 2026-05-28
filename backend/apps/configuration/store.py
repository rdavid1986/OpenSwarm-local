"""Local stores for CONFIG.1 global and CONFIG.2 project configuration."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from backend.apps.configuration.models import (
    GlobalUserConfig,
    ProjectConfig,
    default_global_config,
    default_project_config,
    sanitize_global_config_payload,
    sanitize_project_config_payload,
)
from backend.config.paths import PROJECTS_DIR, SETTINGS_DIR

GLOBAL_CONFIG_FILE = os.path.join(SETTINGS_DIR, "global_config.json")
PROJECT_CONFIG_ROOT = PROJECTS_DIR
_global_config_write_lock = threading.Lock()
_project_config_write_lock = threading.Lock()


def global_config_path() -> str:
    """Return the controlled persistence path for global configuration."""
    return GLOBAL_CONFIG_FILE


def load_global_config(*, create_if_missing: bool = True) -> GlobalUserConfig:
    """Load global config, returning safe defaults for missing/legacy files."""
    path = Path(GLOBAL_CONFIG_FILE)
    if not path.exists():
        config = default_global_config()
        if create_if_missing:
            save_global_config(config)
        return config

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        sanitized = sanitize_global_config_payload(raw if isinstance(raw, dict) else {})
        config = GlobalUserConfig(**sanitized)
    except Exception:
        config = default_global_config()
    return config


def save_global_config(config_or_payload: GlobalUserConfig | dict[str, Any]) -> GlobalUserConfig:
    """Validate, sanitize, and atomically persist global configuration."""
    if isinstance(config_or_payload, GlobalUserConfig):
        payload = config_or_payload.model_dump()
    else:
        payload = dict(config_or_payload or {})
    sanitized = sanitize_global_config_payload(payload)
    config = GlobalUserConfig(**sanitized)
    _atomic_write_global_config(config.model_dump())
    return config


def _atomic_write_global_config(payload: dict[str, Any]) -> None:
    with _global_config_write_lock:
        target = Path(GLOBAL_CONFIG_FILE)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".global_config.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
            for attempt in range(2):
                try:
                    os.replace(tmp, target)
                    return
                except PermissionError:
                    if attempt == 1:
                        raise
                    time.sleep(0.05)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def sanitize_project_id(project_id: str) -> str:
    """Return a filesystem-safe project id, rejecting empty traversal-only ids."""
    raw = str(project_id or "").strip()
    if not raw:
        raise ValueError("project_id is required")
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw.replace("\\", "_").replace("/", "_"))
    while ".." in safe:
        safe = safe.replace("..", "_")
    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip("._-")
    if not safe:
        raise ValueError("project_id must contain at least one safe character")
    return safe[:120]


def project_config_path(project_id: str) -> str:
    safe_project_id = sanitize_project_id(project_id)
    return str(Path(PROJECT_CONFIG_ROOT) / safe_project_id / "config.json")


def load_project_config(project_id: str, *, create_if_missing: bool = True) -> ProjectConfig:
    """Load project config, returning safe defaults for missing/legacy files."""
    safe_project_id = sanitize_project_id(project_id)
    path = Path(project_config_path(safe_project_id))
    if not path.exists():
        config = default_project_config(safe_project_id)
        if create_if_missing:
            save_project_config(safe_project_id, config)
        return config

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        sanitized = sanitize_project_config_payload(raw if isinstance(raw, dict) else {}, project_id=safe_project_id)
        config = ProjectConfig(**sanitized)
    except Exception:
        config = default_project_config(safe_project_id)
    return config


def save_project_config(project_id: str, config_or_payload: ProjectConfig | dict[str, Any]) -> ProjectConfig:
    """Validate, sanitize, and atomically persist project configuration."""
    safe_project_id = sanitize_project_id(project_id)
    if isinstance(config_or_payload, ProjectConfig):
        payload = config_or_payload.model_dump()
    else:
        payload = dict(config_or_payload or {})
    sanitized = sanitize_project_config_payload(payload, project_id=safe_project_id)
    config = ProjectConfig(**sanitized)
    _atomic_write_project_config(safe_project_id, config.model_dump())
    return config


def _atomic_write_project_config(project_id: str, payload: dict[str, Any]) -> None:
    with _project_config_write_lock:
        target = Path(project_config_path(project_id))
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".project_config.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
            for attempt in range(2):
                try:
                    os.replace(tmp, target)
                    return
                except PermissionError:
                    if attempt == 1:
                        raise
                    time.sleep(0.05)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
