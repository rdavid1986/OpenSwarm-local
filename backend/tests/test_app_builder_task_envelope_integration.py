from backend.apps.swarms import swarms as swarms_module
from backend.tests.test_app_builder_mode_routing import _client, _create_chat_swarm


def test_app_builder_start_intake_attaches_task_envelope(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        return {
            "ok": True,
            "source": "model",
            "profile": "landing",
            "confidence": 0.91,
            "skipped_questions": ["backend", "database", "auth", "payments"],
            "required_questions": ["app_type", "main_goal", "target_users", "frontend"],
            "reason": "Landing informativa sin backend.",
            "question_overrides": {},
            "provider_health": {"ok": True},
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "Quiero una landing informativa para una peluquería con horarios y WhatsApp", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    state = body["project_intake_state"]
    envelope = state["task_envelope"]

    assert envelope["mode"] == "app_builder"
    assert envelope["creation_type"] == "web"
    assert envelope["input_modality"] == "text"
    assert envelope["side_effect_policy"] == "none"
    assert envelope["autonomy_level"] == "direct"
    assert envelope["trace_context"]["source"] == "project_intake"
    assert envelope["trace_context"]["swarm_id"] == str(swarm.id)
    assert "preview" in envelope["requested_outputs"]
    assert body["final_result"]["project_intake_state"]["task_envelope"]["mode"] == "app_builder"


def test_app_builder_advance_preserves_or_backfills_task_envelope(monkeypatch, tmp_path):
    client, orchestrator = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(orchestrator)

    async def fake_resolve_dynamic_intake_policy(**kwargs):
        return {
            "ok": True,
            "source": "model",
            "profile": "landing",
            "confidence": 0.91,
            "skipped_questions": ["backend", "database", "auth", "payments"],
            "required_questions": ["app_type", "main_goal", "target_users", "frontend"],
            "reason": "Landing informativa sin backend.",
            "question_overrides": {},
            "provider_health": {"ok": True},
        }

    monkeypatch.setattr(swarms_module, "resolve_dynamic_intake_policy", fake_resolve_dynamic_intake_policy)

    first = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "Quiero una landing informativa para una peluquería", "swarm_mode": "app_builder"},
    )

    assert first.status_code == 200
    first_body = first.json()
    first_envelope = first_body["project_intake_state"]["task_envelope"]

    current_id = first_body["project_intake_state"]["current_question_id"]
    second = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": f"respuesta para {current_id}", "swarm_mode": "app_builder"},
    )

    assert second.status_code == 200
    second_body = second.json()
    second_envelope = second_body["project_intake_state"]["task_envelope"]

    assert second_envelope["mode"] == "app_builder"
    assert second_envelope["creation_type"] == first_envelope["creation_type"]
    assert second_envelope["trace_context"]["source"] == "project_intake"
