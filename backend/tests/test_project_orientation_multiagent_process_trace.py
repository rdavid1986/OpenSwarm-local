from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
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


def assert_orientation_trace(source):
    assert normalize_process_trace_source_kind(source) == "project_orientation_multiagent"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "project_orientation_multiagent"
    assert item["details"]["can_execute"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_process_trace_recognizes_all_orientation_contracts():
    classification = classify_project_orientation(project_type="app", complexity="low")
    sources = [
        classification,
        select_project_architecture_pattern(classification),
        build_project_agent_blueprint_set(),
        build_project_permission_map(terminal_required=True),
        build_project_memory_context_plan(evidence_refs=["explicit-ref"]),
        build_project_output_validation_plan(),
        build_project_model_provider_plan(),
    ]

    items = [assert_orientation_trace(source) for source in sources]

    assert {item["details"]["source_kind"] for item in items} == {
        "project_orientation_classification",
        "project_orientation_architecture",
        "project_orientation_agent_blueprint",
        "project_orientation_permission_map",
        "project_orientation_memory_context",
        "project_orientation_output_validation",
        "project_orientation_model_provider",
    }
    assert all(item["evidence_refs"] == [] or item["evidence_refs"] == ["explicit-ref"] for item in items)


def test_process_trace_uses_coherent_subsystems():
    classification = classify_project_orientation(project_type="app", complexity="low")
    cases = [
        (classification, "ConfigCore"),
        (select_project_architecture_pattern(classification), "SwarmCore"),
        (build_project_agent_blueprint_set(), "SwarmCore"),
        (build_project_permission_map(), "ConfigCore"),
        (build_project_memory_context_plan(), "ContextCore"),
        (build_project_output_validation_plan(), "ValidationCore"),
        (build_project_model_provider_plan(), "ModelCore"),
    ]

    for source, subsystem in cases:
        item = assert_orientation_trace(source)
        assert item["subsystem"] == subsystem


def test_process_trace_no_secret_or_private_reasoning_leak():
    classification = classify_project_orientation(
        project_type="unknown",
        complexity="unknown",
        metadata={"api_key": "secret-value", "chain_of_thought": "hidden", "safe": "ok"},
    )

    item = assert_orientation_trace(classification)
    rendered = str(item).lower()

    assert item["status"] == "blocked"
    assert "secret-value" not in rendered
    assert "hidden" not in rendered
    assert "chain_of_thought" not in rendered
    assert "api_key" not in rendered


def test_process_trace_permission_map_terminal_gate_details():
    permissions = build_project_permission_map(terminal_required=True)

    item = assert_orientation_trace(permissions)

    assert item["details"]["terminal_required"] is True
    assert item["details"]["safeshell_required"] is True
    assert item["details"]["shell_dialect_required"] is True
    assert item["details"]["policy_matrix_required"] is True
    assert "require_safeshell_gate" in item["details"]["required_actions"]


def test_process_trace_model_provider_keeps_external_provider_blocked():
    plan = build_project_model_provider_plan(openrouter_allowed=True, external_fallback_allowed=True)

    item = assert_orientation_trace(plan)

    assert item["details"]["local_first"] is True
    assert item["details"]["openrouter_allowed"] is True
    assert item["details"]["can_call_external_provider"] is False
    assert item["details"]["can_execute"] is False


def test_process_trace_recognizes_mode_integration_approval_gate():
    classification = classify_project_orientation(project_type="app", complexity="high")
    integration = build_project_orientation_mode_integration(
        mode="app_builder",
        classification=classification,
        architecture=select_project_architecture_pattern(classification),
    )

    item = assert_orientation_trace(integration)

    assert item["details"]["source_kind"] == "project_orientation_multiagent"
    assert item["details"]["contract_kind"] == "project_orientation_mode_integration"
    assert item["details"]["mode"] == "app_builder"
    assert item["details"]["orientation_required"] is True
    assert item["details"]["app_builder_gate"] == "approval_required"
    assert item["details"]["agent_card_receives_blueprint"] is True
    assert item["details"]["swarm_card_shows_process_trace"] is True
    assert item["details"]["can_create_agents"] is False
    assert item["details"]["can_start_app_builder_execution"] is False
    assert item["details"]["can_execute"] is False
