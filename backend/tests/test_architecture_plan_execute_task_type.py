from backend.apps.agents.orchestration.models import TaskNode
from backend.apps.agents.runtime.experimental_task_type_registry import (
    classify_experimental_task,
    get_experimental_task_spec,
)


def test_architecture_plan_execute_is_safe_and_classifiable():
    spec = get_experimental_task_spec("architecture_plan_execute")

    assert spec.type == "architecture_plan_execute"
    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is not None
    assert spec.output_contract == {
        "architecture_plan": {
            "status": "ready",
            "summary": "string",
            "components": [],
            "constraints": [],
            "risks": [],
        }
    }

    task = TaskNode(
        id="task-architecture",
        title="Execute architecture plan",
        description="Generate architecture plan from intake",
        objective="Generate architecture plan",
        assigned_agent_id="architect",
        status="pending",
    )

    assert classify_experimental_task(task) == "architecture_plan_execute"


def test_architecture_plan_draft_remains_non_executable():
    spec = get_experimental_task_spec("architecture_plan_draft")

    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
