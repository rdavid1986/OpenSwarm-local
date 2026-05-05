"""Service-sync SubApp.

Exposes a single POST endpoint the frontend posts to. Body shape:
`{kind: str, payload: dict}`. The backend forwards via the service
client, which handles cloud delivery and offline retry.

A periodic spool drainer replays any submissions queued while offline
once the network comes back.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from backend.config.Apps import SubApp
from backend.apps.service import client as svc

logger = logging.getLogger(__name__)

_drain_task: asyncio.Task | None = None


@asynccontextmanager
async def service_lifespan():
    global _drain_task

    async def _drain_loop():
        while True:
            try:
                await svc.drain_spool()
            except Exception as e:
                logger.debug("service spool drain failed: %s", e)
            await asyncio.sleep(60)

    _drain_task = asyncio.create_task(_drain_loop())
    try:
        yield
    finally:
        if _drain_task:
            _drain_task.cancel()
            try:
                await _drain_task
            except asyncio.CancelledError:
                pass


service = SubApp("service", service_lifespan)


@service.router.post("/submit")
async def post_submit(body: dict):
    """Receive an opaque payload from the frontend and forward to the
    cloud. Body: `{kind: str, payload: dict}`."""
    kind = body.get("kind") or ""
    payload = body.get("payload")
    if not kind or not isinstance(payload, dict):
        return {"ok": False, "error": "kind and payload required"}
    svc.submit(str(kind)[:32], payload)
    return {"ok": True}


@service.router.post("/event")
async def post_event(body: dict):
    """Legacy frontend endpoint kept for back-compat with the existing
    analytics.ts shim. Body: `{surface, action, props?, session_id?,
    dashboard_id?, kind?}`. Forwards via `submit_event` which wraps
    into the same opaque payload."""
    surface = body.get("surface") or ""
    action = body.get("action") or ""
    if not surface or not action:
        return {"ok": False, "error": "surface and action are required"}
    svc.submit_event(
        surface=str(surface)[:64],
        action=str(action)[:64],
        props=body.get("props") or {},
        session_id=body.get("session_id"),
        dashboard_id=body.get("dashboard_id"),
        kind=str(body.get("kind") or "event")[:32],
    )
    return {"ok": True}


@service.router.get("/spool/count")
async def spool_count():
    from backend.apps.service import buffer
    return {"pending": buffer.count(svc._spool_path())}
