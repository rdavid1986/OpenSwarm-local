from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator


def test_normalize_generated_plan_uses_defaults_and_source_values():
    plan = SwarmOrchestrator._normalize_generated_plan(
        {"app_type": "landing page", "frontend": "HTML/CSS"},
        defaults={"backend": "no backend", "database": "no database"},
    )

    assert plan["app_type"] == "landing page"
    assert plan["frontend"] == "HTML/CSS"
    assert plan["backend"] == "no backend"
    assert plan["database"] == "no database"
    assert plan["visual_style"] == "clean modern UI"


def test_select_dag_template_static_app_for_static_no_backend_no_database():
    plan = SwarmOrchestrator._normalize_generated_plan(
        {
            "app_type": "static tutorial",
            "frontend": "HTML/CSS",
            "backend": "no backend",
            "database": "no database",
        }
    )

    assert SwarmOrchestrator._select_dag_template(plan) == "static_app"


def test_select_dag_template_falls_back_to_implementation_brief_for_dynamic_scope():
    plan = SwarmOrchestrator._normalize_generated_plan(
        {
            "app_type": "web app",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        }
    )

    assert SwarmOrchestrator._select_dag_template(plan) == "implementation_brief"


def test_template_selection_static_plan_builds_static_app_dag(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        prompt="crear tutorial estático",
        dashboard_id="dashboard-test",
        intent="chat",
    )
    generated_plan = {
        "app_type": "static tutorial",
        "frontend": "HTML/CSS",
        "backend": "no backend",
        "database": "no database",
    }

    normalized = orchestrator._normalize_generated_plan(generated_plan)
    template = orchestrator._select_dag_template(normalized)

    if template == "static_app":
        updated = orchestrator.ensure_static_app_dag(swarm_id=swarm.id, generated_plan=generated_plan)
    else:
        updated = orchestrator.ensure_readme_dag(swarm_id=swarm.id, generated_plan=generated_plan)

    titles = [task.title for task in updated.tasks]
    assert "Create static app" in titles
    assert "Review static app" in titles
    assert "Create README.md" not in titles


def test_template_selection_dynamic_plan_builds_readme_dag(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        prompt="crear app con backend",
        dashboard_id="dashboard-test",
        intent="chat",
    )
    generated_plan = {
        "app_type": "web app",
        "frontend": "React",
        "backend": "FastAPI",
        "database": "PostgreSQL",
    }

    normalized = orchestrator._normalize_generated_plan(generated_plan)
    template = orchestrator._select_dag_template(normalized)

    if template == "static_app":
        updated = orchestrator.ensure_static_app_dag(swarm_id=swarm.id, generated_plan=generated_plan)
    else:
        updated = orchestrator.ensure_readme_dag(swarm_id=swarm.id, generated_plan=generated_plan)

    titles = [task.title for task in updated.tasks]
    assert "Create README.md" in titles
    assert "Review README.md" in titles
    assert "Create static app" not in titles
