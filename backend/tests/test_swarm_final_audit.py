from copy import deepcopy
import json

from backend.apps.swarms.agent_handoff import build_miniagent_handoff
from backend.apps.swarms.agent_worklog import build_agent_worklog_entry
from backend.apps.swarms.swarm_final_audit import build_swarm_final_audit, summarize_swarm_final_audit
from backend.apps.swarms.swarm_timeline import build_swarm_timeline, build_swarm_timeline_event


def test_final_audit_complete():
    worklog = build_agent_worklog_entry(task_id="t1", status="completed", evidence_refs=["ev1"], artifacts_created=["art1"])
    handoff = build_miniagent_handoff(evidence_refs=["ev1"])
    timeline = build_swarm_timeline(events=[build_swarm_timeline_event(event_type="swarm_completed", evidence_refs=["ev2"])])
    audit = build_swarm_final_audit(swarm_id="s1", timeline=timeline, worklogs=[worklog], handoffs=[handoff], validation_summary="ok")
    assert audit["final_status"] == "completed"
    assert audit["can_mark_swarm_complete"] is True
    assert audit["evidence_count"] == 2
    assert audit["handoff_count"] == 1


def test_final_audit_with_blockers():
    worklog = build_agent_worklog_entry(task_id="t1", status="blocked", blockers=[{"severity":"critical", "message":"blocked"}])
    audit = build_swarm_final_audit(worklogs=[worklog])
    assert audit["final_status"] == "blocked"
    assert audit["can_mark_swarm_complete"] is False


def test_final_audit_missing_evidence_warning():
    worklog = build_agent_worklog_entry(task_id="t1", status="completed")
    handoff = build_miniagent_handoff()
    audit = build_swarm_final_audit(worklogs=[worklog], handoffs=[handoff])
    assert audit["final_status"] == "completed_with_warnings"
    assert "missing_evidence" in audit["gaps"]


def test_final_audit_summary_no_mutation_no_cot():
    audit = build_swarm_final_audit(worklogs=[build_agent_worklog_entry(status="completed", chain_of_thought="hidden")])
    before = deepcopy(audit)
    summary = summarize_swarm_final_audit(audit)
    assert summary["summary_kind"] == "swarm_final_audit_summary"
    assert audit == before
    assert "chain_of_thought" not in json.dumps(audit)
