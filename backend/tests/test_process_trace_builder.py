from copy import deepcopy

from backend.apps.runtime_timing import finish_runtime_timer, start_runtime_timer
from backend.apps.swarms.agent_handoff import build_miniagent_handoff
from backend.apps.swarms.agent_worklog import build_agent_worklog_entry
from backend.apps.swarms.context_retrieval_display import build_context_retrieval_display_item, build_context_retrieval_panel
from backend.apps.swarms.miniagent_task_metrics import build_miniagent_task_runtime_metric
from backend.apps.swarms.process_trace_builder import (
    build_process_trace_item_from_source,
    build_process_trace_items_from_sources,
    build_process_trace_panel_from_sources,
    normalize_process_trace_source_kind,
    redact_process_trace_source,
)
from backend.apps.swarms.skill_assignment_trace import build_skill_assignment_trace
from backend.apps.swarms.swarm_final_audit import build_swarm_final_audit
from backend.apps.swarms.swarm_timeline import build_swarm_timeline_event


START = "2026-05-30T10:00:00Z"
FINISH = "2026-05-30T10:00:01Z"


def test_builder_from_timeline_event():
    event = build_swarm_timeline_event(event_id="event1", event_type="evidence_added", title="Evidence", summary="Evidence added")

    item = build_process_trace_item_from_source(event)

    assert item["trace_id"] == "event1"
    assert item["kind"] == "evidence"
    assert item["subsystem"] == "EvidenceCore"
    assert item["metadata"]["source_kind"] == "timeline_event"


def test_builder_from_agent_worklog():
    worklog = build_agent_worklog_entry(
        task_id="task1",
        agent_id="agent1",
        miniagent_id="mini1",
        task_title="Implement tests",
        assigned_skill_id="skill1",
        status="completed",
        evidence_refs=["ev1"],
        actions_executed=["act"],
    )

    item = build_process_trace_item_from_source(worklog)

    assert item["kind"] == "worklog"
    assert item["related_task_id"] == "task1"
    assert item["related_agent_id"] == "agent1"
    assert item["related_skill_id"] == "skill1"
    assert item["details"]["action_count"] == 1


def test_builder_from_context_retrieval_item_and_panel():
    context_item = build_context_retrieval_display_item(retrieval_id="ctx1", title="Memory", summary="Relevant memory", evidence_ref="ev1")
    panel = build_context_retrieval_panel([context_item])

    item_trace = build_process_trace_item_from_source(context_item)
    panel_trace = build_process_trace_item_from_source(panel)

    assert item_trace["trace_id"] == "ctx1"
    assert item_trace["kind"] == "context"
    assert item_trace["evidence_refs"] == ["ev1"]
    assert panel_trace["kind"] == "context"
    assert panel_trace["details"]["item_count"] == 1


def test_builder_from_skill_assignment_trace():
    trace = build_skill_assignment_trace(task_id="task1", agent_id="agent1", skill_id="skill1", skill_name="Testing", match_confidence=0.8)

    item = build_process_trace_item_from_source(trace)

    assert item["kind"] == "skill"
    assert item["subsystem"] == "SkillCore"
    assert item["related_skill_id"] == "skill1"
    assert item["details"]["match_confidence"] == 0.8


def test_builder_from_handoff():
    handoff = build_miniagent_handoff(source_agent_id="a1", target_agent_id="a2", source_task_id="t1", target_task_id="t2", evidence_refs=["ev1"])

    item = build_process_trace_item_from_source(handoff)

    assert item["kind"] == "handoff"
    assert item["subsystem"] == "HandoffCore"
    assert item["related_task_id"] == "t2"
    assert item["evidence_refs"] == ["ev1"]


def test_builder_from_final_audit():
    audit = build_swarm_final_audit(swarm_id="swarm1", worklogs=[build_agent_worklog_entry(task_id="t1", status="completed")], validation_summary="Validated")

    item = build_process_trace_item_from_source(audit)

    assert item["kind"] == "review"
    assert item["subsystem"] == "ReviewCore"
    assert item["summary"] == "Validated"
    assert item["details"]["completed_count"] == 1


def test_builder_from_miniagent_task_runtime_metric():
    metric = build_miniagent_task_runtime_metric(metric_id="metric1", task_id="task1", agent_id="agent1", miniagent_id="mini1", status="completed", started_at=START, finished_at=FINISH)

    item = build_process_trace_item_from_source(metric)

    assert item["trace_id"] == "metric1"
    assert item["kind"] == "metric"
    assert item["subsystem"] == "MetricCore"
    assert item["related_miniagent_id"] == "mini1"


def test_builder_from_runtime_timer_record_and_dict():
    timer = finish_runtime_timer(start_runtime_timer(scope="model_call", label="Model", timer_id="timer1", started_at=START), finished_at=FINISH)
    timer_dict = {**timer.__dict__, "timer_id": "timer2"}

    item_from_record = build_process_trace_item_from_source(timer)
    item_from_dict = build_process_trace_item_from_source(timer_dict)

    assert item_from_record["trace_id"] == "timer1"
    assert item_from_record["duration_ms"] == 1000
    assert item_from_dict["trace_id"] == "timer2"
    assert normalize_process_trace_source_kind(timer) == "runtime_timer"


def test_redaction_of_sensitive_fields():
    source = {
        "event_id": "e1",
        "event_type": "context_retrieval",
        "title": "Safe",
        "summary": "Safe summary",
        "prompt": "full private prompt",
        "metadata": {"api_key": "secret", "safe": "ok"},
        "chain_of_thought": "private reasoning",
    }

    redacted = redact_process_trace_source(source)
    item = build_process_trace_item_from_source(source)
    rendered = str(item)

    assert "full private prompt" not in str(redacted)
    assert "secret" not in str(redacted)
    assert "private reasoning" not in str(redacted)
    assert "full private prompt" not in rendered
    assert "secret" not in rendered
    assert "private reasoning" not in rendered


def test_panel_from_mixed_sources_preserves_order_and_does_not_mutate_inputs():
    event = build_swarm_timeline_event(event_id="event1", event_type="context_retrieval")
    skill = build_skill_assignment_trace(skill_id="skill1")
    sources = [event, skill]
    original = deepcopy(sources)

    items = build_process_trace_items_from_sources(sources)
    panel = build_process_trace_panel_from_sources(sources)

    assert [item["metadata"]["source_kind"] for item in items] == ["timeline_event", "skill_assignment_trace"]
    assert [item["metadata"]["source_kind"] for item in panel["items"]] == ["timeline_event", "skill_assignment_trace"]
    assert panel["item_count"] == 2
    assert sources == original


def test_builder_from_generic_evidence_dict():
    source = {"evidence_id": "ev1", "artifact_id": "art1", "title": "Evidence", "task_id": "task1"}

    item = build_process_trace_item_from_source(source)

    assert item["kind"] == "evidence"
    assert item["evidence_refs"] == ["ev1"]
    assert item["artifact_refs"] == ["art1"]
    assert item["related_task_id"] == "task1"
