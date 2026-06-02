from pathlib import Path
import tempfile

from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.tdd_agent_runtime import (
    build_tdd_runtime_gate,
    execute_tdd_controlled_test_run,
)


def assert_tdd_trace(source):
    assert normalize_process_trace_source_kind(source) == "tdd_agent_runtime"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "tdd_agent_runtime"
    assert item["subsystem"] == "ValidationCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_execute_tests"] is False
    assert item["details"]["can_write_tests"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_apply_patch"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_tdd_controlled_test_run_result_process_trace_shows_execution_evidence_without_write_permissions():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-tdd-trace-")).resolve()
    (workspace / "test_green.py").write_text("def test_green():\n    assert True\n", encoding="utf-8")

    result = execute_tdd_controlled_test_run(
        phase="green",
        command="python -m pytest -q test_green.py",
        workspace_path=str(workspace),
        target_test_file="test_green.py",
        regression_coverage=["test_green.py"],
    )
    item = assert_tdd_trace(result)

    assert item["details"]["contract_kind"] == "tdd_controlled_test_run_result"
    assert item["details"]["execution_status"] == "executed"
    assert item["details"]["test_status"] == "passed"
    assert item["details"]["exit_code"] == 0
    assert item["details"]["can_mark_green"] is True


def test_tdd_runtime_gate_process_trace_blocks_missing_red_green_refactor():
    gate = build_tdd_runtime_gate()
    item = assert_tdd_trace(gate)

    assert item["details"]["contract_kind"] == "tdd_runtime_gate"
    assert item["details"]["gate_status"] == "blocked"
    assert item["details"]["can_complete_tdd_cycle"] is False
    assert "red_phase_not_confirmed" in item["details"]["blockers"]
