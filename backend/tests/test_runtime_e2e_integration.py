from backend.apps.swarms.action_materialization_runtime import (
    ActionMaterializationExecutionResult,
    ActionMaterializationPostValidationGate,
    ActionMaterializationPostValidationResult,
    ActionMaterializationRollbackResult,
)
from backend.apps.swarms.runtime_e2e_integration import (
    build_runtime_e2e_integration_request,
    build_runtime_e2e_integration_state,
)
from backend.apps.swarms.sdd_orchestrator_runtime import SddCompletionGate
from backend.apps.swarms.sdd_tdd_materialization_e2e import SddTddMaterializationE2EGate
from backend.apps.swarms.tdd_agent_runtime import TddRuntimeGate


def test_runtime_e2e_request_blocks_without_runtime_identifiers():
    request = build_runtime_e2e_integration_request()

    assert request.can_execute is False
    assert "attach_candidate_id" in request.required_actions
    assert "attach_workspace_path" in request.required_actions
    assert "attach_policy_matrix_ref" in request.required_actions
    assert "attach_approval_id" in request.required_actions


def test_runtime_e2e_state_blocks_until_all_gates_are_complete():
    request = build_runtime_e2e_integration_request(
        candidate_id="candidate-1",
        workspace_path="/tmp/workspace",
        policy_matrix_ref="policy-1",
        approval_id="approval-1",
    )
    state = build_runtime_e2e_integration_state(request=request)

    assert state.can_start_runtime_e2e is True
    assert state.can_mark_runtime_e2e_complete is False
    assert state.stage == "blocked"
    assert "sdd_gate_not_completed" in state.blockers
    assert "tdd_gate_not_completed" in state.blockers
    assert "materialization_execution_not_confirmed" in state.blockers


def test_runtime_e2e_state_completes_when_sdd_tdd_materialization_validation_rollback_and_e2e_are_complete():
    request = build_runtime_e2e_integration_request(
        swarm_id="swarm-1",
        agent_id="agent-1",
        candidate_id="candidate-1",
        workspace_path="/tmp/workspace",
        policy_matrix_ref="policy-1",
        approval_id="approval-1",
    )

    state = build_runtime_e2e_integration_state(
        request=request,
        sdd_gate=SddCompletionGate(candidate_id="candidate-1", gate_status="completed", can_mark_completed=True),
        tdd_gate=TddRuntimeGate(gate_status="completed", can_complete_tdd_cycle=True),
        materialization_execution=ActionMaterializationExecutionResult(candidate_id="candidate-1", execution_status="executed", evidence_refs=["exec"], can_mark_executed=True),
        post_validation=ActionMaterializationPostValidationResult(candidate_id="candidate-1", validation_status="passed", evidence_refs=["validation"], can_mark_validated=True),
        rollback=ActionMaterializationRollbackResult(candidate_id="candidate-1", rollback_status="ready", evidence_refs=["rollback"]),
        materialization_gate=ActionMaterializationPostValidationGate(candidate_id="candidate-1", gate_status="completed", rollback_ready=True, evidence_refs=["mat-gate"], can_mark_materialization_safe=True),
        e2e_gate=SddTddMaterializationE2EGate(candidate_id="candidate-1", gate_status="completed", evidence_refs=["e2e"], can_mark_change_completed=True),
        process_trace_refs=["trace:sdd", "trace:tdd", "trace:mat"],
    )

    assert state.stage == "completed"
    assert state.can_mark_runtime_e2e_complete is True
    assert state.blockers == []
    assert state.evidence_refs == ["exec", "validation", "rollback", "mat-gate", "e2e"]
    assert state.process_trace_refs == ["trace:sdd", "trace:tdd", "trace:mat"]
