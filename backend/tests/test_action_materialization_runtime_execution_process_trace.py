from pathlib import Path

from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.swarms.action_materialization_runtime import (
    build_action_materialization_evidence_plan,
    build_action_materialization_policy_gate,
    build_action_materialization_request,
    build_action_rollback_plan,
    build_command_materialization_plan,
    build_patch_materialization_plan,
    decide_action_materialization,
    execute_action_materialization_runtime,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def test_action_materialization_execution_result_trace_is_inert_even_after_real_tool_runtime(tmp_path: Path, monkeypatch):
    import backend.apps.agents.orchestration.store as store_module

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = SwarmStore(root=tmp_path / "swarms")
    monkeypatch.setattr(store_module, "swarm_store", store)
    task = TaskNode(id="task-1", title="Materialize", objective="Materialize.")
    swarm = SwarmState(id="swarm-1", title="Swarm", user_prompt="test", tasks=[task])
    swarm.experimental_approvals = [
        {
            "id": "approval-1",
            "status": "allowed",
            "tool_name": "Write",
            "tool_input": {"path": "created.py", "content": "x = 1\n"},
            "workspace_path": str(workspace),
            "swarm_id": "swarm-1",
            "agent_id": "agent-1",
            "task_id": "task-1",
        }
    ]
    store.save(swarm)

    request = build_action_materialization_request(
        candidate_id="candidate-trace",
        requested_operations=[{"path": "created.py", "operation": "write", "content": "x = 1\n"}],
        approval_id="approval-1",
    )
    gate = build_action_materialization_policy_gate(request, approval_id="approval-1", policy_matrix_ref="policy-1")
    decision = decide_action_materialization(
        request=request,
        policy_gate=gate,
        patch_plan=build_patch_materialization_plan(request, workspace_id="workspace"),
        command_plan=build_command_materialization_plan(request, cwd="."),
        evidence_plan=build_action_materialization_evidence_plan(request, validation_commands=["python -m py_compile created.py"]),
        rollback_plan=build_action_rollback_plan(request),
    )
    result = execute_action_materialization_runtime(
        decision,
        workspace_path=str(workspace),
        approval_id="approval-1",
        policy_matrix_ref="policy-1",
        swarm_id="swarm-1",
        agent_id="agent-1",
        task_id="task-1",
    )

    assert normalize_process_trace_source_kind(result) == "action_materialization_runtime"
    item = build_process_trace_item_from_source(result)
    assert item["details"]["contract_kind"] == "action_materialization_execution_result"
    assert item["details"]["execution_status"] == "executed"
    assert item["details"]["can_mark_executed"] is True
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_apply_patch"] is False
    assert item["details"]["can_execute_commands"] is False
    assert item["details"]["contains_private_reasoning"] is False
