from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.sdd_tdd_materialization_e2e import (
    SddTddMaterializationE2EGate,
    SddTddMaterializationE2ESummary,
)


def assert_e2e_trace(source):
    assert normalize_process_trace_source_kind(source) == "sdd_tdd_materialization_e2e"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "sdd_tdd_materialization_e2e"
    assert item["subsystem"] == "ValidationCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_apply_patch"] is False
    assert item["details"]["can_execute_commands"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_activate_mcp"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_e2e_gate_process_trace_exposes_completion_fields():
    gate = SddTddMaterializationE2EGate(
        candidate_id="candidate-trace",
        gate_status="completed",
        sdd_status="completed",
        tdd_status="completed",
        materialization_status="completed",
        completion_conditions={
            "sdd_completion_ok": True,
            "tdd_runtime_ok": True,
            "materialization_safe_ok": True,
        },
        process_trace_refs=["trace:sdd", "trace:tdd", "trace:materialization"],
        can_mark_change_completed=True,
    )

    item = assert_e2e_trace(gate)

    assert item["details"]["contract_kind"] == "sdd_tdd_materialization_e2e_gate"
    assert item["details"]["gate_status"] == "completed"
    assert item["details"]["can_mark_change_completed"] is True
    assert item["details"]["process_trace_refs"] == ["trace:sdd", "trace:tdd", "trace:materialization"]


def test_e2e_summary_process_trace_exposes_summary_fields():
    summary = SddTddMaterializationE2ESummary(
        candidate_id="candidate-trace",
        summary_status="blocked",
        blockers=["sdd_completion_gate_not_confirmed"],
    )

    item = assert_e2e_trace(summary)

    assert item["details"]["contract_kind"] == "sdd_tdd_materialization_e2e_summary"
    assert item["status"] == "blocked"
    assert "sdd_completion_gate_not_confirmed" in item["details"]["blockers"]
