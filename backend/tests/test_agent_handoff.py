import json
from copy import deepcopy

from backend.apps.swarms.agent_handoff import (
    attach_handoff_context_to_metadata,
    build_blocked_handoff_state,
    build_handoff_context_for_next_agent,
    build_handoff_context_section,
    build_handoff_timeline_events,
    build_miniagent_handoff,
    merge_handoffs_for_agent,
    persist_miniagent_handoff_state,
    summarize_miniagent_handoff,
    validate_miniagent_handoff,
)


def test_handoff_preserves_evidence_and_no_cot():
    handoff = build_miniagent_handoff(
        source_agent_id="a1",
        target_agent_id="a2",
        evidence_refs=["ev1"],
        decisions=[{"summary": "kept", "chain_of_thought": "hidden"}],
        metadata={"raw_prompt": "hidden", "safe": "ok"},
    )

    text = json.dumps(handoff)

    assert handoff["evidence_refs"] == ["ev1"]
    assert handoff["status"] == "ready"
    assert handoff["contains_private_reasoning"] is False
    assert "chain_of_thought" not in text
    assert "raw_prompt" not in text
    assert "hidden" not in text
    assert handoff["metadata"]["safe"] == "ok"


def test_next_agent_context_contains_summary_evidence_decisions_blockers():
    handoff = build_miniagent_handoff(
        target_agent_id="a2",
        completed_work_summary="Done",
        evidence_refs=["ev1"],
        decisions=["D"],
        blockers=["B"],
        recommended_next_steps=["continue"],
    )

    ctx = build_handoff_context_for_next_agent([handoff], "a2")

    assert ctx["status"] == "blocked"
    assert ctx["summaries"] == ["Done"]
    assert ctx["evidence_refs"] == ["ev1"]
    assert ctx["decisions"] == ["D"]
    assert ctx["blockers"] == ["B"]
    assert ctx["can_inject_into_next_agent"] is False


def test_merge_preserves_order_dedupes_and_does_not_mutate_inputs():
    h1 = build_miniagent_handoff(handoff_id="h1", source_agent_id="a1", target_agent_id="a3")
    h2 = build_miniagent_handoff(handoff_id="h2", source_agent_id="a2", target_agent_id="a3")
    items = [h1, h2, h1]
    before = deepcopy(items)

    merged = merge_handoffs_for_agent(items, "a3")

    assert [h["source_agent_id"] for h in merged] == ["a1", "a2"]
    assert items == before
    assert summarize_miniagent_handoff(h1)["evidence_count"] == 0


def test_validate_handoff_blocks_missing_required_fields():
    handoff = build_miniagent_handoff(target_agent_id="", completed_work_summary="", evidence_refs=[])

    validation = validate_miniagent_handoff(handoff, require_evidence=True)

    assert validation["status"] == "blocked"
    assert validation["valid"] is False
    assert "target_agent_or_task" in validation["missing_fields"]
    assert "completed_work_summary" in validation["missing_fields"]
    assert "evidence_refs" in validation["missing_fields"]


def test_validate_handoff_accepts_complete_handoff():
    handoff = build_miniagent_handoff(
        source_agent_id="a1",
        target_agent_id="a2",
        completed_work_summary="Done",
        evidence_refs=["ev1"],
        recommended_next_steps=["review"],
    )

    validation = validate_miniagent_handoff(handoff, require_evidence=True)

    assert validation["status"] == "valid"
    assert validation["valid"] is True
    assert validation["can_continue_without_review"] is True


def test_blocked_handoff_state_is_explicit_and_safe():
    handoff = build_miniagent_handoff(handoff_id="h1", target_agent_id="a2", blockers=["missing API contract"])
    validation = validate_miniagent_handoff(handoff)

    blocked = build_blocked_handoff_state(handoff, validation)

    assert blocked["status"] == "blocked"
    assert blocked["handoff_id"] == "h1"
    assert blocked["can_continue"] is False
    assert "resolve_or_acknowledge_handoff_blockers" in blocked["required_actions"]


def test_persist_handoff_state_is_side_effect_free_and_replaces_existing():
    state = {"handoffs": [build_miniagent_handoff(handoff_id="h1", completed_work_summary="old")]}
    before = deepcopy(state)
    handoff = build_miniagent_handoff(handoff_id="h1", completed_work_summary="new")

    updated = persist_miniagent_handoff_state(state, handoff)

    assert state == before
    assert updated["handoff_store_kind"] == "openswarm.miniagent_handoff_store.v1"
    assert updated["handoff_count"] == 1
    assert updated["handoffs"][0]["completed_work_summary"] == "new"


def test_handoff_context_section_is_state_context_compatible():
    handoff = build_miniagent_handoff(
        handoff_id="h1",
        target_agent_id="a2",
        completed_work_summary="Done",
        evidence_refs=["ev1"],
        decisions=[{"summary": "Use SQLite"}],
        recommended_next_steps=["validate"],
    )
    ctx = build_handoff_context_for_next_agent([handoff], "a2")

    section = build_handoff_context_section(ctx)

    assert section["kind"] == "miniagent_handoff_context"
    assert section["source"] == "HandoffCore"
    assert "Done" in section["content"]
    assert section["metadata"]["injection_authorizes_actions"] is False
    assert section["metadata"]["evidence_refs"] == ["ev1"]


def test_handoff_timeline_events_created_received_used():
    handoff = build_miniagent_handoff(
        handoff_id="h1",
        source_agent_id="a1",
        target_agent_id="a2",
        source_task_id="t1",
        target_task_id="t2",
        evidence_refs=["ev1"],
    )

    events = build_handoff_timeline_events(handoff)

    assert [event["event_type"] for event in events] == ["handoff_created", "handoff_received", "handoff_used"]
    assert all(event["handoff_id"] == "h1" for event in events)
    assert events[0]["evidence_refs"] == ["ev1"]
    assert events[1]["agent_id"] == "a2"


def test_attach_handoff_context_to_metadata_does_not_mutate_original():
    context = build_handoff_context_for_next_agent([build_miniagent_handoff(handoff_id="h1", target_agent_id="a2")], "a2")
    original = {"existing": True}

    attached = attach_handoff_context_to_metadata(original, context)

    assert original == {"existing": True}
    assert attached["existing"] is True
    assert attached["handoff_context"]["handoff_ids"] == ["h1"]
