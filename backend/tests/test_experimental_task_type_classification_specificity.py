from backend.apps.agents.orchestration.models import TaskNode
from backend.apps.agents.runtime.experimental_task_type_registry import classify_experimental_task


def test_architecture_plan_is_not_misclassified_as_plan_reused():
    task = TaskNode(
        title="Execute architecture plan",
        objective=(
            "Generate an architecture plan from the project intake before creating artifacts. "
            "Use the intake context: Initial task request. App type: app."
        ),
    )

    assert classify_experimental_task(task) == "architecture_plan_execute"


def test_plan_reused_requires_exact_plan_task_dag_title():
    task = TaskNode(
        title="Plan task DAG",
        objective="Create or reuse a minimal plan for the requested work.",
    )

    assert classify_experimental_task(task) == "plan_reused"
