from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.runtime.experimental_dag_dependency_runner import ExperimentalDAGDependencyRunner


def test_frontend_plan_execute_helper_completes_without_tools():
    task = TaskNode(
        id="task-frontend-plan",
        title="Execute frontend plan",
        description="Generate frontend plan from architecture",
        objective="Generate frontend plan",
        assigned_agent_id="frontend",
        status="pending",
    )
    swarm = SwarmState(
        id="swarm-frontend-helper",
        title="Frontend helper test",
        user_prompt="Generate a frontend plan",
        tasks=[task],
    )

    result = ExperimentalDAGDependencyRunner()._run_frontend_plan_execute_task(
        task=task,
        swarm=swarm,
    )

    assert result["kind"] == "frontend_plan_result"
    assert result["status"] == "ready"
    assert result["frontend_plan"]["status"] == "ready"
    assert task.status == "completed"
    assert task.evidence[-1]["kind"] == "frontend_plan_result"
    assert swarm.tool_history == []
