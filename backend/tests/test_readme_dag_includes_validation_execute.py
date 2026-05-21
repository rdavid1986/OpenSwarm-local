from backend.apps.agents.orchestration.models import SwarmState
from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.runtime.experimental_task_type_registry import classify_experimental_task


def test_readme_dag_includes_validation_execute_before_consolidation():
    store = SwarmStore()
    swarm = SwarmState(
        id="test-swarm-validation-dag",
        title="Test swarm",
        goal="test",
        user_prompt="test",
    )
    store.save(swarm)

    orchestrator = SwarmOrchestrator(store=store)
    updated = orchestrator.ensure_readme_dag(swarm_id="test-swarm-validation-dag")

    task_types = [classify_experimental_task(task) for task in updated.tasks]
    assert task_types == ["create_readme", "review_readme", "validation_execute", "consolidate_final"]

    validation_task = updated.tasks[2]
    consolidate_task = updated.tasks[3]

    assert validation_task.depends_on == [updated.tasks[1].id]
    assert consolidate_task.depends_on == [validation_task.id]
    assert [contract.role for contract in updated.contracts] == [
        "CoordinatorAgent",
        "DocumentationAgent",
        "ReviewerAgent",
        "TesterAgent",
    ]
