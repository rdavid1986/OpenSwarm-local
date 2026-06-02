from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.tdd_agent_runtime import (
    build_tdd_contract_sequence,
    build_tdd_evidence_report,
    build_tdd_red_phase_contract,
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
    assert item["details"]["can_create_agent"] is False
    assert item["details"]["can_create_miniagent"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_activate_mcp"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_tdd_sequence_process_trace_covers_red_green_refactor_contracts():
    sequence = build_tdd_contract_sequence(
        feature_under_test="TDD trace",
        acceptance_criteria=["trace exists"],
        test_cases=[{"name": "trace exists"}],
        target_test_file="backend/tests/test_tdd_agent_process_trace.py",
        test_name="test_tdd_trace_exists",
        command_to_run="python -m pytest -q backend/tests/test_tdd_agent_process_trace.py",
    )
    items = [assert_tdd_trace(source) for source in sequence]

    assert [item["details"]["contract_kind"] for item in items] == [
        "tdd_agent_manifest_role",
        "tdd_test_list_contract",
        "tdd_red_phase_contract",
        "tdd_green_patch_candidate",
        "tdd_refactor_contract",
        "tdd_evidence_report",
    ]


def test_red_phase_process_trace_requires_dry_run_and_evidence():
    red = build_tdd_red_phase_contract(
        target_test_file="backend/tests/test_example.py",
        test_name="test_red",
        behavior_under_test="expected failure",
        expected_failure_reason="not implemented",
        command_to_run="python -m pytest -q backend/tests/test_example.py",
    )
    item = assert_tdd_trace(red)

    assert item["kind"] == "validation"
    assert item["details"]["dry_run_only"] is True
    assert item["details"]["safeshell_required"] is True
    assert item["details"]["test_runner_required"] is True
    assert item["details"]["command_to_run"] == "python -m pytest -q backend/tests/test_example.py"


def test_evidence_process_trace_does_not_mark_green_without_real_outputs():
    evidence = build_tdd_evidence_report(phase="green", passing_output_ref="", regression_coverage=[])
    item = assert_tdd_trace(evidence)

    assert item["status"] == "warning"
    assert item["details"]["evidence_status"] == "missing"
    assert item["details"]["can_mark_green"] is False
    assert "attach_passing_test_output" in item["details"]["required_actions"]
