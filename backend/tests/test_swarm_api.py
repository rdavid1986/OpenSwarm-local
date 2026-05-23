from pathlib import Path

from fastapi.testclient import TestClient

from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.orchestration.executor import SwarmMVPExecutor
from backend.apps.agents.orchestration.models import EvidenceRecord
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

    stored = store.load(swarm_id)
    stored.evidence.append(
        EvidenceRecord(
            kind="manual_test",
            swarm_id=swarm_id,
            task_id=stored.tasks[0].id,
            agent_id=stored.contracts[0].id,
            action="validated",
            summary="Structured evidence persists on SwarmState.",
        )
    )
    stored.tasks[0].evidence.append({"kind": "legacy_task_evidence", "extra": {"kept": True}})
    stored.final_evidence.append({"kind": "legacy_final_evidence", "detail": "kept"})
    store.save(stored)

    evidence_response = client.get(f"/api/swarms/{swarm_id}/evidence")
    assert evidence_response.status_code == 200
    evidence = evidence_response.json()["evidence"]
    assert evidence[0]["kind"] == "manual_test"
    assert evidence[0]["action"] == "validated"

    dumped = client.get(f"/api/swarms/{swarm_id}").json()
    assert dumped["evidence"][0]["kind"] == "manual_test"
    assert dumped["tasks"][0]["evidence"][-1]["extra"]["kept"] is True
    assert dumped["final_evidence"][-1]["detail"] == "kept"

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

