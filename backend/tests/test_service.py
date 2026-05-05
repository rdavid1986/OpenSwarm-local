"""Tests for the service-sync layer.

Public surface is a single `submit(kind, payload)` function. The desktop
hands off opaque dicts; the cloud knows the schema. These tests verify:

  - Envelope (install_id, user_id) is stamped on every submission
  - Routing — three valid `kind` values reach the right path
  - Opt-out (Minimal mode) blocks state/session, lets diagnostic flow
  - Test sink intercepts every submission
  - Spool round-trip (enqueue/drain/acknowledge)

Run:
    cd backend && python -m pytest tests/test_service.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from unittest.mock import patch

import pytest

_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("OPENSWARM_DATA_DIR", _tmpdir)


@pytest.fixture(autouse=True)
def patch_settings(tmp_path):
    sf = tmp_path / "settings.json"
    sf.write_text(json.dumps({
        "installation_id": "test-install-abc",
        "analytics_opt_in": True,
    }))
    import backend.apps.settings.settings as settings_mod
    old = settings_mod.SETTINGS_FILE
    settings_mod.SETTINGS_FILE = str(sf)
    yield
    settings_mod.SETTINGS_FILE = old


@pytest.fixture(autouse=True)
def fresh_client(tmp_path):
    import backend.apps.service.client as client
    client._install_id = None
    client._user_id = None
    client._test_sink = None
    spool = tmp_path / "spool.db"
    with patch.object(client, "_spool_path", lambda: str(spool)):
        yield


@pytest.fixture
def sink():
    captured: list[tuple[str, dict]] = []
    import backend.apps.service.client as client
    client.set_test_sink(lambda kind, body: captured.append((kind, body)))
    yield captured
    client.set_test_sink(None)


# --- core submit ---------------------------------------------------------

def test_submit_state_kind_routed(sink):
    from backend.apps.service.client import submit
    submit("state", {"foo": "bar"})
    assert len(sink) == 1
    kind, body = sink[0]
    assert kind == "state"
    assert body["payload"] == {"foo": "bar"}


def test_submit_session_kind_routed(sink):
    from backend.apps.service.client import submit
    submit("session", {"id": "s-1"})
    kind, body = sink[0]
    assert kind == "session"
    assert body["payload"] == {"id": "s-1"}


def test_submit_diagnostic_kind_routed(sink):
    from backend.apps.service.client import submit
    submit("diagnostic", {"err": "boom"})
    kind, body = sink[0]
    assert kind == "diagnostic"


def test_submit_event_kind_routed(sink):
    from backend.apps.service.client import submit
    submit("event", {"any": "thing"})
    kind, _ = sink[0]
    assert kind == "event"


def test_unknown_kind_dropped(sink):
    from backend.apps.service.client import submit
    submit("nonsense", {"x": 1})
    assert sink == []


def test_envelope_stamped_with_install_id(sink):
    from backend.apps.service.client import submit
    submit("state", {})
    _, body = sink[0]
    assert body["client_state"]["install_id"] == "test-install-abc"


def test_envelope_stamped_with_user_id_when_set(sink):
    from backend.apps.service.client import submit, set_user_id
    set_user_id("alice@example.com")
    submit("state", {})
    _, body = sink[0]
    assert body["client_state"]["user_id"] == "alice@example.com"


def test_user_id_absent_when_not_set(sink):
    from backend.apps.service.client import submit
    submit("state", {})
    _, body = sink[0]
    assert "user_id" not in body["client_state"]


def test_user_id_cleared_with_none(sink):
    from backend.apps.service.client import submit, set_user_id
    set_user_id("alice@example.com")
    set_user_id(None)
    submit("state", {})
    _, body = sink[0]
    assert "user_id" not in body["client_state"]


def test_user_id_cleared_with_empty_string(sink):
    from backend.apps.service.client import submit, set_user_id
    set_user_id("alice@example.com")
    set_user_id("")
    submit("state", {})
    _, body = sink[0]
    assert "user_id" not in body["client_state"]


def test_envelope_includes_environment_metadata(sink):
    from backend.apps.service.client import submit
    submit("state", {})
    _, body = sink[0]
    cs = body["client_state"]
    # OS + device fields should be present on every modern platform.
    assert cs.get("device_type") == "desktop"
    assert cs.get("os")  # darwin / linux / windows
    assert cs.get("os_version")


def test_payload_round_trips_unchanged(sink):
    """Whatever shape the call site hands in, the payload reaches the
    sink intact. The desktop has no schema knowledge."""
    from backend.apps.service.client import submit
    payload = {
        "deeply": {"nested": {"data": [1, 2, 3]}},
        "weird_field_name_42": True,
        "list": ["a", "b"],
        "null": None,
        "number": 3.14,
    }
    submit("session", payload)
    _, body = sink[0]
    assert body["payload"] == payload


def test_empty_payload_accepted(sink):
    from backend.apps.service.client import submit
    submit("state", {})
    assert len(sink) == 1


def test_none_payload_treated_as_empty(sink):
    from backend.apps.service.client import submit
    submit("state", None)  # type: ignore[arg-type]
    _, body = sink[0]
    assert body["payload"] == {}


def test_kind_field_carried_in_body(sink):
    from backend.apps.service.client import submit
    submit("session", {})
    _, body = sink[0]
    assert body["kind"] == "session"


def test_timestamp_carried_in_body(sink):
    from backend.apps.service.client import submit
    submit("state", {})
    _, body = sink[0]
    assert isinstance(body["ts"], float)
    assert body["ts"] > 0


# --- opt-out gating ------------------------------------------------------

def test_minimal_mode_blocks_state(sink, tmp_path):
    sf = tmp_path / "minimal.json"
    sf.write_text(json.dumps({
        "installation_id": "test-install-abc",
        "analytics_opt_in": False,
    }))
    import backend.apps.settings.settings as settings_mod
    settings_mod.SETTINGS_FILE = str(sf)
    from backend.apps.service.client import submit
    submit("state", {"x": 1})
    assert sink == []


def test_minimal_mode_blocks_session(sink, tmp_path):
    sf = tmp_path / "minimal.json"
    sf.write_text(json.dumps({
        "installation_id": "test-install-abc",
        "analytics_opt_in": False,
    }))
    import backend.apps.settings.settings as settings_mod
    settings_mod.SETTINGS_FILE = str(sf)
    from backend.apps.service.client import submit
    submit("session", {"id": "s"})
    assert sink == []


def test_minimal_mode_blocks_event(sink, tmp_path):
    sf = tmp_path / "minimal.json"
    sf.write_text(json.dumps({
        "installation_id": "test-install-abc",
        "analytics_opt_in": False,
    }))
    import backend.apps.settings.settings as settings_mod
    settings_mod.SETTINGS_FILE = str(sf)
    from backend.apps.service.client import submit
    submit("event", {})
    assert sink == []


def test_minimal_mode_allows_diagnostic(sink, tmp_path):
    """Errors/bug reports are usability-essential. Always flow."""
    sf = tmp_path / "minimal.json"
    sf.write_text(json.dumps({
        "installation_id": "test-install-abc",
        "analytics_opt_in": False,
    }))
    import backend.apps.settings.settings as settings_mod
    settings_mod.SETTINGS_FILE = str(sf)
    from backend.apps.service.client import submit
    submit("diagnostic", {"err": "x"})
    assert len(sink) == 1


def test_standard_mode_passes_everything(sink):
    from backend.apps.service.client import submit
    submit("state", {})
    submit("session", {})
    submit("diagnostic", {})
    submit("event", {})
    assert len(sink) == 4


def test_settings_load_failure_defaults_to_enabled(sink):
    import backend.apps.settings.settings as settings_mod
    settings_mod.SETTINGS_FILE = "/nonexistent/path/settings.json"
    from backend.apps.service.client import submit
    submit("state", {})
    assert len(sink) == 1


# --- legacy shim API (back-compat) --------------------------------------

def test_legacy_submit_event_shim(sink):
    from backend.apps.service.client import submit_event
    submit_event("session", "started", {"model": "sonnet"})
    kind, body = sink[0]
    assert kind == "event"
    p = body["payload"]
    assert p["surface"] == "session"
    assert p["action"] == "started"
    assert p["props"] == {"model": "sonnet"}


def test_legacy_submit_session_close_shim(sink):
    from backend.apps.service.client import submit_session_close
    submit_session_close({"id": "s-1", "cost_usd": 0.42})
    kind, body = sink[0]
    assert kind == "session"
    assert body["payload"]["usage_window"] == {"id": "s-1", "cost_usd": 0.42}


def test_legacy_submit_diagnostic_shim(sink):
    from backend.apps.service.client import submit_diagnostic
    submit_diagnostic({"kind": "error_caught"})
    kind, body = sink[0]
    assert kind == "diagnostic"
    assert body["payload"]["diagnostic"]["kind"] == "error_caught"


def test_legacy_submit_state_shim(sink):
    from backend.apps.service.client import submit_state
    submit_state(sessions_open=3, connectors_active=1)
    kind, body = sink[0]
    assert kind == "state"
    assert body["payload"]["sessions_open"] == 3


def test_legacy_record_shim(sink):
    from backend.apps.service.client import record
    record("subscription.activated", {"plan": "pro"})
    kind, body = sink[0]
    assert kind == "event"
    p = body["payload"]
    assert p["surface"] == "subscription"
    assert p["action"] == "activated"


def test_legacy_record_shim_no_dot(sink):
    from backend.apps.service.client import record
    record("singleword", {})
    _, body = sink[0]
    p = body["payload"]
    assert p["surface"] == "singleword"
    assert p["action"] == "fired"


def test_legacy_identify_shim(sink):
    from backend.apps.service.client import identify
    identify({"plan": "pro"})
    kind, body = sink[0]
    assert kind == "state"
    assert body["payload"]["identity"] == {"plan": "pro"}


def test_legacy_session_id_propagates_through_event_shim(sink):
    from backend.apps.service.client import submit_event
    submit_event("session", "tool_call", session_id="s-1", dashboard_id="d-1")
    _, body = sink[0]
    p = body["payload"]
    assert p["session_id"] == "s-1"
    assert p["dashboard_id"] == "d-1"


# --- spool round-trip ----------------------------------------------------

def test_buffer_enqueue_and_drain(tmp_path):
    from backend.apps.service import buffer
    spool = str(tmp_path / "s.db")
    buffer.enqueue(spool, "state:/x", {"a": 1}, now=time.time())
    buffer.enqueue(spool, "state:/x", {"a": 2}, now=time.time())
    assert buffer.count(spool) == 2
    rows = buffer.drain(spool, batch_size=10)
    assert [r[2]["a"] for r in rows] == [1, 2]
    buffer.acknowledge(spool, [r[0] for r in rows])
    assert buffer.count(spool) == 0


def test_buffer_drain_partial(tmp_path):
    from backend.apps.service import buffer
    spool = str(tmp_path / "s.db")
    for i in range(5):
        buffer.enqueue(spool, "state:/x", {"i": i}, now=time.time())
    rows = buffer.drain(spool, batch_size=2)
    assert len(rows) == 2
    assert buffer.count(spool) == 5
    buffer.acknowledge(spool, [r[0] for r in rows])
    assert buffer.count(spool) == 3


def test_buffer_clear(tmp_path):
    from backend.apps.service import buffer
    spool = str(tmp_path / "s.db")
    buffer.enqueue(spool, "state:/x", {}, now=time.time())
    buffer.enqueue(spool, "state:/x", {}, now=time.time())
    buffer.clear(spool)
    assert buffer.count(spool) == 0


def test_buffer_count_on_missing_file(tmp_path):
    from backend.apps.service import buffer
    assert buffer.count(str(tmp_path / "nope.db")) == 0


def test_buffer_drain_on_missing_file(tmp_path):
    from backend.apps.service import buffer
    assert buffer.drain(str(tmp_path / "nope.db")) == []


def test_buffer_corrupt_row_dropped(tmp_path):
    from backend.apps.service import buffer
    spool = str(tmp_path / "s.db")
    with buffer._conn(spool) as c:
        c.execute(
            "INSERT INTO spool (kind, payload, created_at) VALUES (?, ?, ?)",
            ("state:/x", "{not json", time.time()),
        )
    rows = buffer.drain(spool)
    assert rows == []
    assert buffer.count(spool) == 0


def test_buffer_size_cap_under_threshold_retains_all(tmp_path):
    from backend.apps.service import buffer
    spool = str(tmp_path / "s.db")
    big = "x" * 1024
    for i in range(200):
        buffer.enqueue(spool, "state:/x", {"i": i, "pad": big}, now=time.time())
    assert buffer.count(spool) == 200


# --- drain coro ----------------------------------------------------------

@pytest.mark.asyncio
async def test_drain_spool_with_no_entries():
    from backend.apps.service.client import drain_spool
    n = await drain_spool()
    assert n == 0


# --- identity caching ---------------------------------------------------

def test_install_id_persisted_in_settings(sink, tmp_path):
    sf = tmp_path / "fresh.json"
    sf.write_text(json.dumps({"analytics_opt_in": True}))
    import backend.apps.settings.settings as settings_mod
    settings_mod.SETTINGS_FILE = str(sf)
    import backend.apps.service.client as client
    client._install_id = None
    from backend.apps.service.client import submit
    submit("state", {})
    _, body = sink[0]
    iid = body["client_state"]["install_id"]
    assert iid
    raw = json.loads(sf.read_text())
    assert raw["installation_id"] == iid


def test_install_id_stable_across_calls(sink):
    from backend.apps.service.client import submit
    submit("state", {})
    submit("state", {})
    iid1 = sink[0][1]["client_state"]["install_id"]
    iid2 = sink[1][1]["client_state"]["install_id"]
    assert iid1 == iid2


# --- SubApp endpoint ----------------------------------------------------

@pytest.mark.asyncio
async def test_endpoint_post_submit_happy_path(sink):
    from backend.apps.service.service import post_submit
    res = await post_submit({"kind": "state", "payload": {"x": 1}})
    assert res == {"ok": True}
    assert len(sink) == 1
    kind, body = sink[0]
    assert kind == "state"
    assert body["payload"] == {"x": 1}


@pytest.mark.asyncio
async def test_endpoint_post_submit_missing_kind_rejected(sink):
    from backend.apps.service.service import post_submit
    res = await post_submit({"payload": {}})
    assert res["ok"] is False
    assert sink == []


@pytest.mark.asyncio
async def test_endpoint_post_submit_missing_payload_rejected(sink):
    from backend.apps.service.service import post_submit
    res = await post_submit({"kind": "state"})
    assert res["ok"] is False
    assert sink == []


@pytest.mark.asyncio
async def test_endpoint_post_submit_truncates_kind(sink):
    from backend.apps.service.service import post_submit
    long_kind = "x" * 100
    res = await post_submit({"kind": long_kind, "payload": {}})
    # Truncated to 32 chars, still unknown to router → dropped.
    assert res == {"ok": True}
    assert sink == []


@pytest.mark.asyncio
async def test_endpoint_legacy_event_happy_path(sink):
    from backend.apps.service.service import post_event
    res = await post_event({"surface": "test", "action": "happy"})
    assert res == {"ok": True}
    assert len(sink) == 1


@pytest.mark.asyncio
async def test_endpoint_legacy_event_missing_surface(sink):
    from backend.apps.service.service import post_event
    res = await post_event({"action": "x"})
    assert res["ok"] is False


@pytest.mark.asyncio
async def test_endpoint_legacy_event_missing_action(sink):
    from backend.apps.service.service import post_event
    res = await post_event({"surface": "x"})
    assert res["ok"] is False


@pytest.mark.asyncio
async def test_endpoint_spool_count(tmp_path):
    from backend.apps.service import client as svc, buffer
    from backend.apps.service.service import spool_count
    spool = str(tmp_path / "spool.db")
    with patch.object(svc, "_spool_path", lambda: spool):
        buffer.enqueue(spool, "state:/x", {}, now=time.time())
        result = await spool_count()
        assert result == {"pending": 1}
