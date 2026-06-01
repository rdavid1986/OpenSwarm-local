from backend.apps.swarms.agent_mention_routing import (
    build_agent_mention_loop_guard,
    build_agent_route_candidate,
    decide_agent_mention_route,
    parse_agent_mentions,
    resolve_agent_mentions,
)
from backend.apps.swarms.project_agent_manifest import build_project_agent_manifest


def _manifest():
    return build_project_agent_manifest(
        agents=[
            {
                "agent_id": "frontend",
                "aliases": ["@frontend", "@ui"],
                "role": "FrontendAgent",
                "skills": ["react", "css"],
                "allowed_tools": ["Read", "Edit"],
                "capabilities": ["ui"],
            },
            {
                "agent_id": "tdd",
                "aliases": ["@tdd", "@tester", "@qa"],
                "role": "TesterAgent",
                "skills": ["pytest", "regression"],
                "allowed_tools": ["Read", "Grep"],
                "capabilities": ["tdd", "verification"],
            },
        ],
        source_hash="manifest-hash",
    )


def test_parse_agent_mentions_dedupes_and_normalizes_mentions():
    parsed = parse_agent_mentions("Send this to @frontend and @Frontend, then ask @tdd.")

    assert parsed.has_mentions is True
    assert parsed.normalized_mentions == ["@frontend", "@tdd"]
    assert parsed.can_execute is False
    assert parsed.contains_private_reasoning is False


def test_resolve_agent_mentions_against_project_agent_manifest():
    result = resolve_agent_mentions(message="@ui refine the landing page", manifest=_manifest())

    assert result.decision == "resolved"
    assert result.resolved_agents[0]["agent_id"] == "frontend"
    assert result.resolved_agents[0]["role"] == "FrontendAgent"
    assert result.unresolved_mentions == []
    assert result.can_create_agent is False
    assert result.can_activate_tools is False
    assert "prepare_context_packet_for_target_agent" in result.required_actions


def test_unknown_mention_is_blocked_and_requires_manifest_update():
    decision = decide_agent_mention_route(message="@mobile build the app", manifest=_manifest())

    assert decision.decision == "blocked"
    assert "unresolved_agent_mentions" in decision.blockers
    assert "define_agent_in_project_agent_manifest" in decision.required_actions
    assert decision.can_execute is False
    assert decision.can_create_agent is False


def test_direct_route_candidate_keeps_swarm_trace_and_policy_gates():
    candidate = build_agent_route_candidate(message="@tdd create regression tests", manifest=_manifest())

    assert candidate.target_agent_id == "tdd"
    assert candidate.route_status == "needs_review"
    assert candidate.bypass_full_replanning is True
    assert candidate.keep_swarm_trace is True
    assert candidate.policy_matrix_required is True
    assert candidate.context_packets_required is True
    assert candidate.handoff_required is True
    assert candidate.evidence_required is True
    assert candidate.approval_required is True
    assert candidate.can_execute is False
    assert candidate.can_execute_handoffs is False


def test_loop_guard_blocks_repeated_same_target_routes():
    guard = build_agent_mention_loop_guard(
        source_agent_id="coordinator",
        target_agent_id="frontend",
        recent_route_targets=["frontend", "frontend"],
    )

    assert guard.loop_detected is True
    assert guard.blocked is True
    assert guard.can_execute is False
    assert "review_agent_routing_loop" in guard.required_actions


def test_multiple_mentions_are_ambiguous_until_user_selects_target():
    decision = decide_agent_mention_route(message="@frontend and @tdd review this", manifest=_manifest())

    assert decision.decision == "blocked"
    assert "ambiguous_multiple_agent_mentions" in decision.blockers
    assert "choose_single_target_agent" in decision.required_actions
    assert decision.can_create_miniagent is False
    assert decision.can_write_memory is False
