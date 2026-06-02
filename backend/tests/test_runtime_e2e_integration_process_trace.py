from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.runtime_e2e_integration import (
    build_runtime_e2e_integration_request,
    build_runtime_e2e_integration_state,
)


def assert_runtime_e2e_trace(source):
    assert normalize_process_trace_source_kind(source) == "runtime_e2e_integration"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "runtime_e2e_integration"
    assert item["subsystem"] == "RuntimeCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_apply_patch"] is False
    assert item["details"]["can_execute_commands"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_activate_mcp"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_runtime_e2e_request_process_trace_exposes_request_fields():
    request = build_runtime_e2e_integration_request(
        swarm_id="swarm-1",
        agent_id="agent-1",
        candidate_id="candidate-1",
        workspace_path="/tmp/workspace",
        policy_matrix_ref="policy-1",
        approval_id="approval-1",
    )

    item = assert_runtime_e2e_trace(request)

    assert item["details"]["contract_kind"] == "runtime_e2e_integration_request"
    assert item["details"]["candidate_id"] == "candidate-1"
    assert item["details"]["policy_matrix_ref"] == "policy-1"
    assert item["details"]["approval_id"] == "approval-1"


def test_runtime_e2e_state_process_trace_exposes_gate_fields():
    request = build_runtime_e2e_integration_request(candidate_id="candidate-1")
    state = build_runtime_e2e_integration_state(request=request)

    item = assert_runtime_e2e_trace(state)

    assert item["details"]["contract_kind"] == "runtime_e2e_integration_state"
    assert item["details"]["stage"] == "blocked"
    assert "sdd_gate_not_completed" in item["details"]["blockers"]
    assert item["details"]["can_mark_runtime_e2e_complete"] is False
