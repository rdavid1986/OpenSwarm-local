from backend.apps.swarms.action_materialization_runtime import (
    ActionMaterializationPostValidationGate,
    ActionMaterializationPostValidationResult,
    ActionMaterializationRollbackResult,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def assert_action_trace(source):
    assert normalize_process_trace_source_kind(source) == "action_materialization_runtime"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "action_materialization_runtime"
    assert item["subsystem"] == "ActionCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_apply_patch"] is False
    assert item["details"]["can_execute_commands"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_post_validation_result_process_trace_exposes_validation_fields():
    result = ActionMaterializationPostValidationResult(
        candidate_id="candidate-trace",
        validation_status="passed",
        validation_results=[{"tool": "SafeShell", "ok": True}],
        can_mark_validated=True,
    )

    item = assert_action_trace(result)

    assert item["details"]["contract_kind"] == "action_materialization_post_validation_result"
    assert item["details"]["validation_status"] == "passed"
    assert item["details"]["can_mark_validated"] is True


def test_rollback_result_process_trace_exposes_rollback_fields():
    result = ActionMaterializationRollbackResult(
        candidate_id="candidate-trace",
        rollback_status="rolled_back",
        rollback_results=[{"tool": "Write", "ok": True}],
        can_mark_rolled_back=True,
    )

    item = assert_action_trace(result)

    assert item["details"]["contract_kind"] == "action_materialization_rollback_result"
    assert item["details"]["rollback_status"] == "rolled_back"
    assert item["details"]["can_mark_rolled_back"] is True


def test_post_validation_gate_process_trace_exposes_completion_fields():
    gate = ActionMaterializationPostValidationGate(
        candidate_id="candidate-trace",
        gate_status="completed",
        execution_status="executed",
        post_validation_status="passed",
        rollback_status="ready",
        rollback_ready=True,
        completion_conditions={"execution_ok": True, "post_validation_ok": True, "rollback_ready": True},
        can_mark_materialization_safe=True,
    )

    item = assert_action_trace(gate)

    assert item["details"]["contract_kind"] == "action_materialization_post_validation_gate"
    assert item["details"]["post_validation_status"] == "passed"
    assert item["details"]["rollback_ready"] is True
    assert item["details"]["can_mark_materialization_safe"] is True
