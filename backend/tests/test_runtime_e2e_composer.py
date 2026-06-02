from types import SimpleNamespace

from backend.apps.swarms.runtime_e2e_composer import (
    build_runtime_e2e_composer_selection,
    compose_runtime_e2e_integration_state_from_swarm,
)


def _trace(trace_id: str, source_kind: str, **details):
    return {
        "trace_id": trace_id,
        "metadata": {"source_kind": source_kind},
        "details": {"source_kind": source_kind, **details},
    }


def _complete_sources():
    return [
        _trace(
            "trace:sdd",
            "sdd_orchestrator_runtime",
            contract_kind="sdd_completion_gate",
            candidate_id="candidate-1",
            gate_status="completed",
            can_mark_completed=True,
            evidence_refs=["evidence:sdd"],
        ),
        _trace(
            "trace:tdd",
            "tdd_agent_runtime",
            contract_kind="tdd_runtime_gate",
            candidate_id="candidate-1",
            gate_status="completed",
            can_complete_tdd_cycle=True,
            evidence_refs=["evidence:tdd"],
        ),
        _trace(
            "trace:execution",
            "action_materialization_runtime",
            contract_kind="action_materialization_execution_result",
            candidate_id="candidate-1",
            workspace_path="/tmp/workspace",
            policy_matrix_ref="policy-1",
            approval_id="approval-1",
            execution_status="executed",
            can_mark_executed=True,
            evidence_refs=["evidence:execution"],
        ),
        _trace(
            "trace:validation",
            "action_materialization_runtime",
            contract_kind="action_materialization_post_validation_result",
            candidate_id="candidate-1",
            validation_status="passed",
            can_mark_validated=True,
            evidence_refs=["evidence:validation"],
        ),
        _trace(
            "trace:rollback",
            "action_materialization_runtime",
            contract_kind="action_materialization_rollback_result",
            candidate_id="candidate-1",
            rollback_status="ready",
            evidence_refs=["evidence:rollback"],
        ),
        _trace(
            "trace:materialization-safe",
            "action_materialization_runtime",
            contract_kind="action_materialization_post_validation_gate",
            candidate_id="candidate-1",
            gate_status="completed",
            rollback_ready=True,
            can_mark_materialization_safe=True,
            evidence_refs=["evidence:materialization-safe"],
        ),
        _trace(
            "trace:e2e",
            "sdd_tdd_materialization_e2e",
            contract_kind="sdd_tdd_materialization_e2e_gate",
            candidate_id="candidate-1",
            gate_status="completed",
            can_mark_change_completed=True,
            evidence_refs=["evidence:e2e"],
        ),
    ]


def test_runtime_e2e_composer_builds_completed_state_from_swarm_process_trace_and_approvals():
    swarm = SimpleNamespace(
        id="swarm-1",
        final_result={"workspace_path": "/tmp/workspace"},
        process_trace=_complete_sources(),
        experimental_approvals=[
            {
                "id": "approval-1",
                "status": "allowed",
                "metadata": {
                    "candidate_id": "candidate-1",
                    "policy_matrix_ref": "policy-1",
                },
            }
        ],
    )

    state = compose_runtime_e2e_integration_state_from_swarm(swarm)

    assert state.swarm_id == "swarm-1"
    assert state.candidate_id == "candidate-1"
    assert state.stage == "completed"
    assert state.can_start_runtime_e2e is True
    assert state.can_mark_runtime_e2e_complete is True
    assert state.blockers == []
    assert "trace:sdd" in state.process_trace_refs
    assert "trace:e2e" in state.process_trace_refs


def test_runtime_e2e_composer_selection_exposes_missing_real_swarm_inputs_without_side_effects():
    swarm = SimpleNamespace(id="swarm-2", process_trace=[])

    selection = build_runtime_e2e_composer_selection(swarm)

    assert selection.can_compose_runtime_e2e is False
    assert "missing_candidate_id" in selection.blockers
    assert "missing_sdd_gate" in selection.blockers
    assert "provide_materialization_execution" in selection.required_actions
    assert selection.can_execute is False
    assert selection.can_write_files is False
    assert selection.can_apply_patch is False
    assert selection.can_execute_commands is False
    assert selection.can_activate_tools is False
    assert selection.can_activate_mcp is False
    assert selection.can_write_memory is False


def test_runtime_e2e_composer_can_use_explicit_sources_and_approval_payloads():
    swarm = SimpleNamespace(id="swarm-3", process_trace=[])

    state = compose_runtime_e2e_integration_state_from_swarm(
        swarm,
        process_trace_sources=_complete_sources(),
        approvals=[
            {
                "approval_id": "approval-1",
                "metadata": {
                    "candidate_id": "candidate-1",
                    "policy_matrix_ref": "policy-1",
                },
            }
        ],
    )

    assert state.stage == "completed"
    assert state.completion_conditions["request_has_candidate"] is True
    assert state.completion_conditions["request_has_workspace"] is True
    assert state.completion_conditions["request_has_policy"] is True
    assert state.completion_conditions["request_has_approval"] is True
