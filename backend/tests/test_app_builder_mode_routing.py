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
    monkeypatch.setattr(swarms_module, "_local_provider_health_payload", lambda model=None: {
        "ok": True,
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "qwen2.5-coder:14b",
        "status": "available",
        "reason": "Ollama está disponible.",
        "available_models": ["qwen2.5-coder:14b"],
        "error_detail": "",
        "required_action": "",
    })

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
    assert action["capabilities"]["local_provider_health"]["ok"] is True
    assert body["experimental_capabilities"]["local_provider_health"]["ok"] is True


def test_project_plan_ready_action_reflects_local_provider_unavailable(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)
    monkeypatch.setattr(swarms_module, "experimental_dag_dependency_runner_enabled", lambda: True)
    monkeypatch.setattr(swarms_module, "_implementation_runner_flag_state", lambda: {
        flag: True for flag in swarms_module.IMPLEMENTATION_RUNNER_FLAGS
    })
    monkeypatch.setattr(swarms_module, "_local_provider_health_payload", lambda model=None: {
        "ok": False,
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "qwen2.5-coder:14b",
        "status": "unavailable",
        "reason": "Ollama no está corriendo o no responde en http://localhost:11434",
        "available_models": [],
        "error_detail": "connection refused",
        "required_action": "Abrí Ollama o ejecutá `ollama serve`, verificá que el modelo esté instalado con `ollama list`.",
    })

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
    health = action["capabilities"]["local_provider_health"]

    assert body["project_intake_state"]["status"] == "ready_to_implement"
    assert action["type"] == "start_implementation"
    assert action["enabled"] is False
    assert action["reason"] == "Ollama no está corriendo o no responde en http://localhost:11434"
    assert health["ok"] is False
    assert health["status"] == "unavailable"
    assert body["experimental_capabilities"]["local_provider_health"]["status"] == "unavailable"


def test_app_builder_static_site_intake_skips_irrelevant_questions(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)
    monkeypatch.setattr(swarms_module, "experimental_dag_dependency_runner_enabled", lambda: True)
    monkeypatch.setattr(swarms_module, "_implementation_runner_flag_state", lambda: {
        flag: True for flag in swarms_module.IMPLEMENTATION_RUNNER_FLAGS
    })
    monkeypatch.setattr(swarms_module, "_local_provider_health_payload", lambda model=None: {
        "ok": True,
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "model": "qwen2.5-coder:14b",
        "status": "available",
        "reason": "Ollama está disponible.",
        "available_models": ["qwen2.5-coder:14b"],
        "error_detail": "",
        "required_action": "",
    })

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "Quiero una landing informativa para una peluquería", "swarm_mode": "app_builder"},
    )
    assert response.status_code == 200
    body = response.json()
    state = body["project_intake_state"]

    assert state["intake_mode"] == "dynamic_fallback"
    assert state["intake_profile"]["profile"] == "static_site"
    assert set(state["skipped_questions"]) == {"backend", "database", "auth", "payments"}

    seen_questions = [state["current_question_id"]]
    while body["project_intake_state"]["status"] != "ready_to_implement":
        current_id = body["project_intake_state"]["current_question_id"]
        response = client.post(
            f"/api/swarms/{swarm.id}/experimental/chat",
            json={"message": f"respuesta para {current_id}", "swarm_mode": "app_builder"},
        )
        assert response.status_code == 200
        body = response.json()
        next_id = body["project_intake_state"].get("current_question_id")
        if next_id:
            seen_questions.append(next_id)

    assert "backend" not in seen_questions
    assert "database" not in seen_questions
    assert "auth" not in seen_questions
    assert "payments" not in seen_questions

    plan = body["project_intake_state"]["generated_plan"]
    assert plan["backend"] == "Sin backend por ahora"
    assert plan["database"] == "No necesita base por ahora"
    assert plan["auth"] == "Sin login"
    assert plan["payments"] == "No"
    assert set(plan["skipped_questions"]) == {"backend", "database", "auth", "payments"}
    summary = body["final_result"]["summary"]
    assert "Decisiones inferidas por intake adaptado:" in summary
    assert "Backend deseado: Sin backend por ahora" in summary
    assert "Autenticación: Sin login" in summary
    assert "Criterio aplicado:" in summary
    assert body["final_result"]["project_intake_action"]["enabled"] is True


def test_app_builder_full_app_intake_keeps_all_questions(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "Quiero un dashboard con login, backend y base de datos", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    state = body["project_intake_state"]

    assert state["intake_profile"]["profile"] == "full_app"
    assert state["skipped_questions"] == []
    assert state["current_question_id"] == "app_type"
