from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.runtime.experimental_dag_dependency_runner import ExperimentalDAGDependencyRunner


def test_security_review_execute_helper_completes_without_tools():
    task = TaskNode(
        id="task-security-review",
        title="Execute security review",
        description="Generate security review from architecture and plans",
        objective="Generate security review",
        assigned_agent_id="security",
        status="pending",
    )
    swarm = SwarmState(
        id="swarm-security-helper",
        title="Security helper test",
        user_prompt="Generate a security review",
        tasks=[task],
    )

    result = ExperimentalDAGDependencyRunner()._run_security_review_execute_task(
        task=task,
        swarm=swarm,
    )

    assert result["kind"] == "security_review_result"
    assert result["status"] == "ready"
    assert result["security_review"]["status"] == "ready"
    assert task.status == "completed"
    assert task.evidence[-1]["kind"] == "security_review_result"
    assert swarm.tool_history == []
