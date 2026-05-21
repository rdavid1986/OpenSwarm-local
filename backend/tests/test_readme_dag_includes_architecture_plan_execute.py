from backend.apps.agents.orchestration.models import SwarmState
from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.runtime.experimental_task_type_registry import classify_experimental_task


def test_readme_dag_includes_architecture_plan_execute_before_readme():
    orchestrator = SwarmOrchestrator()
    swarm = SwarmState(
        id="swarm-architecture-dag",
        title="Architecture DAG test",
        user_prompt="Create a project README",
    )
    orchestrator.store.save(swarm)

    updated = orchestrator.ensure_readme_dag(
        swarm_id=swarm.id,
        generated_plan={
            "summary": "Build a local-first app",
            "app_type": "web app",
            "main_goal": "test goal",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "SQLite",
            "mvp_priority": "README MVP",
            "out_of_scope": "payments",
        },
    )

    task_types = [classify_experimental_task(task) for task in updated.tasks]
    assert task_types == [
        "architecture_plan_execute",
        "frontend_plan_execute",
        "backend_plan_execute",
        "security_review_execute",
        "create_readme",
        "review_readme",
        "validation_execute",
        "consolidate_final",
    ]

    architecture_task = updated.tasks[0]
    frontend_task = updated.tasks[1]
    backend_task = updated.tasks[2]
    security_task = updated.tasks[3]
    write_task = updated.tasks[4]
    review_task = updated.tasks[5]
    validation_task = updated.tasks[6]
    consolidate_task = updated.tasks[7]

    assert frontend_task.depends_on == [architecture_task.id]
    assert backend_task.depends_on == [frontend_task.id]
    assert security_task.depends_on == [backend_task.id]
    assert write_task.depends_on == [security_task.id]
    assert review_task.depends_on == [write_task.id]
    assert validation_task.depends_on == [review_task.id]
    assert consolidate_task.depends_on == [validation_task.id]

    assert [contract.role for contract in updated.contracts] == [
        "CoordinatorAgent",
        "ArchitectAgent",
        "FrontendAgent",
        "BackendAgent",
        "SecurityAgent",
        "DocumentationAgent",
        "ReviewerAgent",
        "TesterAgent",
    ]
