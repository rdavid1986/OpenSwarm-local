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
