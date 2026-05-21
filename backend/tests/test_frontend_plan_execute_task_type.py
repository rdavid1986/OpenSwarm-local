from backend.apps.agents.orchestration.models import TaskNode
from backend.apps.agents.runtime.experimental_task_type_registry import (
    classify_experimental_task,
    get_experimental_task_spec,
)


def test_frontend_plan_execute_is_safe_and_classifiable():
    spec = get_experimental_task_spec("frontend_plan_execute")

    assert spec.type == "frontend_plan_execute"
    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is not None
    assert spec.output_contract == {
        "frontend_plan": {
            "status": "ready",
            "summary": "string",
            "components": [],
            "routes": [],
            "constraints": [],
            "risks": [],
        }
    }

    task = TaskNode(
        id="task-frontend-plan",
        title="Execute frontend plan",
        description="Generate frontend plan from architecture",
        objective="Generate frontend plan",
        assigned_agent_id="frontend",
        status="pending",
    )

    assert classify_experimental_task(task) == "frontend_plan_execute"


def test_frontend_plan_draft_remains_non_executable():
    spec = get_experimental_task_spec("frontend_plan_draft")

    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
