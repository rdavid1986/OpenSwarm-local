from backend.apps.swarms.import_compatibility_runtime import (
    build_import_compatibility_report,
    detect_import_source,
    evaluate_import_policy_bridge,
    normalize_import_candidate,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source


def assert_agent_import_inert(value):
    assert value.can_execute is False
    assert getattr(value, "can_install", False) is False
    assert getattr(value, "can_activate_mcp", False) is False
    assert getattr(value, "can_create_agent", False) is False
    assert getattr(value, "can_write_memory", False) is False


def test_agent_spec_candidate_records_blueprint_without_materializing_agent():
    envelope = normalize_import_candidate({
        "source_format": "agent",
        "name": "Planner Agent",
        "source_author": "team",
        "source_license": "MIT",
        "source_uri": "file://agents/planner.json",
        "source_hash": "hash",
        "agent_spec": {"name": "Planner Agent", "role": "PlannerAgent", "instructions": "Plan tasks only."},
        "required_tools": ["Read", "Grep"],
        "handoffs": [{"from_role": "PlannerAgent", "to_role": "BackendAgent"}],
        "memory": ["project_instructions"],
        "stop_conditions": ["validation_failed", "approval_required"],
    })

    candidate = envelope.normalized_candidate
    decision = evaluate_import_policy_bridge(envelope, build_import_compatibility_report(envelope))

    assert envelope.normalized_type == "AgentSpecCandidate"
    assert candidate["agent_blueprint"]["name"] == "Planner Agent"
    assert candidate["agent_blueprint"]["can_create_agent"] is False
    assert candidate["tool_mapping"]["can_activate_tools"] is False
    assert candidate["memory_mapping"]["can_write_memory"] is False
    assert candidate["handoff_mapping"]["can_execute_handoffs"] is False
    assert candidate["agent_review_plan"]["approval_required_before_materialization"] is True
    assert "review_agent_spec_candidate" in decision.required_actions
    assert "confirm_no_agent_materialization" in decision.required_actions
    assert_agent_import_inert(envelope)
    assert_agent_import_inert(decision)


def test_subagent_blueprint_candidate_from_crewai_like_manifest_is_inert():
    detection = detect_import_source({
        "raw_text": "CrewAI specialist subagent role: BackendAgent goal: implement APIs",
    })
    envelope = normalize_import_candidate({
        "source_format": "subagent",
        "name": "Backend Specialist",
        "subagents": [
            {"name": "Backend Specialist", "role": "BackendAgent", "goal": "Implement APIs", "tools": ["Read", "Edit"]}
        ],
    }, detection=detection)

    candidate = envelope.normalized_candidate
    decision = evaluate_import_policy_bridge(envelope)

    assert envelope.normalized_type == "SubagentBlueprintCandidate"
    assert len(candidate["subagent_blueprints"]) == 1
    assert candidate["subagent_blueprints"][0]["can_create_agent"] is False
    assert candidate["subagent_blueprints"][0]["can_activate_tools"] is False
    assert candidate["subagent_blueprints"][0]["can_execute_handoffs"] is False
    assert candidate["subagent_blueprints"][0]["can_write_memory"] is False
    assert "review_subagent_blueprint_candidate" in decision.required_actions
    assert "confirm_no_miniagent_materialization" in decision.required_actions
    assert_agent_import_inert(envelope)
    assert_agent_import_inert(decision)


def test_agent_import_policy_requires_review_for_tools_memory_handoffs_and_stop_conditions():
    envelope = normalize_import_candidate({
        "source_format": "agent",
        "name": "Unsafe Planner",
        "tools": ["Bash"],
        "handoffs": [{"from_role": "PlannerAgent", "to_role": "ExecutorAgent"}],
        "memory": ["write project memory"],
    })
    report = build_import_compatibility_report(envelope)
    decision = evaluate_import_policy_bridge(envelope, report)

    assert decision.decision == "needs_review"
    assert decision.risk_level == "high"
    assert "review_agent_tool_mapping" in report.required_actions
    assert "review_agent_memory_mapping" in report.required_actions
    assert "define_agent_stop_conditions" in report.required_actions
    assert "review_agent_tool_memory_handoff_mapping" in decision.required_actions
    assert decision.memory_write_gate_required is False
    assert_agent_import_inert(envelope)
    assert_agent_import_inert(decision)


def test_agent_import_process_trace_includes_blueprints_and_mappings_without_private_reasoning():
    envelope = normalize_import_candidate({
        "source_format": "agent",
        "name": "Coordinator",
        "agent_spec": {"role": "CoordinatorAgent"},
        "required_tools": ["Read"],
        "handoffs": [{"from_role": "CoordinatorAgent", "to_role": "TesterAgent"}],
        "memory": ["project_instructions"],
    })
    item = build_process_trace_item_from_source(envelope)

    assert item["subsystem"] == "SwarmCore"
    assert item["details"]["can_create_agent"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    assert item["details"]["agent_blueprint"]["can_create_agent"] is False
    assert item["details"]["handoff_mapping"]["can_execute_handoffs"] is False
    assert item["details"]["tool_mapping"]["can_activate_tools"] is False
    assert item["details"]["memory_mapping"]["can_write_memory"] is False
    assert item["details"]["agent_review_plan"]["can_create_agent"] is False
