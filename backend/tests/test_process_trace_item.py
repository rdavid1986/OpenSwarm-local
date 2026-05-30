from copy import deepcopy

from backend.apps.runtime_timing import finish_runtime_timer, start_runtime_timer
from backend.apps.swarms.process_trace_item import (
    build_process_trace_item,
    build_process_trace_panel,
    build_process_trace_turn_container,
    build_humanized_reasoning_trace_item,
    append_process_trace_turn_item,
    summarize_process_trace_turn_container,
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


def test_build_process_trace_turn_container_shape_and_defaults():
    item = build_process_trace_item(trace_id="reasoning1", kind="summary", title="Reasoning summary")

    container = build_process_trace_turn_container(
        items=[item],
        turn_trace_id="turn1",
        title="Thought",
        status="completed",
        message_id="msg1",
        output_message_id="assistant1",
        duration_ms=1234,
        related_agent_ids=["agent1"],
    )

    assert container["turn_trace_kind"] == "process_trace_turn_container"
    assert container["turn_trace_version"] == "openswarm.process_trace_turn_container.v1"
    assert container["turn_trace_id"] == "turn1"
    assert container["title"] == "Thought"
    assert container["status"] == "completed"
    assert container["message_id"] == "msg1"
    assert container["output_message_id"] == "assistant1"
    assert container["duration_ms"] == 1234
    assert container["item_count"] == 1
    assert container["child_trace_ids"] == ["reasoning1"]
    assert container["default_collapsed_after_finish"] is True
    assert container["default_expanded_while_running"] is False
    assert container["visible_to_user"] is True
    assert container["internal_only"] is False


def test_process_trace_turn_container_redacts_sensitive_metadata():
    container = build_process_trace_turn_container(
        metadata={"safe": "ok", "prompt": "hidden prompt", "nested": {"api_key": "secret", "safe": True}},
        items=[build_process_trace_item(details={"chain_of_thought": "private", "count": 1})],
    )

    rendered = str(container)
    assert "hidden prompt" not in rendered
    assert "secret" not in rendered
    assert "private" not in rendered
    assert container["metadata"] == {"safe": "ok", "nested": {"safe": True}}
    assert container["items"][0]["details"] == {"count": 1}


def test_append_process_trace_turn_item_does_not_mutate_inputs():
    container = build_process_trace_turn_container(turn_trace_id="turn1")
    item = build_process_trace_item(trace_id="tool1", kind="tool")
    original_container = deepcopy(container)
    original_item = deepcopy(item)

    updated = append_process_trace_turn_item(container, item)

    assert updated["item_count"] == 1
    assert updated["child_trace_ids"] == ["tool1"]
    assert container == original_container
    assert item == original_item


def test_summarize_process_trace_turn_container_does_not_mutate_input():
    item = build_process_trace_item(trace_id="model1", kind="model")
    container = build_process_trace_turn_container(
        turn_trace_id="turn1",
        items=[item],
        evidence_refs=["ev1"],
        artifact_refs=["art1"],
    )
    original = deepcopy(container)

    summary = summarize_process_trace_turn_container(container)

    assert summary["summary_kind"] == "process_trace_turn_container_summary"
    assert summary["turn_trace_id"] == "turn1"
    assert summary["item_count"] == 1
    assert summary["child_trace_count"] == 1
    assert summary["evidence_count"] == 1
    assert summary["artifact_count"] == 1
    assert container == original


def test_humanized_reasoning_trace_item_contract():
    item = build_humanized_reasoning_trace_item(
        trace_id="reasoning1",
        summary="The agent identified this as a greeting and prepared a short response.",
        source="operational_summary",
        requested_level="high",
        applied_level="low",
        provider="ollama",
        model="qwen3.6:latest",
        capability_supported=True,
        duration_ms=250,
        related_agent_id="agent1",
        output_message_id="assistant1",
    )

    assert item["trace_id"] == "reasoning1"
    assert item["kind"] == "reasoning"
    assert item["subsystem"] == "ReasoningCore"
    assert item["icon_id"] == "reasoning-core"
    assert item["title"] == "Reasoning summary"
    assert item["summary"] == "The agent identified this as a greeting and prepared a short response."
    assert item["badge"] == "operational_summary"
    assert item["duration_ms"] == 250
    assert item["related_agent_id"] == "agent1"
    assert item["metadata"]["summary_source"] == "operational_summary"
    assert item["metadata"]["requested_reasoning_level"] == "high"
    assert item["metadata"]["applied_reasoning_level"] == "low"
    assert item["metadata"]["provider"] == "ollama"
    assert item["metadata"]["model"] == "qwen3.6:latest"
    assert item["metadata"]["output_message_id"] == "assistant1"
    assert item["details"]["capability_supported"] is True


def test_humanized_reasoning_trace_item_redacts_private_reasoning():
    item = build_humanized_reasoning_trace_item(
        summary="Safe public summary.",
        source="bad-source",
        requested_level="extreme",
        applied_level="medium",
        metadata={
            "chain_of_thought": "private",
            "safe": "ok",
            "nested": {"prompt": "hidden", "safe": True},
        },
    )

    rendered = str(item)
    assert item["badge"] == "fallback"
    assert item["metadata"]["summary_source"] == "fallback"
    assert item["metadata"]["requested_reasoning_level"] == "auto"
    assert item["metadata"]["applied_reasoning_level"] == "medium"
    assert "private" not in rendered
    assert "hidden" not in rendered
    assert item["metadata"]["safe"] == "ok"
    assert item["metadata"]["nested"] == {"safe": True}


def test_reasoning_and_debug_kinds_are_allowed():
    reasoning = build_process_trace_item(kind="reasoning")
    thinking = build_process_trace_item(kind="thinking")
    debug = build_process_trace_item(kind="debug")

    assert reasoning["kind"] == "reasoning"
    assert thinking["kind"] == "thinking"
    assert debug["kind"] == "debug"
