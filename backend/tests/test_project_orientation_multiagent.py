from backend.apps.swarms.project_orientation_multiagent import (
    build_project_agent_blueprint_set,
    build_project_memory_context_plan,
    build_project_model_provider_plan,
    build_project_output_validation_plan,
    build_project_permission_map,
    build_project_orientation_mode_integration,
    classify_project_orientation,
    select_project_architecture_pattern,
)


def test_classification_no_execute_and_single_agent_low_complexity():
    classification = classify_project_orientation(
        project_type="app",
        complexity="low",
        required_tools=["read"],
        required_outputs=["patch"],
    )

    assert classification.orientation_kind == "project_orientation_classification"
    assert classification.project_type == "app"
    assert classification.single_agent_ok is True
    assert classification.multiagent_required is False
    assert classification.can_execute is False
    assert "do_not_create_agents_yet" in classification.required_actions


def test_classification_marks_multiagent_for_high_complexity_parallel_outputs():
    classification = classify_project_orientation(
        project_type="data_pipeline",
        complexity="high",
        required_tools=["read", "write", "test", "browser"],
        required_outputs=["api", "worker", "tests"],
    )

    assert classification.multiagent_required is True
    assert classification.workflow_required is True
    assert classification.single_agent_ok is False
    assert classification.human_review_required is True


def test_architecture_selector_single_agent_when_multiagent_not_needed():
    classification = classify_project_orientation(project_type="web", complexity="low")

    decision = select_project_architecture_pattern(classification)

    assert decision.selected_pattern == "single_agent"
    assert decision.can_execute is False
    assert "parallel_specialists" in decision.rejected_patterns


def test_architecture_selector_parallel_specialists_for_high_complexity():
    classification = classify_project_orientation(
        project_type="app",
        complexity="high",
        required_outputs=["frontend", "backend", "tests"],
    )

    decision = select_project_architecture_pattern(classification)

    assert decision.selected_pattern == "parallel_specialists"
    assert decision.risk_level == "high"
    assert decision.approval_required is True
    assert decision.can_execute is False


def test_agent_blueprint_keeps_boundaries_and_handoffs_safe():
    blueprints = build_project_agent_blueprint_set(
        roles=[{"role_id": "planner", "responsibilities": ["plan"], "tools_allowed": ["read"]}],
        handoffs=[{"from_role": "planner", "to_role": "implementer", "shared_context": ["plan"]}],
    )

    assert blueprints.can_execute is False
    assert blueprints.roles[0]["role_id"] == "planner"
    assert "no_unapproved_tools" in blueprints.roles[0]["boundaries"]
    assert blueprints.handoffs[0]["private_context_allowed"] is False
    assert "no_private_reasoning_transfer" in blueprints.boundaries


def test_permission_map_requires_policy_matrix_and_blocks_terminal_without_gates():
    permissions = build_project_permission_map(terminal_required=True, file_write_allowed=True)

    assert permissions.policy_matrix_required is True
    assert permissions.terminal_required is True
    assert permissions.safeshell_required is True
    assert permissions.shell_dialect_required is True
    assert permissions.can_execute is False
    assert "require_safeshell_gate" in permissions.required_actions
    assert "require_shell_dialect_gate" in permissions.required_actions
    assert "block_terminal_until_approved" in permissions.required_actions


def test_memory_context_plan_blocks_writes_by_default():
    plan = build_project_memory_context_plan(relevant_docs=["README.md"], metadata={"token": "leak"})

    assert plan.project_instructions_required is True
    assert plan.can_mutate_memory is False
    assert plan.can_execute is False
    assert "raw_prompts" in plan.blocked_memory_writes
    assert plan.metadata["token"] == "[redacted]"


def test_output_validation_plan_requires_evidence_and_completion_gate():
    plan = build_project_output_validation_plan(expected_outputs=["code"], tests_required=["pytest"])

    assert plan.can_write_files is False
    assert plan.can_execute is False
    assert plan.diff_preview_required is True
    assert "tests_or_typecheck" in plan.minimum_evidence
    assert plan.completion_gate == "evidence_and_human_review"


def test_model_provider_plan_is_local_first_and_blocks_external_call():
    plan = build_project_model_provider_plan(
        recommended_local_model="ollama/qwen",
        openrouter_allowed=True,
        external_fallback_allowed=True,
    )

    assert plan.local_first is True
    assert plan.can_call_external_provider is False
    assert plan.can_execute is False
    assert plan.openrouter_allowed is True
    assert "require_external_provider_privacy_budget_approval" in plan.required_actions


def test_mode_integration_blocks_large_app_builder_until_orientation_approved():
    classification = classify_project_orientation(
        project_type="app",
        complexity="high",
        required_outputs=["frontend", "backend", "tests"],
    )
    architecture = select_project_architecture_pattern(classification)

    integration = build_project_orientation_mode_integration(
        mode="app_builder",
        classification=classification,
        architecture=architecture,
    )

    assert integration.integration_kind == "project_orientation_mode_integration"
    assert integration.orientation_required is True
    assert integration.app_builder_gate == "approval_required"
    assert "show_orientation_summary" in integration.required_actions
    assert "block_large_app_builder_execution_until_orientation_approved" in integration.required_actions
    assert integration.agent_card_receives_blueprint is True
    assert integration.swarm_card_shows_process_trace is True
    assert integration.can_create_agents is False
    assert integration.can_start_app_builder_execution is False
    assert integration.can_execute is False


def test_mode_integration_skill_builder_decides_candidate_without_writes():
    classification = classify_project_orientation(project_type="skill", complexity="medium")

    integration = build_project_orientation_mode_integration(
        mode="skill_builder",
        classification=classification,
    )

    assert integration.skill_builder_decision == "create_or_update_skill_candidate"
    assert "decide_create_import_document_or_clarify_skill" in integration.required_actions
    assert integration.can_create_agents is False
    assert integration.can_start_app_builder_execution is False
    assert integration.can_execute is False
