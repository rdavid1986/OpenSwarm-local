"""Local store for CONFIG.1 global user configuration."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from backend.apps.configuration.models import GlobalUserConfig, default_global_config, sanitize_global_config_payload
from backend.config.paths import SETTINGS_DIR

GLOBAL_CONFIG_FILE = os.path.join(SETTINGS_DIR, "global_config.json")
_global_config_write_lock = threading.Lock()


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