def test_orchestration_canvas_enriches_existing_nodes_with_evidence(tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    swarm = orchestrator.create_swarm(user_prompt="Crear app", dashboard_id="dash-1")

    swarm.orchestration_canvas_state = {
        "nodes": [
            {"id": "frontend_agent", "status": "pending", "x": 10, "y": 20, "expanded": True},
            {"id": "reviewer", "status": "pending", "x": 30, "y": 40},
            {"id": "test_runner", "status": "pending", "x": 50, "y": 60},
            {"id": "consolidator", "status": "pending", "x": 70, "y": 80},
        ],
        "edges": [],
    }
    swarm.artifacts.append({
        "id": "artifact-1",
        "path": "README.md",
        "evidence_id": "evidence-1",
        "evidence_ref": "call-1",
    })
    swarm.final_evidence = [
        {
            "kind": "artifact",
            "artifact": {
                "id": "artifact-1",
                "path": "README.md",
                "evidence_id": "evidence-1",
                "evidence_ref": "call-1",
            },
        },
        {
            "kind": "review_result",
            "review_result": {
                "artifact_id": "artifact-1",
                "artifact_path": "README.md",
                "status": "approved",
            },
        },
        {
            "kind": "tool_history_summary",
            "tools": [
                {"tool": "Write", "ok": True},
                {"tool": "Read", "ok": True},
            ],
        },
    ]
    swarm.final_result = {
        "status": "completed",
        "claim_guard": {"status": "verified"},
    }

    swarms_module._enrich_orchestration_canvas_with_evidence(swarm)

    nodes = {node["id"]: node for node in swarm.orchestration_canvas_state["nodes"]}

    assert swarm.orchestration_canvas_state["evidence_linked"] is True
    assert nodes["frontend_agent"]["artifact_ref"] == "artifact-1"
    assert nodes["frontend_agent"]["evidence_ref"] == "evidence-1"
    assert nodes["frontend_agent"]["status"] == "completed"
    assert nodes["frontend_agent"]["x"] == 10
    assert nodes["frontend_agent"]["y"] == 20
    assert nodes["frontend_agent"]["expanded"] is True
    assert nodes["reviewer"]["artifact_ref"] == "artifact-1"
    assert nodes["reviewer"]["status"] == "completed"
    assert nodes["test_runner"]["evidence_ref"] == "2/2 tools ok"
    assert nodes["consolidator"]["evidence_ref"] == "claim_guard:verified"
    assert nodes["consolidator"]["status"] == "completed"


def test_dag_proposal_preview_endpoint_persists_decision_only(monkeypatch, tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    client = TestClient(app)

    created = client.post(
        "/api/swarms/create",
        json={"user_prompt": "Crear app desde proposal", "dashboard_id": "dash-preview", "intent": "chat"},
    )
    assert created.status_code == 200
    swarm_id = created.json()["id"]

    response = client.post(
        f"/api/swarms/{swarm_id}/experimental/dag-proposal-preview",
        json={
            "final_message": {
                "content": """
                {
                  "kind": "model_generated_dag",
                  "tasks": [
                    {
                      "id": "architecture",
                      "task_type": "architecture_plan_execute",
                      "role": "ArchitectAgent",
                      "title": "Execute architecture plan",
                      "objective": "Plan architecture."
                    },
                    {
                      "id": "create_readme",
                      "task_type": "create_readme",
                      "role": "DocumentationAgent",
                      "title": "Create implementation brief README.md",
                      "objective": "Create README.",
                      "depends_on": ["architecture"]
                    }
                  ]
                }
                """
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "accepted"
    assert body["validation_errors"] == []
    assert body["decision"]["kind"] == "dag_proposal_validation"
    assert body["decision"]["source"] == "model_dag_proposal"

    stored = store.load(swarm_id)
    assert stored.tasks == []
    assert stored.contracts == []
    assert stored.decisions[-1]["status"] == "accepted"


def test_dag_proposal_preview_endpoint_rejects_invalid_output(monkeypatch, tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    client = TestClient(app)

    created = client.post(
        "/api/swarms/create",
        json={"user_prompt": "Crear app desde proposal inválido", "dashboard_id": "dash-preview", "intent": "chat"},
    )
    assert created.status_code == 200
    swarm_id = created.json()["id"]

    response = client.post(
        f"/api/swarms/{swarm_id}/experimental/dag-proposal-preview",
        json={"final_message": "no hay json"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "rejected"
    assert body["validation_errors"][0]["error"] == "model_dag_proposal_response_not_json"

    stored = store.load(swarm_id)
    assert stored.tasks == []
    assert stored.contracts == []
    assert stored.decisions[-1]["status"] == "rejected"


def test_dag_proposal_preview_endpoint_persists_decision_only(monkeypatch, tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    client = TestClient(app)

    created = client.post(
        "/api/swarms/create",
        json={"user_prompt": "Crear app desde proposal", "dashboard_id": "dash-preview", "intent": "chat"},
    )
    assert created.status_code == 200
    swarm_id = created.json()["id"]

    response = client.post(
        f"/api/swarms/{swarm_id}/experimental/dag-proposal-preview",
        json={
            "final_message": {
                "content": """
                {
                  "kind": "model_generated_dag",
                  "tasks": [
                    {
                      "id": "architecture",
                      "task_type": "architecture_plan_execute",
                      "role": "ArchitectAgent",
                      "title": "Execute architecture plan",
                      "objective": "Plan architecture."
                    },
                    {
                      "id": "create_readme",
                      "task_type": "create_readme",
                      "role": "DocumentationAgent",
                      "title": "Create implementation brief README.md",
                      "objective": "Create README.",
                      "depends_on": ["architecture"]
                    }
                  ]
                }
                """
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "accepted"
    assert body["validation_errors"] == []
    assert body["decision"]["kind"] == "dag_proposal_validation"
    assert body["decision"]["source"] == "model_dag_proposal"

    stored = store.load(swarm_id)
    assert stored.tasks == []
    assert stored.contracts == []
    assert stored.decisions[-1]["status"] == "accepted"


def test_dag_proposal_preview_endpoint_rejects_invalid_output(monkeypatch, tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    client = TestClient(app)

    created = client.post(
        "/api/swarms/create",
        json={"user_prompt": "Crear app desde proposal inválido", "dashboard_id": "dash-preview", "intent": "chat"},
    )
    assert created.status_code == 200
    swarm_id = created.json()["id"]

    response = client.post(
        f"/api/swarms/{swarm_id}/experimental/dag-proposal-preview",
        json={"final_message": "no hay json"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "rejected"
    assert body["validation_errors"][0]["error"] == "model_dag_proposal_response_not_json"

    stored = store.load(swarm_id)
    assert stored.tasks == []
    assert stored.contracts == []
    assert stored.decisions[-1]["status"] == "rejected"


def test_dag_proposal_preview_generate_endpoint_uses_service(monkeypatch, tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)

    class FakeGenerateService:
        def __init__(self):
            self.calls = []

        async def generate_preview(self, *, swarm_id, request):
            self.calls.append((swarm_id, request))
            swarm = store.load(swarm_id)
            swarm.decisions.append({
                "kind": "dag_proposal_validation",
                "source": "model_dag_proposal",
                "proposal_kind": "model_generated_dag",
                "status": "accepted",
                "validation_errors": [],
                "metadata": {"fake": True},
            })
            store.save(swarm)

            class Response:
                ok = True
                status = "accepted"
                validation_errors = []
                decision = swarm.decisions[-1]
                final_message = {"content": "{\"kind\":\"model_generated_dag\",\"tasks\":[]}"}
                provider_events = []
                errors = []
                turns = 1
                swarm = swarm.model_dump(mode="json")

            return Response()

    fake_service = FakeGenerateService()
    monkeypatch.setattr(swarms_module, "model_dag_proposal_preview_service", fake_service)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    client = TestClient(app)

    created = client.post(
        "/api/swarms/create",
        json={"user_prompt": "Crear app desde modelo", "dashboard_id": "dash-preview", "intent": "chat"},
    )
    assert created.status_code == 200
    swarm_id = created.json()["id"]

    response = client.post(
        f"/api/swarms/{swarm_id}/experimental/dag-proposal-preview/generate",
        json={
            "model": "qwen2.5-coder:14b",
            "generated_plan": {"app_type": "web app", "frontend": "React"},
            "max_turns": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "accepted"
    assert body["decision"]["source"] == "model_dag_proposal"
    assert body["turns"] == 1
    assert fake_service.calls[0][0] == swarm_id
    assert fake_service.calls[0][1].model == "qwen2.5-coder:14b"
    assert fake_service.calls[0][1].generated_plan["frontend"] == "React"

    stored = store.load(swarm_id)
    assert stored.tasks == []
    assert stored.contracts == []
    assert stored.decisions[-1]["status"] == "accepted"


def test_dag_proposal_preview_generate_endpoint_uses_service(monkeypatch, tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)

    class FakeGenerateService:
        def __init__(self):
            self.calls = []

        async def generate_preview(self, *, swarm_id, request):
            self.calls.append((swarm_id, request))
            swarm = store.load(swarm_id)
            swarm.decisions.append({
                "kind": "dag_proposal_validation",
                "source": "model_dag_proposal",
                "proposal_kind": "model_generated_dag",
                "status": "accepted",
                "validation_errors": [],
                "metadata": {"fake": True},
            })
            store.save(swarm)

            class Response:
                ok = True
                status = "accepted"
                validation_errors = []
                decision = swarm.decisions[-1]
                final_message = {"content": "{\"kind\":\"model_generated_dag\",\"tasks\":[]}"}
                provider_events = []
                errors = []
                turns = 1
                swarm = swarm.model_dump(mode="json")

            return Response()

    fake_service = FakeGenerateService()
    monkeypatch.setattr(swarms_module, "model_dag_proposal_preview_service", fake_service)

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    client = TestClient(app)

    created = client.post(
        "/api/swarms/create",
        json={"user_prompt": "Crear app desde modelo", "dashboard_id": "dash-preview", "intent": "chat"},
    )
    assert created.status_code == 200
    swarm_id = created.json()["id"]

    response = client.post(
        f"/api/swarms/{swarm_id}/experimental/dag-proposal-preview/generate",
        json={
            "model": "qwen2.5-coder:14b",
            "generated_plan": {"app_type": "web app", "frontend": "React"},
            "max_turns": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "accepted"
    assert body["decision"]["source"] == "model_dag_proposal"
    assert body["turns"] == 1
    assert fake_service.calls[0][0] == swarm_id
    assert fake_service.calls[0][1].model == "qwen2.5-coder:14b"
    assert fake_service.calls[0][1].generated_plan["frontend"] == "React"

    stored = store.load(swarm_id)
    assert stored.tasks == []
    assert stored.contracts == []
    assert stored.decisions[-1]["status"] == "accepted"
