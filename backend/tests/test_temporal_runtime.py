from backend.apps.swarms.temporal_runtime import (
    apply_session_temporal_update,
    build_duration_aggregation,
    build_retry_backoff_state,
    build_session_title_timestamp_fallback,
    build_temporal_evidence_record,
    build_temporal_log_file_candidate,
    build_temporal_log_policy,
    build_temporal_migration_backfill_plan,
    build_temporal_runtime_trace_source,
    build_timeline_ordering_decision,
    build_timezone_format_policy,
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



def test_log_policy_normalizes_retention_size_and_excludes_chain_of_thought():
    policy = build_temporal_log_policy(retention_count=0, max_log_size_bytes=-1, include_chain_of_thought=True)

    assert policy.retention_count == 10
    assert policy.max_log_size_bytes == 5_000_000
    assert policy.include_chain_of_thought is False
    assert "chain_of_thought_excluded" in policy.warnings


def test_log_filename_candidate_uses_stable_timestamp():
    policy = build_temporal_log_policy(timestamp_format="%Y%m%dT%H%M%SZ", local_path_label="logs")
    candidate = build_temporal_log_file_candidate(timestamp=START, policy=policy, current_size_bytes=10)

    assert candidate.filename == "openswarm-runtime-20260531T100000Z.log"
    assert candidate.local_path_label == "logs"
    assert candidate.should_rotate is False


def test_timeline_ordering_uses_last_message_for_conversation():
    decision = build_timeline_ordering_decision(created_at=START, metadata_updated_at=FINISH, last_message_at=MID, last_activity_at=FINISH)

    assert decision.order_key == "last_message_at"
    assert decision.order_timestamp == MID
    assert decision.reason == "conversation_last_message"


def test_metadata_update_does_not_win_over_last_message_ordering():
    decision = build_timeline_ordering_decision(created_at=START, metadata_updated_at=FINISH, last_message_at=MID)

    assert decision.order_key == "last_message_at"
    assert decision.order_timestamp == MID


def test_timezone_policy_produces_stable_local_label():
    policy = build_timezone_format_policy(timezone="America/Buenos_Aires", locale="es-AR", hour_cycle="24h", timestamp=START)

    assert policy.timezone == "America/Buenos_Aires"
    assert "2026-05-31" in policy.local_time_label
    assert policy.storage_timezone == "UTC"


def test_title_fallback_uses_timestamp_and_fallback_status():
    policy = build_timezone_format_policy(timezone="UTC", timestamp=START)
    fallback = build_session_title_timestamp_fallback(timestamp=START, timezone_policy=policy)

    assert fallback.title_status == "fallback"
    assert "Session 2026-05-31" in fallback.title
    assert fallback.allow_regenerate is True


def test_retry_backoff_calculates_next_retry_and_deadline():
    retry = build_retry_backoff_state(attempt_count=2, first_attempt_at=START, last_attempt_at=MID, base_backoff_ms=1000, max_retry_deadline="2026-05-31T10:01:00Z")

    assert retry.backoff_ms == 2000
    assert retry.next_retry_at == "2026-05-31T10:00:07Z"
    assert retry.should_retry is True
    assert retry.total_retry_duration_ms == 5000


def test_retry_backoff_blocks_after_max_attempts_or_deadline():
    retry = build_retry_backoff_state(attempt_count=3, max_attempts=3, first_attempt_at=START, last_attempt_at=MID)
    deadline = build_retry_backoff_state(attempt_count=1, first_attempt_at=START, last_attempt_at=MID, base_backoff_ms=60000, max_retry_deadline=FINISH)

    assert retry.should_retry is False
    assert retry.blocked_reason == "max_attempts_exceeded"
    assert deadline.should_retry is False
    assert deadline.blocked_reason == "deadline_exceeded"


def test_duration_aggregation_sums_buckets():
    aggregation = build_duration_aggregation([
        {"execution_kind": "model", "duration_ms": 100, "evidence_refs": ["ev1"]},
        {"execution_kind": "tool", "duration_ms": 50, "evidence_refs": ["ev1", "ev2"]},
        {"execution_kind": "script", "duration_ms": 25},
        {"execution_kind": "qa", "duration_ms": 10, "status": "blocked"},
    ], idle_time_ms=5, user_gap_time_ms=7, assistant_gap_time_ms=8)

    assert aggregation.total_agent_run_time_ms == 185
    assert aggregation.model_duration_ms == 100
    assert aggregation.tool_duration_ms == 50
    assert aggregation.command_duration_ms == 25
    assert aggregation.qa_duration_ms == 10
    assert aggregation.idle_time_ms == 5
    assert aggregation.user_gap_time_ms == 7
    assert aggregation.assistant_gap_time_ms == 8
    assert aggregation.longest_blocked_state_ms == 10
    assert aggregation.evidence_refs == ["ev1", "ev2"]


def test_temporal_evidence_marks_stale_for_expiry_or_source_update():
    expired = build_temporal_evidence_record(evidence_id="ev1", produced_at=START, observed_at=START, ingested_at=START, expires_at=MID, now=FINISH)
    source_changed = build_temporal_evidence_record(evidence_id="ev2", source_updated_at=FINISH, validation_at=MID, now=FINISH)

    assert expired.evidence_stale is True
    assert expired.freshness_status == "stale"
    assert source_changed.evidence_stale is True
    assert "revalidate_temporal_evidence" in source_changed.required_actions


def test_migration_backfill_unknown_when_no_source_and_no_precision_invented():
    plan = build_temporal_migration_backfill_plan(target_id="legacy1")

    assert plan.timestamp_status == "unknown"
    assert plan.inferred_created_at is None
    assert plan.confidence == 0.0
    assert plan.migration_source == "unknown"


def test_migration_backfill_infers_from_source_with_confidence():
    plan = build_temporal_migration_backfill_plan(target_id="legacy1", created_at=START, migration_source="message_timestamp")

    assert plan.timestamp_status == "inferred"
    assert plan.inferred_created_at == START
    assert 0 < plan.confidence < 1
    assert plan.stable_order_key.startswith(START)


def test_extended_temporal_runtime_trace_source_redacts_and_includes_sections():
    policy = build_temporal_log_policy(metadata={"secret_token": "leak"})
    ordering = build_timeline_ordering_decision(created_at=START, last_message_at=MID)
    retry = build_retry_backoff_state(attempt_count=3, max_attempts=3, first_attempt_at=START, last_attempt_at=MID)
    source = build_temporal_runtime_trace_source(log_policy=policy, ordering=ordering, retry_backoff=retry, metadata={"prompt": "leak", "trace_id": "tr2"})
    text = str(source).lower()

    assert source["trace_id"] == "tr2"
    assert source["log_policy"]["redaction_enabled"] is True
    assert source["ordering"]["order_key"] == "last_message_at"
    assert source["retry_backoff"]["should_retry"] is False
    assert "leak" not in text
    assert "secret_token" not in text
    assert "prompt" not in text
