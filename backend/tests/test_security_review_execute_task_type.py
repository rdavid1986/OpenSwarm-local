from backend.apps.agents.orchestration.models import TaskNode
from backend.apps.agents.runtime.experimental_task_type_registry import (
    classify_experimental_task,
    get_experimental_task_spec,
)


def test_security_review_execute_is_safe_and_classifiable():
    spec = get_experimental_task_spec("security_review_execute")

    assert spec.type == "security_review_execute"
    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is not None
    assert spec.output_contract == {
        "security_review": {
            "status": "ready",
            "summary": "string",
            "findings": [],
            "constraints": [],
            "risks": [],
        }
    }

    task = TaskNode(
        id="task-security-review",
        title="Execute security review",
        description="Generate security review from architecture and plans",
        objective="Generate security review",
        assigned_agent_id="security",
        status="pending",
    )

    assert classify_experimental_task(task) == "security_review_execute"


def test_security_review_draft_remains_non_executable():
    spec = get_experimental_task_spec("security_review_draft")

    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
