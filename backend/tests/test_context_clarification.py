import pytest

from backend.apps.agents.runtime.provider import ProviderEvent
from backend.apps.swarms.context_clarification import resolve_context_clarification, resolve_model_context_clarification


def test_context_clarification_accepts_specific_app_request():
    result = resolve_context_clarification(
        user_message="Quiero crear una landing para una peluquería con horarios y WhatsApp",
        swarm_mode="app_builder",
    )

    assert result["ok"] is True
    assert result["needs_clarification"] is False
    assert result["reason"] == "context_sufficient"


def test_context_clarification_asks_for_empty_message():
    result = resolve_context_clarification(user_message="", swarm_mode="ask")

    assert result["ok"] is False
    assert result["needs_clarification"] is True
    assert result["reason"] == "empty_user_message"


def test_context_clarification_asks_for_vague_project_mode_request():
    result = resolve_context_clarification(user_message="hacelo", swarm_mode="plan")

    assert result["ok"] is False
    assert result["needs_clarification"] is True
    assert result["reason"] == "project_mode_request_too_vague"


def test_context_clarification_asks_for_debug_target_without_context():
    result = resolve_context_clarification(user_message="debug este error", swarm_mode="debug")

    assert result["ok"] is False
    assert result["needs_clarification"] is True
    assert result["reason"] == "debug_request_without_target_context"


def test_context_clarification_allows_debug_when_context_exists():
    result = resolve_context_clarification(
        user_message="debug este error",
        swarm_mode="debug",
        available_context={"logs": "Traceback..."},
    )

    assert result["ok"] is True
    assert result["needs_clarification"] is False


def test_context_clarification_uses_mode_specific_empty_question():
    result = resolve_context_clarification(user_message="", swarm_mode="skill_builder")

    assert result["clarification_question"] == "¿Qué skill querés crear o mejorar?"


def test_context_clarification_uses_mode_specific_vague_question():
    result = resolve_context_clarification(user_message="continuar", swarm_mode="app_builder")

    assert result["clarification_question"] == "¿Qué tipo de app o web querés construir?"


def test_context_clarification_returns_options_with_custom_choice():
    result = resolve_context_clarification(user_message="hacelo", swarm_mode="app_builder")

    assert result["needs_clarification"] is True
    assert result["clarification_options"][-1] == {"label": "Otra opción", "value": "__custom__", "kind": "custom"}
    assert {"label": "Landing simple", "value": "landing simple", "kind": "recommended"} in result["clarification_options"]


def test_context_clarification_success_returns_empty_options():
    result = resolve_context_clarification(
        user_message="Quiero una landing para una peluquería",
        swarm_mode="app_builder",
    )

    assert result["needs_clarification"] is False
    assert result["clarification_options"] == []


def test_context_clarification_marks_possible_options():
    result = resolve_context_clarification(user_message="hacelo", swarm_mode="debug")

    assert {"label": "Revisar archivo", "value": "revisar archivo", "kind": "possible"} in result["clarification_options"]


def test_context_clarification_returns_pending_state():
    result = resolve_context_clarification(user_message="hacelo", swarm_mode="plan")
    state = result["clarification_state"]

    assert state["status"] == "pending_clarification"
    assert state["clarification_id"]
    assert state["mode"] == "plan"
    assert state["reason"] == "project_mode_request_too_vague"
    assert state["question"] == result["clarification_question"]
    assert state["options"] == result["clarification_options"]


def test_context_clarification_success_returns_empty_state():
    result = resolve_context_clarification(
        user_message="Quiero una landing para una peluquería",
        swarm_mode="app_builder",
    )

    assert result["clarification_state"] == {}


def test_context_clarification_infers_game_creation_type():
    result = resolve_context_clarification(user_message="Quiero crear un videojuego 3D", swarm_mode="plan")

    assert result["ok"] is True
    assert result["creation_type"] == "game"


def test_context_clarification_infers_desktop_creation_type():
    result = resolve_context_clarification(user_message="Quiero crear un programa de Windows", swarm_mode="plan")

    assert result["ok"] is True
    assert result["creation_type"] == "desktop"


def test_context_clarification_asks_for_generic_app_creation_type():
    result = resolve_context_clarification(user_message="Quiero crear una app", swarm_mode="app_builder")

    assert result["ok"] is False
    assert result["reason"] == "creation_type_unclear"
    assert result["creation_type"] == "unknown"
    assert {"label": "Videojuego", "value": "game", "kind": "possible"} in result["clarification_options"]
    assert result["clarification_state"]["status"] == "pending_clarification"


def test_context_clarification_infers_web_app_creation_type():
    result = resolve_context_clarification(user_message="Quiero crear un dashboard con login", swarm_mode="app_builder")

    assert result["ok"] is True
    assert result["creation_type"] == "web_app"


class _FakeClarificationAdapter:
    async def run_turn(self, context):
        yield ProviderEvent(
            type="message_final",
            payload={
                "message": {
                    "content": '{"needs_clarification":true,"creation_type":"mobile","confidence":0.91,"reason":"La palabra app es ambigua.","clarification_question":"¿Qué tipo de app querés crear?","clarification_options":[{"label":"Android","value":"mobile","kind":"recommended"},{"label":"Web app","value":"web_app","kind":"possible"}],"risk":"medium"}'
                }
            },
        )


@pytest.mark.asyncio
async def test_model_context_clarification_uses_adapter():
    result = await resolve_model_context_clarification(
        user_message="Quiero crear una app",
        swarm_mode="app_builder",
        adapter_factory=lambda: _FakeClarificationAdapter(),
    )

    assert result["source"] == "model"
    assert result["needs_clarification"] is True
    assert result["creation_type"] == "mobile"
    assert result["clarification_question"] == "¿Qué tipo de app querés crear?"
    assert result["clarification_state"]["status"] == "pending_clarification"


@pytest.mark.asyncio
async def test_model_context_clarification_falls_back_on_low_confidence():
    class LowConfidenceAdapter:
        async def run_turn(self, context):
            yield ProviderEvent(
                type="message_final",
                payload={"message": {"content": '{"needs_clarification":false,"creation_type":"web","confidence":0.2,"reason":"weak"}'}},
            )

    result = await resolve_model_context_clarification(
        user_message="Quiero crear una app",
        swarm_mode="app_builder",
        adapter_factory=lambda: LowConfidenceAdapter(),
    )

    assert result["source"] == "fallback"
    assert result["needs_clarification"] is True
    assert result["reason"] == "creation_type_unclear"


@pytest.mark.asyncio
async def test_model_context_clarification_does_not_overask_clear_specific_request():
    class OveraskingAdapter:
        async def run_turn(self, context):
            yield ProviderEvent(
                type="message_final",
                payload={
                    "message": {
                        "content": '{"needs_clarification":true,"creation_type":"web","confidence":0.92,"reason":"Quiere detalles extra.","clarification_question":"¿Querés backend?","clarification_options":[{"label":"Sí","value":"sí","kind":"possible"},{"label":"No","value":"no","kind":"recommended"}],"risk":"low"}'
                    }
                },
            )

    result = await resolve_model_context_clarification(
        user_message="Quiero crear una landing para una peluquería con horarios y WhatsApp",
        swarm_mode="app_builder",
        adapter_factory=lambda: OveraskingAdapter(),
    )

    assert result["needs_clarification"] is False
    assert result["reason"] == "context_sufficient"
    assert result["source"] == "fallback"
    assert result["model_reason"] == "Model tried to ask clarification even though deterministic context is sufficient."
