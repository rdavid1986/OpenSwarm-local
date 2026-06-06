"""Side-effect-free IDE theme compatibility preview API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from backend.config.Apps import SubApp

from .ide_theme_candidates import (
    build_ide_theme_candidate,
    build_ide_theme_diagnostic_report,
    build_ide_theme_source_adapter,
)


@asynccontextmanager
async def _theme_compat_lifespan(app=None):
    yield


theme_compat = SubApp("theme-compat", _theme_compat_lifespan)


@theme_compat.router.post("/ide-theme/preview")
async def preview_ide_theme_candidate(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a reviewable IDE theme/profile candidate without applying anything.

    This endpoint is intentionally side-effect-free:
    - does not apply themes
    - does not install extensions
    - does not copy assets
    - does not mutate settings
    - does not activate permissions
    """

    payload = dict(body or {})
    adapter = build_ide_theme_source_adapter(payload)
    candidate = build_ide_theme_candidate(payload, adapter)
    diagnostic_report = build_ide_theme_diagnostic_report(candidate)

    return {
        "status": "ok",
        "side_effect_free": True,
        "can_apply_theme": False,
        "can_install_extensions": False,
        "can_copy_assets": False,
        "can_mutate_settings": False,
        "can_enable_permissions": False,
        "adapter": adapter.as_dict(),
        "candidate": candidate.as_dict(),
        "diagnostic_report": diagnostic_report.as_dict(),
    }
