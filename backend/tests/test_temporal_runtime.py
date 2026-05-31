from backend.apps.swarms.temporal_runtime import (
    apply_session_temporal_update,
    build_local_time_label,
    build_message_temporal_state,
    build_part_temporal_state,
    build_session_temporal_state,
    build_temporal_context_snapshot,
    build_temporal_execution_state,
    build_temporal_freshness_state,
    build_temporal_trace_source,
    dump_temporal_trace_source,
    sanitize_temporal_metadata,
    temporal_duration_ms,
)

START = "2026-05-31T10:00:00Z"
MID = "2026-05-31T10:00:05Z"
FINISH = "2026-05-31T10:00:10Z"


def test_created_updated_and_metadata_updated_are_separate():
    state = build_session_temporal_state(session_id="s1", created_at=START, updated_at=MID, metadata_updated_at=FINISH)

    assert state.created_at == START
    assert state.updated_at == MID
    assert state.metadata_updated_at == FINISH


def test_metadata_update_does_not_change_last_message_at():
    state = build_session_temporal_state(session_id="s1", created_at=START, last_message_at=MID)
    updated = apply_session_temporal_update(state, event_kind="metadata_update", at=FINISH, metadata={"safe": True})

    assert updated.metadata_updated_at == FINISH
    assert updated.last_message_at == MID
    assert updated.metadata["safe"] is True


def test_user_message_updates_user_and_last_message_times():
    state = build_session_temporal_state(session_id="s1", created_at=START)
    updated = apply_session_temporal_update(state, event_kind="message", role="user", at=MID)

    assert updated.last_user_message_at == MID
    assert updated.last_message_at == MID
    assert updated.message_count == 1


def test_assistant_message_updates_assistant_and_last_message_times():
    state = build_session_temporal_state(session_id="s1", created_at=START)
    updated = apply_session_temporal_update(state, event_kind="message", role="assistant", at=MID)

    assert updated.last_assistant_message_at == MID
    assert updated.last_message_at == MID


def test_activity_update_updates_last_activity_only():
    state = build_session_temporal_state(session_id="s1", created_at=START)
    updated = apply_session_temporal_update(state, event_kind="activity", at=MID)

    assert updated.last_activity_at == MID
    assert updated.last_message_at is None


def test_duration_completed_vs_interrupted():
    completed = build_temporal_execution_state(execution_id="e1", execution_kind="tool", started_at=START, completed_at=FINISH)
    interrupted = build_temporal_execution_state(execution_id="e2", execution_kind="tool", started_at=START, interrupted_at=MID)

    assert completed.duration_ms == 10000
    assert completed.status == "completed"
    assert interrupted.duration_ms == 5000
    assert interrupted.status == "interrupted"


def test_running_duration_uses_now_without_completion():
    running = build_temporal_execution_state(execution_id="e1", execution_kind="model", started_at=START, now=MID)

    assert running.running_duration_ms == 5000
    assert running.duration_ms is None


def test_timezone_local_label_is_stable():
    label = build_local_time_label(START, timezone_name="America/Buenos_Aires")

    assert "2026-05-31" in label
    assert "America/Buenos_Aires" in label


def test_message_gap_and_part_temporal_state():
    message = build_message_temporal_state(message_id="m2", role="assistant", created_at=MID, previous_message_at=START)
    part = build_part_temporal_state(part_id="p1", message_id="m2", part_kind="text", started_at=START, completed_at=MID)

    assert message.elapsed_since_previous_ms == 5000
    assert part.duration_ms == 5000


def test_ai_visible_time_context_is_compact_and_safe():
    session = build_session_temporal_state(session_id="s1", started_at=START, last_message_at=MID)
    freshness = build_temporal_freshness_state(created_at=START, last_verified_at=START, ttl_seconds=60, now=MID)
    snapshot = build_temporal_context_snapshot(session=session, freshness=freshness, timezone_name="UTC", now=MID, metadata={"prompt": "do not leak"})
    text = str(snapshot).lower()

    assert snapshot.ai_visible_context["current_utc"] == MID
    assert snapshot.ai_visible_context["last_message_at"] == MID
    assert "prompt" not in text
    assert "do not leak" not in text


def test_stale_after_and_freshness_states():
    fresh = build_temporal_freshness_state(created_at=START, last_verified_at=START, ttl_seconds=60, now=MID)
    stale = build_temporal_freshness_state(created_at=START, stale_after=MID, now=FINISH)

    assert fresh.status == "fresh"
    assert stale.status == "stale"
    assert "refresh_or_verify_context" in stale.required_actions


def test_temporal_trace_source_redacts_sensitive_metadata():
    execution = build_temporal_execution_state(execution_id="e1", execution_kind="action", started_at=START, completed_at=FINISH, metadata={"secret_token": "leak", "safe": "ok"})
    source = build_temporal_trace_source(execution=execution, metadata={"prompt": "leak", "trace_id": "tr1"})
    text = str(source).lower()

    assert source["source_kind"] == "temporal_runtime"
    assert source["trace_id"] == "tr1"
    assert source["duration_ms"] == 10000
    assert "leak" not in text
    assert "prompt" not in text
    assert "secret_token" not in text


def test_sanitize_temporal_metadata_removes_private_fields():
    safe = sanitize_temporal_metadata({"prompt": "secret", "nested": {"raw_response": "secret", "ok": True}})

    assert "prompt" not in safe
    assert "raw_response" not in safe["nested"]
    assert safe["nested"]["ok"] is True
    assert temporal_duration_ms(START, FINISH) == 10000
