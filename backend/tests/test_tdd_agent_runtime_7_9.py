from pathlib import Path
import tempfile

from backend.apps.swarms.tdd_agent_runtime import (
    build_tdd_controlled_test_run_request,
    build_tdd_runtime_gate,
    execute_tdd_controlled_test_run,
)


def _workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix="openswarm-tdd-runtime-")).resolve()


def test_tdd_controlled_test_run_request_requires_targeted_pytest_command():
    request = build_tdd_controlled_test_run_request(
        phase="green",
        command="python -m pytest",
        workspace_path=".",
        target_test_file="test_example.py",
    )

    assert request.can_execute_tests is False
    assert "use_targeted_pytest_quiet_command" in request.required_actions


def test_tdd_red_phase_confirms_expected_failure_with_safeshell():
    workspace = _workspace()
    (workspace / "test_red.py").write_text(
        "def test_expected_failure():\n    assert False\n",
        encoding="utf-8",
    )

    result = execute_tdd_controlled_test_run(
        phase="red",
        command="python -m pytest -q test_red.py",
        workspace_path=str(workspace),
        target_test_file="test_red.py",
    )

    assert result.execution_status == "executed"
    assert result.test_status == "failed"
    assert result.exit_code != 0
    assert result.red_confirmed is True
    assert result.can_mark_green is False
    assert "command_executed" in result.evidence_refs


def test_tdd_green_phase_requires_passing_test_and_regression_coverage():
    workspace = _workspace()
    (workspace / "test_green.py").write_text(
        "def test_expected_pass():\n    assert True\n",
        encoding="utf-8",
    )

    result = execute_tdd_controlled_test_run(
        phase="green",
        command="python -m pytest -q test_green.py",
        workspace_path=str(workspace),
        target_test_file="test_green.py",
        regression_coverage=["test_green.py"],
    )

    assert result.execution_status == "executed"
    assert result.test_status == "passed"
    assert result.exit_code == 0
    assert result.green_confirmed is True
    assert result.can_mark_green is True
    assert "command_executed" in result.evidence_refs


def test_tdd_refactor_phase_requires_passing_regression_coverage():
    workspace = _workspace()
    (workspace / "test_refactor.py").write_text(
        "def test_regression():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    result = execute_tdd_controlled_test_run(
        phase="refactor",
        command="python -m pytest -q test_refactor.py",
        workspace_path=str(workspace),
        target_test_file="test_refactor.py",
        regression_coverage=["test_refactor.py"],
    )

    assert result.execution_status == "executed"
    assert result.test_status == "passed"
    assert result.refactor_confirmed is True
    assert result.can_mark_refactor_safe is True


def test_tdd_runtime_gate_blocks_until_all_phases_have_real_evidence():
    gate = build_tdd_runtime_gate()

    assert gate.gate_status == "blocked"
    assert gate.can_complete_tdd_cycle is False
    assert "red_phase_not_confirmed" in gate.blockers
    assert "green_phase_not_confirmed" in gate.blockers
    assert "refactor_phase_not_confirmed" in gate.blockers


def test_tdd_runtime_gate_completes_with_red_green_refactor_evidence():
    workspace = _workspace()
    (workspace / "test_red.py").write_text("def test_red():\n    assert False\n", encoding="utf-8")
    (workspace / "test_green.py").write_text("def test_green():\n    assert True\n", encoding="utf-8")
    (workspace / "test_refactor.py").write_text("def test_refactor():\n    assert True\n", encoding="utf-8")

    red = execute_tdd_controlled_test_run(
        phase="red",
        command="python -m pytest -q test_red.py",
        workspace_path=str(workspace),
        target_test_file="test_red.py",
    )
    green = execute_tdd_controlled_test_run(
        phase="green",
        command="python -m pytest -q test_green.py",
        workspace_path=str(workspace),
        target_test_file="test_green.py",
        regression_coverage=["test_green.py"],
    )
    refactor = execute_tdd_controlled_test_run(
        phase="refactor",
        command="python -m pytest -q test_refactor.py",
        workspace_path=str(workspace),
        target_test_file="test_refactor.py",
        regression_coverage=["test_refactor.py"],
    )

    gate = build_tdd_runtime_gate(red_result=red, green_result=green, refactor_result=refactor)

    assert gate.gate_status == "completed"
    assert gate.can_complete_tdd_cycle is True
    assert gate.can_mark_green is True
    assert gate.can_mark_refactor_safe is True
    assert gate.blockers == []
