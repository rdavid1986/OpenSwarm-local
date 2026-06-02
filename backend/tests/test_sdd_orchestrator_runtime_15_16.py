from backend.apps.swarms.sdd_orchestrator_runtime import (
    build_sdd_completion_gate,
    build_sdd_evidence_trace,
    build_sdd_runtime_15_16_sequence,
    build_sdd_spec_drift_report,
    build_sdd_verification_report,
)


def assert_inert(contract):
    assert contract.can_execute is False
    assert getattr(contract, "can_write_files", False) is False
    assert getattr(contract, "can_apply_patch", False) is False
    assert getattr(contract, "can_execute_commands", False) is False
    assert getattr(contract, "contains_private_reasoning", False) is False


def test_spec_drift_report_blocks_when_hashes_are_missing():
    report = build_sdd_spec_drift_report(candidate_id="candidate-1")

    assert report.drift_status == "unknown"
    assert "missing_spec_hash" in report.blockers
    assert report.can_continue_without_spec_update is False
    assert_inert(report)


def test_spec_drift_report_detects_changed_requirements_and_returns_to_spec_writer():
    report = build_sdd_spec_drift_report(
        candidate_id="candidate-2",
        previous_spec_hash="abc",
        current_spec_hash="def",
        changed_requirements=["New login requirement"],
        affected_files=["backend/apps/example.py"],
    )

    assert report.drift_status == "drift_detected"
    assert report.drift_severity == "high"
    assert report.return_stage == "spec_writer"
    assert "spec_drift_detected" in report.blockers
    assert_inert(report)


def test_spec_drift_report_allows_continue_when_hashes_match_and_no_changes():
    report = build_sdd_spec_drift_report(
        candidate_id="candidate-3",
        previous_spec_hash="abc",
        current_spec_hash="abc",
    )

    assert report.drift_status == "no_drift"
    assert report.change_control_decision == "continue"
    assert report.can_continue_without_spec_update is True
    assert report.blockers == []
    assert_inert(report)


def test_completion_gate_blocks_without_verified_report_evidence_materialization_and_drift_clearance():
    gate = build_sdd_completion_gate(candidate_id="candidate-4")

    assert gate.gate_status == "blocked"
    assert gate.can_mark_completed is False
    assert "verification_not_confirmed" in gate.blockers
    assert "evidence_insufficient" in gate.blockers
    assert "materialization_not_confirmed" in gate.blockers
    assert "spec_drift_not_cleared" in gate.blockers
    assert_inert(gate)


def test_completion_gate_can_mark_completed_only_when_all_conditions_are_real():
    verification = build_sdd_verification_report(
        candidate_id="candidate-5",
        spec_compliance="passed",
        acceptance_result="passed",
        test_results=[{"command": "pytest", "status": "passed"}],
        regression_result="passed",
        design_compliance="passed",
        evidence_quality="sufficient",
    )
    evidence = build_sdd_evidence_trace(
        candidate_id="candidate-5",
        evidence_refs=["evidence:1"],
        validation_refs=["validation:1"],
        materialization_refs=["materialization:1"],
        process_trace_refs=["trace:1"],
        changed_files=["backend/apps/example.py"],
    )
    drift = build_sdd_spec_drift_report(
        candidate_id="candidate-5",
        previous_spec_hash="abc",
        current_spec_hash="abc",
    )
    materialization = {"decision": "executed"}

    gate = build_sdd_completion_gate(
        candidate_id="candidate-5",
        verification_report=verification,
        evidence_trace=evidence,
        materialization_decision=materialization,
        drift_report=drift,
    )

    assert gate.gate_status == "completed"
    assert gate.can_mark_completed is True
    assert gate.blockers == []
    assert gate.completion_conditions["verification_ok"] is True
    assert gate.completion_conditions["evidence_ok"] is True
    assert gate.completion_conditions["materialization_ok"] is True
    assert gate.completion_conditions["drift_ok"] is True
    assert_inert(gate)


def test_runtime_15_16_sequence_order_is_correct_and_inert():
    sequence = build_sdd_runtime_15_16_sequence(
        candidate_id="candidate-6",
        previous_spec_hash="same",
        current_spec_hash="same",
    )

    assert [item.sdd_contract_kind for item in sequence] == [
        "sdd_spec_drift_report",
        "sdd_completion_gate",
    ]
    for item in sequence:
        assert_inert(item)
