import json
from copy import deepcopy

from backend.apps.swarms.agent_handoff import build_handoff_context_for_next_agent, build_miniagent_handoff, merge_handoffs_for_agent, summarize_miniagent_handoff


def test_handoff_preserves_evidence_and_no_cot():
    handoff = build_miniagent_handoff(source_agent_id="a1", target_agent_id="a2", evidence_refs=["ev1"], decisions=[{"summary":"kept", "chain_of_thought":"hidden"}])
    assert handoff["evidence_refs"] == ["ev1"]
    assert "chain_of_thought" not in json.dumps(handoff)


def test_next_agent_context_contains_summary_evidence_decisions_blockers():
    handoff = build_miniagent_handoff(target_agent_id="a2", completed_work_summary="Done", evidence_refs=["ev1"], decisions=["D"], blockers=["B"])
    ctx = build_handoff_context_for_next_agent([handoff], "a2")
    assert ctx["summaries"] == ["Done"]
    assert ctx["evidence_refs"] == ["ev1"]
    assert ctx["decisions"] == ["D"]
    assert ctx["blockers"] == ["B"]


def test_merge_preserves_order_and_does_not_mutate_inputs():
    h1 = build_miniagent_handoff(source_agent_id="a1", target_agent_id="a3")
    h2 = build_miniagent_handoff(source_agent_id="a2", target_agent_id="a3")
    items = [h1, h2]
    before = deepcopy(items)
    merged = merge_handoffs_for_agent(items, "a3")
    assert [h["source_agent_id"] for h in merged] == ["a1", "a2"]
    assert items == before
    assert summarize_miniagent_handoff(h1)["evidence_count"] == 0
