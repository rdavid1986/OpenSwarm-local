from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.runtime.experimental_dag_dependency_runner import ExperimentalDAGDependencyRunner


def test_backend_plan_execute_helper_completes_without_tools():
    task = TaskNode(
        id="task-backend-plan",
        title="Execute backend plan",
        description="Generate backend plan from architecture",
        objective="Generate backend plan",
        assigned_agent_id="backend",
        status="pending",
    )
    swarm = SwarmState(
        id="swarm-backend-helper",
        title="Backend helper test",
        user_prompt="Generate a backend plan",
        tasks=[task],
    )

    result = ExperimentalDAGDependencyRunner()._run_backend_plan_execute_task(
        task=task,
        swarm=swarm,
    )

    assert result["kind"] == "backend_plan_result"
    assert result["status"] == "ready"
    assert result["backend_plan"]["status"] == "ready"
    assert task.status == "completed"
    assert task.evidence[-1]["kind"] == "backend_plan_result"
    assert swarm.tool_history == []
