from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore


def test_create_swarm_builds_specialized_initial_dag_without_name_error():
    orchestrator = SwarmOrchestrator(store=SwarmStore())

    swarm = orchestrator.create_swarm(
        user_prompt="crea un app tutorial de openswarm",
        dashboard_id="debug-dashboard",
    )

    assert swarm.intent == "task"
    assert [contract.role for contract in swarm.contracts] == [
        "CoordinatorAgent",
        "PlannerAgent",
        "ArchitectAgent",
        "FrontendAgent",
        "BackendAgent",
        "SecurityAgent",
        "DocumentationAgent",
        "ReviewerAgent",
        "TesterAgent",
    ]
    assert [task.title for task in swarm.tasks] == [
        "Plan task DAG",
        "Execute architecture plan",
        "Execute frontend plan",
        "Execute backend plan",
        "Execute security review",
        "Create README.md",
        "Review README.md",
        "Execute safe validation checks",
        "Consolidate final evidence",
    ]

    tasks_by_title = {task.title: task for task in swarm.tasks}
    assert tasks_by_title["Execute architecture plan"].depends_on == [tasks_by_title["Plan task DAG"].id]
    assert tasks_by_title["Execute frontend plan"].depends_on == [tasks_by_title["Execute architecture plan"].id]
    assert tasks_by_title["Execute backend plan"].depends_on == [tasks_by_title["Execute frontend plan"].id]
    assert tasks_by_title["Execute security review"].depends_on == [tasks_by_title["Execute backend plan"].id]
    assert tasks_by_title["Create README.md"].depends_on == [tasks_by_title["Execute security review"].id]
    assert tasks_by_title["Review README.md"].depends_on == [tasks_by_title["Create README.md"].id]
    assert tasks_by_title["Execute safe validation checks"].depends_on == [tasks_by_title["Review README.md"].id]
    assert tasks_by_title["Consolidate final evidence"].depends_on == [tasks_by_title["Execute safe validation checks"].id]
