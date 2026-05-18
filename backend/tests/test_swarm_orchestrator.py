from backend.apps.agents.orchestration import SwarmOrchestrator, SwarmStore


def test_swarm_orchestrator_creates_mvp_task_dag(tmp_path):
    orchestrator = SwarmOrchestrator(SwarmStore(root=tmp_path))
    swarm = orchestrator.create_swarm(
        user_prompt="Crea un README.md básico en el workspace, revisalo con un agente reviewer y reportá evidencia.",
        dashboard_id="d1",
    )

    assert swarm.dashboard_id == "d1"
    assert len(swarm.contracts) == 4
    assert len(swarm.tasks) == 4
    assert [task.title for task in swarm.tasks] == [
        "Plan task DAG",
        "Create README.md",
        "Review README.md",
        "Consolidate final evidence",
    ]
    assert swarm.tasks[1].depends_on == [swarm.tasks[0].id]
    assert swarm.tasks[2].depends_on == [swarm.tasks[1].id]


def test_swarm_store_round_trips_state(tmp_path):
    store = SwarmStore(root=tmp_path)
    orchestrator = SwarmOrchestrator(store)
    created = orchestrator.create_swarm(user_prompt="Crear README")

    loaded = store.load(created.id)

    assert loaded.id == created.id
    assert loaded.user_prompt == "Crear README"
    assert len(store.list()) == 1


def test_structured_submit_artifact_message(tmp_path):
    orchestrator = SwarmOrchestrator(SwarmStore(root=tmp_path))
    swarm = orchestrator.create_swarm(user_prompt="Crear README")
    worker = next(c for c in swarm.contracts if c.role == "DocumentationAgent")
    task = next(t for t in swarm.tasks if t.title == "Create README.md")

    updated = orchestrator.submit_artifact(
        swarm_id=swarm.id,
        from_agent_id=worker.id,
        task_id=task.id,
        artifact={"id": "artifact-1", "path": "README.md", "kind": "documentation"},
    )

    assert updated.artifacts[0]["path"] == "README.md"
    assert updated.messages[-1].type == "submit_artifact"
    assert updated.messages[-1].artifact_refs == ["artifact-1"]
