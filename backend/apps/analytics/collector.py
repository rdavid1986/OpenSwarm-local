"""Operational state forwarder.

Thin shim kept only because ~50 call sites across the codebase use this
import path. Forwards every call to the service-sync layer in
backend.apps.service.client, which handles the cloud relay.

New code should import from `backend.apps.service.client` directly.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def init():
    """Backwards-compat — service module bootstraps lazily; nothing to do."""
    return None


def shutdown():
    """Backwards-compat — service module manages its own lifecycle."""
    return None


def record(
    event_type: str,
    properties: dict | None = None,
    session_id: str | None = None,
    dashboard_id: str | None = None,
) -> None:
    """Forward to the service-sync layer."""
    try:
        from backend.apps.service.client import submit_event
        if "." in event_type:
            surface, action = event_type.split(".", 1)
        else:
            surface, action = event_type, "fired"
        submit_event(
            surface=surface,
            action=action,
            props=properties or {},
            session_id=session_id,
            dashboard_id=dashboard_id,
        )
    except Exception as e:
        logger.debug("service submit_event failed (non-critical): %s", e)


def identify(extra_properties: dict | None = None) -> None:
    """Forward identity updates to the service-sync layer."""
    try:
        from backend.apps.service.client import update_identity
        update_identity(extra_properties or {})
    except Exception as e:
        logger.debug("service update_identity failed (non-critical): %s", e)


def get_collector():
    """Backwards-compat stub."""
    return None
