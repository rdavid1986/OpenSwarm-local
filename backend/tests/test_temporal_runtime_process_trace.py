from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.temporal_runtime import (
    build_temporal_context_snapshot,
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
