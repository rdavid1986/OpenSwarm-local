from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.sdd_orchestrator_runtime import (
    build_sdd_completion_gate,
    build_sdd_spec_drift_report,
)


def assert_sdd_trace(source):
    assert normalize_process_trace_source_kind(source) == "sdd_orchestrator_runtime"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "sdd_orchestrator_runtime"
    assert item["subsystem"] == "SwarmCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_apply_patch"] is False
    assert item["details"]["can_execute_commands"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_spec_drift_report_process_trace_exposes_change_control_fields():
    report = build_sdd_spec_drift_report(
        candidate_id="candidate-trace",
        previous_spec_hash="abc",
        current_spec_hash="def",
        changed_acceptance_criteria=["New acceptance criterion"],
        changed_design_refs=["design:1"],
        affected_files=["backend/apps/example.py"],
    )
    item = assert_sdd_trace(report)

    assert item["status"] == "blocked"
    assert item["details"]["contract_kind"] == "sdd_spec_drift_report"
    assert item["details"]["drift_status"] == "drift_detected"
    assert item["details"]["return_stage"] == "spec_writer"
    assert "spec_drift_detected" in item["details"]["blockers"]


def test_completion_gate_process_trace_blocks_without_required_evidence():
    gate = build_sdd_completion_gate(candidate_id="candidate-gate")
    item = assert_sdd_trace(gate)

    assert item["status"] == "blocked"
    assert item["details"]["contract_kind"] == "sdd_completion_gate"
    assert item["details"]["gate_status"] == "blocked"
    assert item["details"]["can_mark_completed"] is False
    assert "verification_not_confirmed" in item["details"]["blockers"]
    assert "required_evidence" in item["details"]
