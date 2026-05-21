from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.runtime.experimental_dag_dependency_runner import ExperimentalDAGDependencyRunner


def test_architecture_plan_execute_helper_completes_without_tools():
    task = TaskNode(
        id="task-architecture",
        title="Execute architecture plan",
        description="Generate architecture plan from intake",
        objective="Generate architecture plan",
        assigned_agent_id="architect",
        status="pending",
    )
    swarm = SwarmState(
        id="swarm-architecture-helper",
        title="Architecture helper test",
        user_prompt="Generate an architecture plan",
        tasks=[task],
    )

    result = ExperimentalDAGDependencyRunner()._run_architecture_plan_execute_task(
        task=task,
        swarm=swarm,
    )

    assert result["kind"] == "architecture_plan_result"
    assert result["status"] == "ready"
    assert result["architecture_plan"]["status"] == "ready"
    assert task.status == "completed"
    assert task.evidence[-1]["kind"] == "architecture_plan_result"
    assert swarm.tool_history == []
