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

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        fallback = kwargs["fallback_profile"]
        return {
            "ok": False,
            "source": "fallback",
            "profile": fallback["profile"],
            "confidence": fallback["confidence"],
            "skipped_questions": fallback["skipped_questions"],
            "required_questions": [],
            "reason": fallback["reason"],
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)

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

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        fallback = kwargs["fallback_profile"]
        return {
            "ok": False,
            "source": "fallback",
            "profile": fallback["profile"],
            "confidence": fallback["confidence"],
            "skipped_questions": fallback["skipped_questions"],
            "required_questions": [],
            "reason": fallback["reason"],
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)
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

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        fallback = kwargs["fallback_profile"]
        return {
            "ok": False,
            "source": "fallback",
            "profile": fallback["profile"],
            "confidence": fallback["confidence"],
            "skipped_questions": fallback["skipped_questions"],
            "required_questions": [],
            "reason": fallback["reason"],
            "question_overrides": {},
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)

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


def test_app_builder_model_assisted_intake_policy_is_used(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        return {
            "ok": True,
            "source": "model",
            "profile": "landing",
            "confidence": 0.91,
            "skipped_questions": ["database", "auth", "payments"],
            "required_questions": ["app_type", "backend", "visual_style"],
            "reason": "El modelo detectó una landing con formulario.",
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "Quiero una landing con formulario de contacto", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    state = body["project_intake_state"]

    assert state["intake_mode"] == "model_assisted"
    assert state["intake_profile"]["profile"] == "landing"
    assert state["question_policy"]["source"] == "model"
    assert set(state["skipped_questions"]) == {"database", "auth", "payments"}


def test_app_builder_applies_model_question_overrides(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        return {
            "ok": True,
            "source": "model",
            "profile": "landing",
            "confidence": 0.92,
            "skipped_questions": ["database", "auth", "payments"],
            "required_questions": ["app_type", "backend", "visual_style"],
            "reason": "Landing con formulario.",
            "question_overrides": {
                "app_type": {
                    "title": "Tipo de landing",
                    "prompt": "¿Qué tipo de landing querés crear para este proyecto?",
                    "options": ["Landing informativa", "Landing con formulario", "Portfolio simple"],
                }
            },
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "Quiero una landing con formulario", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    assistant_payload = body["messages"][-1]["payload"]
    question = assistant_payload["project_intake_question"]
    options = assistant_payload["project_intake_options"]

    assert body["project_intake_state"]["intake_mode"] == "model_assisted"
    assert body["project_intake_state"]["question_overrides"]["app_type"]["title"] == "Tipo de landing"
    assert question["id"] == "app_type"
    assert question["title"] == "Tipo de landing"
    assert question["prompt"] == "¿Qué tipo de landing querés crear para este proyecto?"
    assert [option["label"] for option in options[:3]] == ["Landing informativa", "Landing con formulario", "Portfolio simple"]
    assert options[-1]["value"] == "__custom__"


def test_app_builder_merges_plan_enrichment_without_replacing_core_fields(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        return {
            "ok": False,
            "source": "fallback",
            "profile": "static_site",
            "confidence": 0.7,
            "skipped_questions": ["backend", "database", "auth", "payments"],
            "required_questions": [],
            "reason": "Fallback static site.",
            "question_overrides": {},
        }

    async def fake_enrich_dynamic_intake_plan(**kwargs):
        return {
            "ok": True,
            "source": "model",
            "confidence": 0.88,
            "reason": "Model-assisted plan enrichment.",
            "plan_enrichment": {
                "mvp_scope": ["Crear landing estática", "Agregar formulario visual"],
                "recommended_stack_reason": "HTML/CSS simple alcanza para el primer MVP.",
                "implementation_notes": ["Priorizar contenido visible"],
                "risks": ["El formulario no enviará datos sin backend"],
                "out_of_scope_reason": "Pagos y login quedan fuera.",
            },
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)
    monkeypatch.setattr(swarms_module, "enrich_dynamic_intake_plan", fake_enrich_dynamic_intake_plan)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "Quiero una landing informativa", "swarm_mode": "app_builder"},
    )
    assert response.status_code == 200
    body = response.json()

    while body["project_intake_state"]["status"] != "ready_to_implement":
        current_id = body["project_intake_state"]["current_question_id"]
        response = client.post(
            f"/api/swarms/{swarm.id}/experimental/chat",
            json={"message": f"respuesta para {current_id}", "swarm_mode": "app_builder"},
        )
        assert response.status_code == 200
        body = response.json()

    plan = body["project_intake_state"]["generated_plan"]
    assert plan["backend"] == "Sin backend por ahora"
    assert plan["database"] == "No necesita base por ahora"
    assert plan["auth"] == "Sin login"
    assert plan["payments"] == "No"
    assert plan["plan_enrichment_source"] == "model"
    assert plan["plan_enrichment"]["mvp_scope"] == ["Crear landing estática", "Agregar formulario visual"]
    assert plan["plan_enrichment"]["risks"] == ["El formulario no enviará datos sin backend"]


def test_app_builder_landing_skipped_questions_get_defaults(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        return {
            "ok": True,
            "source": "model",
            "profile": "landing",
            "confidence": 0.91,
            "skipped_questions": ["backend", "database", "auth", "payments"],
            "required_questions": ["app_type", "main_goal", "target_users", "frontend", "deploy", "visual_style", "mvp_priority", "technical_constraints", "out_of_scope"],
            "reason": "Landing informativa sin backend.",
            "question_overrides": {},
        }

    async def fake_enrich_dynamic_intake_plan(**kwargs):
        return {
            "ok": False,
            "source": "fallback",
            "confidence": 0.0,
            "reason": "No enrichment in test.",
            "plan_enrichment": {},
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)
    monkeypatch.setattr(swarms_module, "enrich_dynamic_intake_plan", fake_enrich_dynamic_intake_plan)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "Quiero una landing informativa para una peluquería", "swarm_mode": "app_builder"},
    )
    assert response.status_code == 200
    body = response.json()

    while body["project_intake_state"]["status"] != "ready_to_implement":
        current_id = body["project_intake_state"]["current_question_id"]
        response = client.post(
            f"/api/swarms/{swarm.id}/experimental/chat",
            json={"message": f"respuesta para {current_id}", "swarm_mode": "app_builder"},
        )
        assert response.status_code == 200
        body = response.json()

    plan = body["project_intake_state"]["generated_plan"]
    summary = body["final_result"]["summary"]

    assert plan["backend"] == "Sin backend por ahora"
    assert plan["database"] == "No necesita base por ahora"
    assert plan["auth"] == "Sin login"
    assert plan["payments"] == "No"
    assert "None" not in summary
    assert "Stack sugerido:" in summary
    assert "Sin backend por ahora" in summary
    assert "No necesita base por ahora" in summary
    assert "Autenticación: Sin login" in summary
    assert "Pagos: No" in summary


def test_plan_mode_vague_request_returns_context_clarification(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "hacelo", "swarm_mode": "plan"},
    )

    assert response.status_code == 200
    body = response.json()
    final_result = body["final_result"]
    clarification = final_result["context_clarification"]

    assert final_result["route"] == "context_clarification"
    assert clarification["needs_clarification"] is True
    assert clarification["clarification_state"]["status"] == "pending_clarification"
    assert clarification["clarification_options"]


def test_app_builder_vague_request_uses_context_clarification_before_intake(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "hacelo", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    clarification = body["final_result"]["context_clarification"]

    assert body["final_result"]["route"] == "context_clarification"
    assert clarification["needs_clarification"] is True
    assert clarification["clarification_state"]["status"] == "pending_clarification"
    assert body["project_intake_state"] == {}
