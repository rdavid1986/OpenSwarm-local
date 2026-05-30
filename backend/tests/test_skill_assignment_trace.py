from backend.apps.swarms.skill_assignment_trace import build_skill_assignment_from_candidates, build_skill_assignment_trace, summarize_skill_assignment_trace


def test_assignment_with_match():
    trace = build_skill_assignment_from_candidates(
        task={"task_id":"t1", "title":"Frontend review", "requirements":["react", "ui"]},
        candidates=[{"skill_id":"s1", "skill_name":"React UI Expert", "tags":["react", "ui"], "source":"candidate"}],
        agent_id="a1",
    )
    assert trace["skill_id"] == "s1"
    assert trace["fallback_used"] is False
    assert trace["match_confidence"] == 1.0
    assert trace["can_activate_tools"] is False
    assert trace["can_activate_mcp"] is False
    assert trace["can_install_skill"] is False


def test_assignment_fallback_without_skill_and_alternatives():
    trace = build_skill_assignment_from_candidates(task={"task_id":"t1", "requirements":["go"]}, candidates=[])
    assert trace["fallback_used"] is True
    assert trace["skill_name"] == "No skill assigned"
    assert trace["risks"] == ["no_matching_skill"]


def test_assignment_summary_and_manual_alternatives():
    trace = build_skill_assignment_trace(skill_id="s1", skill_name="Skill", alternatives_considered=[{"skill_id":"s2"}])
    summary = summarize_skill_assignment_trace(trace)
    assert summary["skill_name"] == "Skill"
    assert trace["alternatives_considered"] == [{"skill_id":"s2"}]
