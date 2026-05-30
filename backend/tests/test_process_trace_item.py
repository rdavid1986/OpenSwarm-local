from copy import deepcopy

from backend.apps.runtime_timing import finish_runtime_timer, start_runtime_timer
from backend.apps.swarms.process_trace_item import (
    build_process_trace_item,
    build_process_trace_panel,
    append_process_trace_item,
    process_trace_item_from_timeline_event,
    process_trace_item_from_runtime_metric,
    summarize_process_trace_item,
)


def test_build_process_trace_item_shape_and_defaults():
    item = build_process_trace_item(trace_id="t1", kind="context", title="Context", summary="Loaded context")

    assert item["trace_kind"] == "process_trace_item"
    assert item["trace_version"] == "openswarm.process_trace_item.v1"
    assert item["trace_id"] == "t1"
    assert item["kind"] == "context"
    assert item["subsystem"] == "TraceCore"
    assert item["status"] == "planned"
    assert item["visible_to_user"] is True
    assert item["internal_only"] is False
    assert set(("details", "metadata", "evidence_refs", "artifact_refs")).issubset(item)


def test_invalid_kind_and_status_normalize_to_safe_defaults():
    item = build_process_trace_item(kind="bad-kind", status="bad-status")

    assert item["kind"] == "unknown"
    assert item["status"] == "planned"


def test_sensitive_keys_are_removed_from_details_and_metadata():
    item = build_process_trace_item(
        metadata={"api_key": "secret", "safe": "ok", "nested": {"token": "secret", "safe": True}},
        details={"prompt": "full prompt", "chain_of_thought": "private", "count": 1},
    )

    rendered = str(item)
    assert "secret" not in rendered
    assert "full prompt" not in rendered
    assert "private" not in rendered
    assert "api_key" not in item["metadata"]
    assert "token" not in item["metadata"]["nested"]
    assert item["metadata"]["safe"] == "ok"
    assert item["details"] == {"count": 1}


def test_summary_does_not_mutate_input():
    item = build_process_trace_item(trace_id="t1", evidence_refs=["ev1"])
    original = deepcopy(item)

    summary = summarize_process_trace_item(item)

    assert summary["trace_id"] == "t1"
    assert summary["evidence_count"] == 1
    assert item == original


def test_panel_append_does_not_mutate_inputs():
    item = build_process_trace_item(trace_id="t1")
    panel = build_process_trace_panel(panel_title="Trace")
    original_panel = deepcopy(panel)
    original_item = deepcopy(item)

    updated = append_process_trace_item(panel, item)

    assert updated["item_count"] == 1
    assert panel == original_panel
    assert item == original_item


def test_mapping_from_timeline_event():
    event = {
        "event_id": "e1",
        "event_type": "skill_assigned",
        "title": "Skill assigned",
        "summary": "Used test skill",
        "task_id": "task1",
        "agent_id": "agent1",
        "skill_id": "skill1",
        "evidence_refs": ["ev1"],
        "artifact_refs": ["art1"],
        "created_at": "2026-05-30T10:00:00Z",
        "severity": "info",
    }

    item = process_trace_item_from_timeline_event(event)

    assert item["trace_id"] == "e1"
    assert item["kind"] == "skill"
    assert item["status"] == "completed"
    assert item["related_skill_id"] == "skill1"
    assert item["evidence_refs"] == ["ev1"]


def test_mapping_from_runtime_metric():
    timer = finish_runtime_timer(
        start_runtime_timer(scope="tool_call", label="Run tool", started_at="2026-05-30T10:00:00Z", timer_id="timer1"),
        finished_at="2026-05-30T10:00:01Z",
    )

    item = process_trace_item_from_runtime_metric(timer)

    assert item["trace_id"] == "timer1"
    assert item["kind"] == "metric"
    assert item["status"] == "completed"
    assert item["duration_ms"] == 1000
    assert item["details"]["scope"] == "tool_call"
