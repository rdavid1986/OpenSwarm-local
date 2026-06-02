from pathlib import Path

from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.swarms.action_materialization_runtime import (
    build_action_materialization_evidence_plan,
    build_action_materialization_policy_gate,
    build_action_materialization_request,
    build_command_materialization_plan,
    build_patch_materialization_plan,
    build_action_rollback_plan,
    build_action_materialization_execution_request,
    decide_action_materialization,
    execute_action_materialization_runtime,
)


def _approved_swarm(tmp_path: Path, monkeypatch, *, tool_name: str, tool_input: dict, workspace: Path, approval_id: str = "approval-1"):
    import backend.apps.agents.orchestration.store as store_module

    store = SwarmStore(root=tmp_path / "swarms")
    monkeypatch.setattr(store_module, "swarm_store", store)
    task = TaskNode(id="task-1", title="Materialize", objective="Materialize approved action.")
    swarm = SwarmState(id="swarm-1", title="Materialization swarm", user_prompt="test", tasks=[task])
    swarm.experimental_approvals = [
        {
            "id": approval_id,
            "status": "allowed",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "workspace_path": str(workspace),
            "swarm_id": "swarm-1",
            "agent_id": "agent-1",
            "task_id": "task-1",
        }
    ]
    store.save(swarm)
    return swarm


def _decision(*, operation: dict | None = None, command: str | None = None):
    request = build_action_materialization_request(
        candidate_id="candidate-1",
        source_contract_kind="unit_test",
        requested_operations=[operation] if operation else [],
        requested_commands=[command] if command else [],
        approval_id="approval-1",
    )
    gate = build_action_materialization_policy_gate(request, approval_id="approval-1", policy_matrix_ref="policy-1")
    patch = build_patch_materialization_plan(request, workspace_id="workspace")
    command_plan = build_command_materialization_plan(request, cwd=".")
    evidence = build_action_materialization_evidence_plan(request, validation_commands=["python -m py_compile created.py"])
    rollback = build_action_rollback_plan(request)
    return decide_action_materialization(
        request=request,
        policy_gate=gate,
        patch_plan=patch,
        command_plan=command_plan,
        evidence_plan=evidence,
        rollback_plan=rollback,
    )


def test_execution_request_blocks_without_approval_and_policy():
    decision = _decision(operation={"path": "created.py", "operation": "write", "content": "x = 1\n"})
    request = build_action_materialization_execution_request(decision, workspace_path=".")

    assert request.can_execute is False
    assert "attach_approved_runtime_approval_id" in request.required_actions
    assert "attach_policy_matrix_decision" in request.required_actions


def test_action_materialization_executes_approved_write_and_persists_evidence(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool_input = {"path": "created.py", "content": "x = 1\n"}
    _approved_swarm(tmp_path, monkeypatch, tool_name="Write", tool_input=tool_input, workspace=workspace)
    decision = _decision(operation={"path": "created.py", "operation": "write", "content": "x = 1\n"})

    result = execute_action_materialization_runtime(
        decision,
        workspace_path=str(workspace),
        approval_id="approval-1",
        policy_matrix_ref="policy-1",
        swarm_id="swarm-1",
        agent_id="agent-1",
        task_id="task-1",
    )

    assert result.execution_status == "executed"
    assert result.can_mark_executed is True
    assert result.changed_files == ["created.py"]
    assert (workspace / "created.py").read_text(encoding="utf-8") == "x = 1\n"
    assert result.tool_results[0]["tool"] == "Write"
    assert result.tool_results[0]["ok"] is True


def test_action_materialization_blocks_write_when_approval_input_mismatches(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _approved_swarm(tmp_path, monkeypatch, tool_name="Write", tool_input={"path": "other.py", "content": "x"}, workspace=workspace)
    decision = _decision(operation={"path": "created.py", "operation": "write", "content": "x = 1\n"})

    result = execute_action_materialization_runtime(
        decision,
        workspace_path=str(workspace),
        approval_id="approval-1",
        policy_matrix_ref="policy-1",
        swarm_id="swarm-1",
        agent_id="agent-1",
        task_id="task-1",
    )

    assert result.execution_status == "blocked"
    assert result.can_mark_executed is False
    assert "write_failed_or_not_approved" in result.blockers
    assert not (workspace / "created.py").exists()


def test_action_materialization_executes_approved_safeshell_command(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "ok.py").write_text("x = 1\n", encoding="utf-8")
    tool_input = {"command": "python -m py_compile ok.py"}
    _approved_swarm(tmp_path, monkeypatch, tool_name="SafeShell", tool_input=tool_input, workspace=workspace)
    decision = _decision(command="python -m py_compile ok.py")

    result = execute_action_materialization_runtime(
        decision,
        workspace_path=str(workspace),
        approval_id="approval-1",
        policy_matrix_ref="policy-1",
        swarm_id="swarm-1",
        agent_id="agent-1",
        task_id="task-1",
    )

    assert result.execution_status == "executed"
    assert result.can_mark_executed is True
    assert result.command_outputs[0]["exit_code"] == 0
