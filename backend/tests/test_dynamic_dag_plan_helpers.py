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
        user_prompt="crear tutorial estático",
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
    assert "Create static app files" in titles
    assert "Review static app files" in titles
    assert "Create README.md" not in titles


def test_template_selection_dynamic_plan_builds_readme_dag(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app con backend",
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
    assert "Create implementation brief README.md" in titles
    assert "Review implementation brief README.md" in titles
    assert "Create static app" not in titles


def test_select_dag_template_landing_visual_without_backend_uses_static_app():
    plan = SwarmOrchestrator._normalize_generated_plan(
        {
            "summary": "Landing visual para peluqueria",
            "app_type": "landing page",
            "main_goal": "mostrar horarios y WhatsApp",
            "frontend": "HTML/CSS",
            "backend": "sin backend por ahora",
            "database": "no necesita base por ahora",
        }
    )

    assert SwarmOrchestrator._select_dag_template(plan) == "static_app"


def test_select_dag_template_real_backend_signal_overrides_visual_scope():
    plan = SwarmOrchestrator._normalize_generated_plan(
        {
            "summary": "Dashboard visual con backend real",
            "app_type": "dashboard",
            "main_goal": "usuarios con login real y datos persistentes",
            "frontend": "React",
            "backend": "backend real FastAPI",
            "database": "PostgreSQL",
        }
    )

    assert SwarmOrchestrator._select_dag_template(plan) == "implementation_brief"


def test_select_dag_template_static_label_with_real_database_stays_implementation_brief():
    plan = SwarmOrchestrator._normalize_generated_plan(
        {
            "summary": "Static admin with persisted data",
            "app_type": "static dashboard",
            "main_goal": "manage products with production database",
            "frontend": "HTML/CSS",
            "backend": "server",
            "database": "PostgreSQL",
        }
    )

    assert SwarmOrchestrator._select_dag_template(plan) == "implementation_brief"


def _task_types_for_topological_order(swarm):
    from backend.apps.agents.runtime.experimental_dag_dependency_runner import ExperimentalDAGDependencyRunner
    from backend.apps.agents.runtime.experimental_task_type_registry import classify_experimental_task

    runner = ExperimentalDAGDependencyRunner()
    ordered = runner._topological_sort(swarm)
    return [classify_experimental_task(task) for task in ordered]


def test_static_app_dag_topological_phase_order_keeps_consolidate_last(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path
    swarm = orchestrator.create_swarm(
        user_prompt="crear landing estatica",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    updated = orchestrator.ensure_static_app_dag(
        swarm_id=swarm.id,
        generated_plan={
            "app_type": "landing page",
            "frontend": "HTML/CSS",
            "backend": "no backend",
            "database": "no database",
        },
    )

    assert _task_types_for_topological_order(updated) == [
        "architecture_plan_execute",
        "frontend_plan_execute",
        "backend_plan_execute",
        "security_review_execute",
        "create_static_app",
        "review_static_app",
        "validation_execute",
        "consolidate_final",
    ]


def test_implementation_brief_dag_topological_phase_order_keeps_consolidate_last(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path
    swarm = orchestrator.create_swarm(
        user_prompt="crear app con backend",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    updated = orchestrator.ensure_readme_dag(
        swarm_id=swarm.id,
        generated_plan={
            "app_type": "web app",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
    )

    assert _task_types_for_topological_order(updated) == [
        "architecture_plan_execute",
        "frontend_plan_execute",
        "backend_plan_execute",
        "security_review_execute",
        "create_readme",
        "review_readme",
        "validation_execute",
        "consolidate_final",
    ]


def test_topological_phase_order_rejects_unknown_dependency(tmp_path):
    from backend.apps.agents.runtime.experimental_dag_dependency_runner import ExperimentalDAGDependencyRunner

    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path
    swarm = orchestrator.create_swarm(
        user_prompt="crear app con backend",
        dashboard_id="dashboard-test",
        intent="chat",
    )
    updated = orchestrator.ensure_readme_dag(swarm_id=swarm.id)
    updated.tasks[1].depends_on = ["missing-task"]

    runner = ExperimentalDAGDependencyRunner()
    try:
        runner._topological_sort(updated)
    except ValueError as exc:
        assert "Unknown task dependencies" in str(exc)
    else:
        raise AssertionError("Expected unknown dependency to fail")
