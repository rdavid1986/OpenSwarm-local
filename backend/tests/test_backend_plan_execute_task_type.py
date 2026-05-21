from backend.apps.agents.orchestration.models import TaskNode
from backend.apps.agents.runtime.experimental_task_type_registry import (
    classify_experimental_task,
    get_experimental_task_spec,
)


def test_backend_plan_execute_is_safe_and_classifiable():
    spec = get_experimental_task_spec("backend_plan_execute")

    assert spec.type == "backend_plan_execute"
    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is not None
    assert spec.output_contract == {
        "backend_plan": {
            "status": "ready",
            "summary": "string",
            "services": [],
            "data_models": [],
            "api_endpoints": [],
            "constraints": [],
            "risks": [],
        }
    }

    task = TaskNode(
        id="task-backend-plan",
        title="Execute backend plan",
        description="Generate backend plan from architecture",
        objective="Generate backend plan",
        assigned_agent_id="backend",
        status="pending",
    )

    assert classify_experimental_task(task) == "backend_plan_execute"


def test_backend_plan_draft_remains_non_executable():
    spec = get_experimental_task_spec("backend_plan_draft")

    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
