import json

from backend.apps.swarms.swarm_timeline import append_swarm_timeline_event, build_swarm_timeline, build_swarm_timeline_event, summarize_swarm_timeline


def test_timeline_events_orderable_and_preserve_evidence():
    e2 = build_swarm_timeline_event(event_type="evidence_added", created_at="2026-01-02T00:00:00Z", evidence_refs=["ev2"])
    e1 = build_swarm_timeline_event(event_type="context_retrieval", created_at="2026-01-01T00:00:00Z", evidence_refs=["ev1"])
    timeline = build_swarm_timeline(swarm_id="s1", events=[e2, e1])
    assert [e["evidence_refs"][0] for e in timeline["events"]] == ["ev1", "ev2"]
    assert summarize_swarm_timeline(timeline)["evidence_count"] == 2


def test_append_timeline_event_and_no_cot():
    timeline = build_swarm_timeline(swarm_id="s1")
    event = build_swarm_timeline_event(event_type="action_executed", chain_of_thought="hidden")
    updated = append_swarm_timeline_event(timeline, event)
    assert len(updated["events"]) == 1
    assert updated["events"][0]["visible_to_user"] is True
    assert updated["events"][0]["internal_only"] is False
    assert "chain_of_thought" not in json.dumps(updated)


def test_timeline_summary_compact():
    timeline = build_swarm_timeline(events=[build_swarm_timeline_event(event_type="blocker_found", severity="warning")])
    summary = summarize_swarm_timeline(timeline)
    assert summary["event_count"] == 1
    assert summary["warning_count"] == 1
