import json
from copy import deepcopy

from backend.apps.swarms.agent_worklog import append_agent_worklog_event, build_agent_worklog_entry, build_empty_agent_worklog, summarize_agent_worklog_entry


def test_worklog_defaults_are_safe_json_and_no_cot():
    entry = build_empty_agent_worklog(swarm_id="s1", chain_of_thought="hidden")
    dumped = json.dumps(entry)
    assert entry["worklog_kind"] == "agent_worklog_entry"
    assert entry["status"] == "planned"
    assert entry["handoff_summary"]
    assert "chain_of_thought" not in dumped


def test_worklog_summary_does_not_mutate():
    entry = build_agent_worklog_entry(task_id="t1", evidence_refs=["ev1"], actions_executed=[{"name":"read"}])
    before = deepcopy(entry)
    summary = summarize_agent_worklog_entry(entry)
    assert summary["evidence_count"] == 1
    assert summary["action_count"] == 1
    assert entry == before


def test_append_event_adds_data_not_execution():
    entry = build_empty_agent_worklog()
    updated = append_agent_worklog_event(entry, {"event_type":"command_planned", "chain_of_thought":"secret"})
    assert len(updated["events"]) == 1
    assert "chain_of_thought" not in json.dumps(updated)
    assert entry["events"] == []
