from pathlib import Path

from fastapi.testclient import TestClient

from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.orchestration.executor import SwarmMVPExecutor
from backend.apps.swarms import swarms as swarms_module


def test_swarm_api_create_get_and_state(monkeypatch, tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    executor = SwarmMVPExecutor(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)
    monkeypatch.setattr(swarms_module, "swarm_mvp_executor", executor)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    client = TestClient(app)

    response = client.post("/api/swarms/create", json={"user_prompt": "Crea README", "dashboard_id": "dash-1"})
    assert response.status_code == 200
    swarm = response.json()
    assert swarm["user_prompt"] == "Crea README"
    assert len(swarm["tasks"]) == 4

    swarm_id = swarm["id"]
    assert client.get(f"/api/swarms/{swarm_id}").status_code == 200
    assert client.get("/api/swarms/list?dashboard_id=dash-1").json()["swarms"][0]["id"] == swarm_id

    paused = client.post(f"/api/swarms/{swarm_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    cancelled = client.post(f"/api/swarms/{swarm_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    workspace = tmp_path / "workspace"
    run = client.post(f"/api/swarms/{swarm_id}/run-mvp", json={"workspace_path": str(workspace)})
    assert run.status_code == 200
    assert (workspace / "README.md").exists()
    assert run.json()["status"] == "completed"
    assert run.json()["final_evidence"]
