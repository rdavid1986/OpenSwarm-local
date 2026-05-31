from backend.apps.swarms.miniagent_skill_adaptive import (
    build_adaptive_skill_trace_items,
    build_miniagent_adaptive_skill_state,
    detect_miniagent_skill_gap,
    resolve_swarm_skill_gap_decision,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def test_detects_missing_skill_without_assignment():
    gap = detect_miniagent_skill_gap(
        task={"task_id": "t1", "title": "Build React UI", "domain": "frontend"},
        context_packet={"summary": "Needs UI work", "evidence_refs": ["ctx1"]},
    )

    assert gap["adaptive_kind"] == "miniagent_skill_gap"
    assert gap["has_gap"] is True
    assert gap["gap_type"] == "missing_skill"
    assert gap["severity"] == "blocked"
    assert gap["recommended_resolution"] == "create_skill_candidate"
    assert gap["required_approval"] is True
    assert gap["source"] == "inferred_from_task_state"
    assert gap["evidence_refs"] == ["ctx1"]


def test_detects_reported_missing_current_docs_without_research_execution():
    gap = detect_miniagent_skill_gap(
        assigned_skill_id="skill-react",
        assigned_skill_name="React UI",
        task={"task_id": "t1", "title": "Use latest framework API"},
        blockers=["missing_current_docs for latest API"],
    )

    assert gap["has_gap"] is True
    assert gap["gap_type"] == "missing_current_docs"
    assert gap["recommended_resolution"] == "request_research"
    assert gap["required_approval"] is True
    assert gap["details"]["blocker_count"] == 1


def test_adaptive_state_blocks_resume_while_waiting_for_decision():
    gap = detect_miniagent_skill_gap(task={"task_id": "t1"})
    state = build_miniagent_adaptive_skill_state(
        miniagent_id="mini1",
        task_id="t1",
        skill_gap=gap,
        adaptive_state="waiting_swarm_decision",
        trace_refs=["trace1"],
    )

    assert state["adaptive_kind"] == "miniagent_adaptive_state"
    assert state["adaptive_state"] == "waiting_swarm_decision"
    assert state["approval_required"] is True
    assert state["resume_allowed"] is False
    assert state["trace_refs"] == ["trace1"]


def test_resolution_defers_without_enough_data():
    decision = resolve_swarm_skill_gap_decision(skill_gap={"has_gap": True, "gap_type": "unknown"})

    assert decision["adaptive_kind"] == "swarm_skill_resolution_decision"
    assert decision["decision"] == "defer"
    assert decision["safe_to_resume"] is False
    assert decision["next_state"] in {"waiting_swarm_decision", "blocked"}
    assert decision["safety_gate"]["actions_executed"] == []


def test_resolution_requires_approval_for_research():
    gap = detect_miniagent_skill_gap(
        assigned_skill_id="skill1",
        task={"task_id": "t1"},
        blockers=["missing_current_docs"],
    )
    decision = resolve_swarm_skill_gap_decision(skill_gap=gap, user_approval_state="missing")

    assert decision["decision"] == "request_research"
    assert decision["requires_user_approval"] is True
    assert decision["requires_browser_research"] is True
    assert decision["safe_to_resume"] is False
    assert "approval" in decision["blocked_reason"].lower()
    assert decision["safety_gate"]["browser_research_requires_approval"] is True


def test_resolution_can_prepare_existing_skill_switch_after_approval_not_installing():
    gap = {
        "adaptive_kind": "miniagent_skill_gap",
        "has_gap": True,
        "gap_type": "wrong_domain_skill",
        "recommended_resolution": "switch_skill",
        "task_id": "t1",
    }
    decision = resolve_swarm_skill_gap_decision(
        skill_gap=gap,
        available_skills=[{"skill_id": "react-ui", "skill_name": "React UI", "tags": ["frontend", "react"]}],
        task_context={"task_id": "t1", "title": "Frontend React work", "domain": "frontend"},
        user_approval_state="approved",
    )

    assert decision["decision"] == "switch_skill"
    assert decision["selected_skill_id"] == "react-ui"
    assert decision["safe_to_resume"] is True
    assert decision["safety_gate"]["actions_executed"] == []


def test_trace_items_and_builder_render_adaptive_contracts():
    gap = detect_miniagent_skill_gap(task={"task_id": "t1", "miniagent_id": "mini1"})
    state = build_miniagent_adaptive_skill_state(skill_gap=gap, adaptive_state="waiting_swarm_decision")
    decision = resolve_swarm_skill_gap_decision(skill_gap=gap)

    items = build_adaptive_skill_trace_items(skill_gap=gap, adaptive_state=state, decision=decision)

    assert [item["subsystem"] for item in items] == ["SkillCore", "MiniAgentCore", "ReviewCore"]
    assert items[0]["kind"] == "skill"
    assert items[1]["related_miniagent_id"] == "mini1"
    assert items[2]["metadata"]["adaptive_kind"] == "swarm_skill_resolution_decision"

    builder_item = build_process_trace_item_from_source(gap)
    assert normalize_process_trace_source_kind(gap) == "miniagent_skill_adaptive"
    assert builder_item["subsystem"] == "SkillCore"
    assert builder_item["metadata"]["source_kind"] == "miniagent_skill_adaptive"
