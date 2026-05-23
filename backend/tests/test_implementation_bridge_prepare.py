from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore


def _orchestrator(tmp_path):
    return SwarmOrchestrator(SwarmStore(root=tmp_path))


def _completed_planning_swarm(orchestrator, *, artifact_kind="implementation_brief", implementation_performed=False, generated_plan=None):
    swarm = orchestrator.create_swarm(
        user_prompt="Planificar app aprobada",
        intent="chat",
    )
    swarm.final_result = {
        "status": "completed",
        "artifact_kind": artifact_kind,
        "implementation_performed": implementation_performed,
        "generated_plan": generated_plan or {
            "app_type": "static tutorial",
            "frontend": "HTML/CSS",
            "backend": "no backend",
            "database": "no database",
            "summary": "Static tutorial app",
            "main_goal": "Build a static tutorial app",
        },
        "claim_guard": {"status": "verified"},
    }
    return orchestrator.store.save(swarm)


def test_bridge_rejects_without_approval(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    source = _completed_planning_swarm(orchestrator)

    _, errors, metadata = orchestrator.prepare_implementation_bridge_from_planning(
        source_swarm_id=source.id,
        approve=False,
    )

    assert errors == [{"error": "approval_required"}]
    assert metadata["source_swarm_id"] == source.id


def test_bridge_rejects_missing_final_result(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    source = orchestrator.create_swarm(user_prompt="Plan sin final result", intent="chat")

    _, errors, _ = orchestrator.prepare_implementation_bridge_from_planning(
        source_swarm_id=source.id,
        approve=True,
    )

    assert errors == [{"error": "source_final_result_required"}]


def test_bridge_rejects_already_implemented_source(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    source = _completed_planning_swarm(
        orchestrator,
        artifact_kind="static_app",
        implementation_performed=True,
    )

    _, errors, _ = orchestrator.prepare_implementation_bridge_from_planning(
        source_swarm_id=source.id,
        approve=True,
    )

    assert errors
    assert errors[0]["error"] == "source_already_implemented"


def test_bridge_rejects_fullstack_as_unsupported_for_now(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    source = _completed_planning_swarm(
        orchestrator,
        generated_plan={
            "app_type": "web app",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "summary": "Fullstack task app",
            "main_goal": "Build fullstack task app",
        },
    )

    _, errors, metadata = orchestrator.prepare_implementation_bridge_from_planning(
        source_swarm_id=source.id,
        approve=True,
    )

    assert errors
    assert errors[0]["error"] == "unsupported_implementation_target"
    assert metadata["target_template"] == "implementation_brief"


def test_bridge_static_creates_new_task_swarm_without_execution(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    source = _completed_planning_swarm(orchestrator)

    implementation, errors, metadata = orchestrator.prepare_implementation_bridge_from_planning(
        source_swarm_id=source.id,
        approve=True,
    )

    assert errors == []
    assert metadata["next_action"] == "run_dag_dependencies"
    assert implementation.id != source.id
    assert implementation.intent == "task"
    assert implementation.tasks
    assert all(task.task_type for task in implementation.tasks)
    assert implementation.tool_history == []
    assert implementation.final_evidence == []
    assert implementation.final_result == {}
    assert any(
        decision.get("kind") == "implementation_bridge_prepared"
        and decision.get("status") == "accepted"
        for decision in implementation.decisions
    )

    reloaded_source = orchestrator.store.load(source.id)
    assert reloaded_source.tasks == []
    assert reloaded_source.final_result["implementation_performed"] is False
