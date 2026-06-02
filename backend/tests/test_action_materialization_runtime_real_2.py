from pathlib import Path

from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.swarms.action_materialization_runtime import (
    build_action_materialization_evidence_plan,
    build_action_materialization_policy_gate,
    build_action_materialization_post_validation_gate,
    build_action_materialization_post_validation_request,
    build_action_materialization_request,
    build_action_materialization_rollback_request,
    build_action_rollback_plan,
    build_command_materialization_plan,
    build_patch_materialization_plan,
    decide_action_materialization,
    execute_action_materialization_post_validation,
    execute_action_materialization_rollback_runtime,
    execute_action_materialization_runtime,
)


def _store_with_approvals(tmp_path: Path, monkeypatch, workspace: Path, approvals: list[dict]):
    import backend.apps.agents.orchestration.store as store_module

    store = SwarmStore(root=tmp_path / "swarms")
    monkeypatch.setattr(store_module, "swarm_store", store)
    task = TaskNode(id="task-1", title="Materialize", objective="Materialize approved action.")
    swarm = SwarmState(id="swarm-1", title="Materialization swarm", user_prompt="test", tasks=[task])
    swarm.experimental_approvals = [
        {
            "status": "allowed",
            "workspace_path": str(workspace),
            "swarm_id": "swarm-1",
            "agent_id": "agent-1",
            "task_id": "task-1",
            **approval,
        }
        for approval in approvals
    ]
    store.save(swarm)
    return swarm


def _decision(operation: dict | None = None, command: str | None = None):
    request = build_action_materialization_request(
        candidate_id="candidate-real-2",
        source_contract_kind="unit_test",
        requested_operations=[operation] if operation else [],
        requested_commands=[command] if command else [],
        approval_id="approval-write",
    )
    gate = build_action_materialization_policy_gate(request, approval_id="approval-write", policy_matrix_ref="policy-1")
    return decide_action_materialization(
        request=request,
        policy_gate=gate,
        patch_plan=build_patch_materialization_plan(request, workspace_id="workspace"),
        command_plan=build_command_materialization_plan(request, cwd="."),
        evidence_plan=build_action_materialization_evidence_plan(request, validation_commands=["python -m py_compile created.py"]),
        rollback_plan=build_action_rollback_plan(request),
    )


def _execute_write(tmp_path: Path, monkeypatch, workspace: Path):
    _store_with_approvals(
        tmp_path,
        monkeypatch,
        workspace,
        [
            {"id": "approval-write", "tool_name": "Write", "tool_input": {"path": "created.py", "content": "x = 1\n"}},
            {"id": "approval-validate", "tool_name": "SafeShell", "tool_input": {"command": "python -m py_compile created.py"}},
            {"id": "approval-rollback", "tool_name": "Write", "tool_input": {"path": "created.py", "content": "x = 0\n"}},
        ],
    )
    decision = _decision(operation={"path": "created.py", "operation": "write", "content": "x = 1\n"})
    return execute_action_materialization_runtime(
        decision,
        workspace_path=str(workspace),
        approval_id="approval-write",
        policy_matrix_ref="policy-1",
        swarm_id="swarm-1",
        agent_id="agent-1",
        task_id="task-1",
    )


def test_post_validation_request_blocks_without_execution_and_approval():
    request = build_action_materialization_post_validation_request(
        {"candidate_id": "candidate-real-2"},
        validation_commands=[],
    )

    assert request.can_execute is False
    assert "execute_materialization_before_post_validation" in request.required_actions
    assert "attach_approved_runtime_approval_id" in request.required_actions
    assert "define_post_validation_commands" in request.required_actions


def test_post_validation_executes_approved_safeshell_after_materialization(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    execution = _execute_write(tmp_path, monkeypatch, workspace)

    result = execute_action_materialization_post_validation(
        execution,
        validation_commands=["python -m py_compile created.py"],
        workspace_path=str(workspace),
        approval_id="approval-validate",
        policy_matrix_ref="policy-1",
        swarm_id="swarm-1",
        agent_id="agent-1",
        task_id="task-1",
    )

    assert result.validation_status == "passed"
    assert result.can_mark_validated is True
    assert result.validation_results[0]["tool"] == "SafeShell"
    assert result.validation_results[0]["ok"] is True


def test_rollback_request_requires_explicit_rollback_operations_or_commands():
    request = build_action_materialization_rollback_request(
        {"candidate_id": "candidate-real-2", "rollback_plan": {}},
        workspace_path=".",
        approval_id="approval-rollback",
        policy_matrix_ref="policy-1",
    )

    assert request.can_execute is False
    assert "define_rollback_operations_or_commands" in request.required_actions


def test_controlled_rollback_executes_approved_write_restore(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    execution = _execute_write(tmp_path, monkeypatch, workspace)

    result = execute_action_materialization_rollback_runtime(
        execution,
        rollback_operations=[{"path": "created.py", "operation": "write", "content": "x = 0\n"}],
        workspace_path=str(workspace),
        approval_id="approval-rollback",
        policy_matrix_ref="policy-1",
        swarm_id="swarm-1",
        agent_id="agent-1",
        task_id="task-1",
    )

    assert result.rollback_status == "rolled_back"
    assert result.can_mark_rolled_back is True
    assert (workspace / "created.py").read_text(encoding="utf-8") == "x = 0\n"


def test_post_validation_gate_blocks_until_execution_validation_and_rollback_are_ready(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    execution = _execute_write(tmp_path, monkeypatch, workspace)

    gate = build_action_materialization_post_validation_gate(
        execution_result=execution,
        post_validation_result=None,
        rollback_request=None,
        rollback_required=True,
    )

    assert gate.gate_status == "blocked"
    assert gate.can_mark_materialization_safe is False
    assert "post_validation_not_confirmed" in gate.blockers


def test_post_validation_gate_completes_with_execution_validation_and_rollback_plan(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    execution = _execute_write(tmp_path, monkeypatch, workspace)
    validation = execute_action_materialization_post_validation(
        execution,
        validation_commands=["python -m py_compile created.py"],
        workspace_path=str(workspace),
        approval_id="approval-validate",
        policy_matrix_ref="policy-1",
        swarm_id="swarm-1",
        agent_id="agent-1",
        task_id="task-1",
    )
    rollback_request = build_action_materialization_rollback_request(
        execution,
        rollback_operations=[{"path": "created.py", "operation": "write", "content": "x = 0\n"}],
        workspace_path=str(workspace),
        approval_id="approval-rollback",
        policy_matrix_ref="policy-1",
    )

    gate = build_action_materialization_post_validation_gate(
        execution_result=execution,
        post_validation_result=validation,
        rollback_request=rollback_request,
        rollback_required=True,
    )

    assert gate.gate_status == "completed"
    assert gate.can_mark_materialization_safe is True
    assert gate.completion_conditions["execution_ok"] is True
    assert gate.completion_conditions["post_validation_ok"] is True
    assert gate.completion_conditions["rollback_ready"] is True
