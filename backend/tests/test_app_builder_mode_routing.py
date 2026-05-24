from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.runtime.provider import ProviderEvent
from backend.apps.swarms import swarms as swarms_module


class _FakeNormalChatAdapter:
    def __init__(self, *args, **kwargs):
        pass

    async def run_turn(self, context):
        yield ProviderEvent(type="provider_request", payload={"routed": True})
        yield ProviderEvent(
            type="message_final",
            payload={"message": {"role": "assistant", "content": "normal answer"}},
        )


def _client(monkeypatch, tmp_path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)
    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    return TestClient(app), orchestrator


def _create_chat_swarm(orchestrator):
    return orchestrator.create_swarm(user_prompt="hello", dashboard_id="dash-1", intent="chat")


def test_app_builder_normal_chat_starts_project_intake(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)
    monkeypatch.setattr(swarms_module, "OllamaAdapter", _FakeNormalChatAdapter)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "CRM para odontólogos", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["final_result"]["route"] == "implementation_request"
    assert body["project_intake_state"]["status"] == "collecting"
    assert body["final_result"]["project_intake_state"]["status"] == "collecting"
    assert body["provider_events"] == []


def test_ask_mode_same_text_stays_normal_chat(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)
    monkeypatch.setattr(swarms_module, "OllamaAdapter", _FakeNormalChatAdapter)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "CRM para odontólogos", "swarm_mode": "ask"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["final_result"]["route"] == "normal_chat"
    assert body["provider_events"]


def test_project_plan_ready_action_reflects_runner_disabled(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)
    monkeypatch.setattr(swarms_module, "experimental_dag_dependency_runner_enabled", lambda: False)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "CRM para odontólogos", "swarm_mode": "app_builder"},
    )
    assert response.status_code == 200

    questions = swarms_module._project_intake_questions()
    for index, question in enumerate(questions):
        response = client.post(
            f"/api/swarms/{swarm.id}/experimental/chat",
            json={"message": f"respuesta {index + 1} para {question['id']}", "swarm_mode": "app_builder"},
        )
        assert response.status_code == 200

    body = response.json()
    action = body["final_result"]["project_intake_action"]
    assert body["final_result"]["route"] == "project_plan_ready"
    assert body["project_intake_state"]["status"] == "ready_to_implement"
    assert action["type"] == "start_implementation"
    assert action["enabled"] is False
    assert action["reason"]
