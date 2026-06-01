from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.sdd_orchestrator_runtime import (
    build_sdd_contract_sequence,
    build_sdd_policy_review_contract,
    build_sdd_role_manifest,
)


def assert_sdd_trace(source):
    assert normalize_process_trace_source_kind(source) == "sdd_orchestrator_runtime"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "sdd_orchestrator_runtime"
    assert item["subsystem"] == "SwarmCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_create_agent"] is False
    assert item["details"]["can_create_miniagent"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_execute_handoffs"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_sdd_role_manifest_process_trace_is_visible_and_safe():
    manifest = build_sdd_role_manifest()
    item = assert_sdd_trace(manifest)

    assert item["details"]["contract_kind"] == "sdd_role_manifest"
    assert "explorer" in item["details"]["role_order"]
    assert item["details"]["policy_matrix_required"] is True


def test_sdd_sequence_process_trace_covers_contracts_without_execution():
    sequence = build_sdd_contract_sequence(
        objective="Add SDD contracts",
        files_considered=["backend/apps/swarms/sdd_orchestrator_runtime.py"],
        requirements=["Contracts exist"],
        acceptance_criteria=["ProcessTrace exists"],
        task_nodes=[{"task_id": "trace"}],
    )
    items = [assert_sdd_trace(source) for source in sequence]

    assert [item["details"]["contract_kind"] for item in items] == [
        "sdd_role_manifest",
        "sdd_explorer_context",
        "sdd_proposal",
        "sdd_spec_contract",
        "sdd_design_contract",
        "sdd_task_dag_contract",
        "sdd_policy_review_contract",
        "sdd_test_strategy_contract",
    ]


def test_sdd_policy_trace_blocks_unsafe_actions_without_private_reasoning():
    policy = build_sdd_policy_review_contract(
        risk_level="critical",
        blocked_actions=["activate_mcp_without_approval"],
    )
    item = assert_sdd_trace(policy)

    assert item["status"] == "blocked"
    assert item["details"]["risk_level"] == "critical"
    assert "activate_mcp_without_approval" in item["details"]["blocked_actions"]
