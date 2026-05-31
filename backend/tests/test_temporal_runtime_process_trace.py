from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.temporal_runtime import (
    build_duration_aggregation,
    build_retry_backoff_state,
    build_temporal_context_snapshot,
    build_temporal_evidence_record,
    build_temporal_log_policy,
    build_temporal_migration_backfill_plan,
    build_temporal_runtime_trace_source,
    build_timeline_ordering_decision,
    build_temporal_execution_state,
    build_temporal_freshness_state,
    build_temporal_trace_source,
)

START = "2026-05-31T10:00:00Z"
FINISH = "2026-05-31T10:00:10Z"


def test_process_trace_recognizes_temporal_runtime():
    execution = build_temporal_execution_state(execution_id="exec1", execution_kind="tool", started_at=START, completed_at=FINISH)
    freshness = build_temporal_freshness_state(created_at=START, last_verified_at=START, ttl_seconds=1, now=FINISH)
    source = build_temporal_trace_source(execution=execution, freshness=freshness, metadata={"trace_id": "trace1"})

    assert normalize_process_trace_source_kind(source) == "temporal_runtime"
    item = build_process_trace_item_from_source(source)

    assert item["trace_id"] == "trace1"
    assert item["kind"] == "metric"
    assert item["subsystem"] == "RuntimeCore"
    assert item["details"]["source_kind"] == "temporal_runtime"
    assert item["details"]["duration_ms"] == 10000
    assert item["details"]["stale_after"] is None
    assert item["details"]["can_execute_model"] is False
    assert item["details"]["can_execute_tools"] is False


def test_temporal_process_trace_redacts_sensitive_fields():
    source = {
        "source_kind": "temporal_runtime",
        "temporal_kind": "temporal_trace_source",
        "trace_id": "trace2",
        "duration_ms": 1,
        "execution": {"execution_id": "exec2", "prompt": "leak", "raw_response": "leak"},
        "context": {"ai_visible_context": {"current_utc": START}, "chain_of_thought": "leak"},
        "metadata": {"secret_token": "leak"},
    }

    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    for forbidden in ("leak", "prompt", "raw_response", "chain_of_thought", "secret_token"):
        assert forbidden not in text


def test_temporal_process_trace_status_reflects_freshness_warning():
    freshness = build_temporal_freshness_state(created_at=START, stale_after=START, now=FINISH)
    context = build_temporal_context_snapshot(freshness=freshness, now=FINISH)
    source = build_temporal_trace_source(freshness=freshness, context=context)
    item = build_process_trace_item_from_source(source)

    assert item["status"] == "blocked"
    assert item["details"]["freshness"]["status"] == "stale"
    assert "refresh_or_verify_context" in item["details"]["required_actions"]



def test_process_trace_includes_extended_temporal_sections():
    log_policy = build_temporal_log_policy(retention_count=3)
    ordering = build_timeline_ordering_decision(created_at=START, last_message_at=FINISH)
    retry = build_retry_backoff_state(attempt_count=3, max_attempts=3, first_attempt_at=START, last_attempt_at=FINISH)
    aggregation = build_duration_aggregation([{"execution_kind": "model", "duration_ms": 10, "evidence_refs": ["ev1"]}])
    evidence = build_temporal_evidence_record(evidence_id="ev1", produced_at=START, expires_at=START, now=FINISH)
    migration = build_temporal_migration_backfill_plan(target_id="legacy", created_at=START, migration_source="fixture")
    source = build_temporal_runtime_trace_source(
        log_policy=log_policy,
        ordering=ordering,
        retry_backoff=retry,
        duration_aggregation=aggregation,
        temporal_evidence=evidence,
        migration_backfill=migration,
        metadata={"trace_id": "extended"},
    )
    item = build_process_trace_item_from_source(source)

    assert normalize_process_trace_source_kind(source) == "temporal_runtime"
    assert item["subsystem"] == "RuntimeCore"
    assert item["details"]["log_policy"]["retention_count"] == 3
    assert item["details"]["ordering"]["order_key"] == "last_message_at"
    assert item["details"]["retry_backoff"]["should_retry"] is False
    assert item["details"]["duration_aggregation"]["model_duration_ms"] == 10
    assert item["details"]["temporal_evidence"]["evidence_stale"] is True
    assert item["details"]["migration_backfill"]["timestamp_status"] == "inferred"
    assert item["details"]["can_execute_model"] is False
    assert item["details"]["can_execute_tools"] is False


def test_extended_temporal_process_trace_redacts_sensitive_sections():
    source = build_temporal_runtime_trace_source(
        log_policy={"redaction_enabled": True, "prompt": "leak"},
        retry_backoff={"metadata": {"raw_response": "leak"}},
        temporal_evidence={"metadata": {"chain_of_thought": "leak"}},
        metadata={"secret_token": "leak", "trace_id": "safe"},
    )
    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    for forbidden in ("leak", "prompt", "raw_response", "chain_of_thought", "secret_token"):
        assert forbidden not in text
