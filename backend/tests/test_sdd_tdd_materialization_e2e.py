from backend.apps.swarms.action_materialization_runtime import ActionMaterializationPostValidationGate
from backend.apps.swarms.sdd_orchestrator_runtime import SddCompletionGate
from backend.apps.swarms.sdd_tdd_materialization_e2e import (
    build_sdd_tdd_materialization_e2e_gate,
    build_sdd_tdd_materialization_e2e_summary,
)
from backend.apps.swarms.tdd_agent_runtime import TddRuntimeGate


def _sdd_gate():
    return SddCompletionGate(
        candidate_id="candidate-e2e",
        gate_status="completed",
        verification_status="verified",
        evidence_status="sufficient",
        materialization_status="executed",
        drift_status="no_drift",
        completion_conditions={
            "verification_ok": True,
            "evidence_ok": True,
            "materialization_ok": True,
            "drift_ok": True,
        },
        can_mark_completed=True,
    )


def _tdd_gate():
    return TddRuntimeGate(
        gate_status="completed",
        red_confirmed=True,
        green_confirmed=True,
        refactor_confirmed=True,
        evidence_refs=["tdd:trace"],
        can_mark_green=True,
        can_mark_refactor_safe=True,
        can_complete_tdd_cycle=True,
    )


def _materialization_gate():
    return ActionMaterializationPostValidationGate(
        candidate_id="candidate-e2e",
        gate_status="completed",
        execution_status="executed",
        post_validation_status="passed",
        rollback_status="ready",
        rollback_ready=True,
        completion_conditions={
            "execution_ok": True,
            "post_validation_ok": True,
            "rollback_ready": True,
        },
        evidence_refs=["materialization:trace"],
        can_mark_materialization_safe=True,
    )


def test_e2e_gate_blocks_without_sdd_tdd_and_materialization_gates():
    gate = build_sdd_tdd_materialization_e2e_gate(candidate_id="candidate-e2e")

    assert gate.gate_status == "blocked"
    assert gate.can_mark_change_completed is False
    assert "sdd_completion_gate_not_confirmed" in gate.blockers
    assert "tdd_runtime_gate_not_confirmed" in gate.blockers
    assert "materialization_safe_gate_not_confirmed" in gate.blockers


def test_e2e_gate_completes_only_when_sdd_tdd_and_materialization_are_complete():
    gate = build_sdd_tdd_materialization_e2e_gate(
        candidate_id="candidate-e2e",
        sdd_completion_gate=_sdd_gate(),
        tdd_runtime_gate=_tdd_gate(),
        materialization_gate=_materialization_gate(),
        process_trace_refs=["trace:sdd", "trace:tdd", "trace:materialization"],
    )

    assert gate.gate_status == "completed"
    assert gate.can_mark_change_completed is True
    assert gate.blockers == []
    assert gate.completion_conditions["sdd_completion_ok"] is True
    assert gate.completion_conditions["tdd_runtime_ok"] is True
    assert gate.completion_conditions["materialization_safe_ok"] is True
    assert gate.process_trace_refs == ["trace:sdd", "trace:tdd", "trace:materialization"]


def test_e2e_summary_preserves_gate_inputs_without_execution_permissions():
    gate = build_sdd_tdd_materialization_e2e_gate(
        candidate_id="candidate-e2e",
        sdd_completion_gate=_sdd_gate(),
        tdd_runtime_gate=_tdd_gate(),
        materialization_gate=_materialization_gate(),
    )
    summary = build_sdd_tdd_materialization_e2e_summary(
        gate=gate,
        sdd_completion_gate=_sdd_gate(),
        tdd_runtime_gate=_tdd_gate(),
        materialization_gate=_materialization_gate(),
    )

    assert summary.summary_status == "completed"
    assert summary.can_mark_change_completed is True
    assert summary.contains_private_reasoning is False
    assert summary.gate["can_execute"] is False
    assert summary.gate["can_write_files"] is False
    assert summary.gate["can_apply_patch"] is False
