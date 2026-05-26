import pytest

from backend.apps.agents.runtime.provider import ProviderEvent
from backend.apps.swarms.dynamic_intake_policy import (
    build_dynamic_intake_policy_prompt,
    normalize_dynamic_intake_policy,
    resolve_dynamic_intake_policy,
)


QUESTIONS = [
    {"id": "app_type", "title": "Tipo", "prompt": "Tipo?"},
    {"id": "backend", "title": "Backend deseado", "prompt": "Backend?"},
    {"id": "database", "title": "Persistencia/base de datos", "prompt": "DB?"},
    {"id": "auth", "title": "Autenticación", "prompt": "Login?"},
    {"id": "payments", "title": "Pagos", "prompt": "Pagos?"},
    {"id": "visual_style", "title": "Estilo visual", "prompt": "Estilo?"},
]

FALLBACK_STATIC = {
    "profile": "static_site",
    "confidence": 0.7,
    "skipped_questions": ["backend", "database", "auth", "payments"],
    "reason": "fallback static",
}


class _FakeAdapter:
    async def run_turn(self, context):
        assert "sos openswarm" in context.system_prompt.lower()
        assert "modo app_builder" in context.system_prompt.lower()
        assert "el modelo razona, pero no inventa estado" in context.system_prompt.lower()
        yield ProviderEvent(
            type="message_final",
            payload={
                "message": {
                    "content": '{"profile":"landing","confidence":0.91,"skipped_questions":["database","auth","payments"],"required_questions":["app_type","backend","visual_style"],"reason":"landing with form"}'
                }
            },
        )


def test_build_dynamic_intake_policy_prompt_contains_question_ids():
    prompt = build_dynamic_intake_policy_prompt(
        user_message="landing con contacto",
        questions=QUESTIONS,
        fallback_profile=FALLBACK_STATIC,
    )

    assert "landing con contacto" in prompt
    assert "backend" in prompt
    assert "openswarm_system_prompt" in prompt
    assert "modo app_builder" in prompt.lower()
    assert "state_context" in prompt
    assert "state_context_prompt" in prompt
    assert "model_response_contract_prompt" in prompt
    assert "expected_json_shape" in prompt


def test_build_dynamic_intake_policy_prompt_includes_state_context_policy_route():
    prompt = build_dynamic_intake_policy_prompt(
        user_message="landing con contacto",
        questions=QUESTIONS,
        fallback_profile=FALLBACK_STATIC,
    )

    assert '"route": "dynamic_intake_policy"' in prompt
    assert '"project_intake_status": "policy_resolution"' in prompt
    assert "Use state_context as the real state snapshot." in prompt


def test_normalize_dynamic_intake_policy_accepts_model_policy():
    result = normalize_dynamic_intake_policy(
        {
            "profile": "landing",
            "confidence": 0.9,
            "skipped_questions": ["database", "auth", "payments"],
            "required_questions": ["app_type", "backend", "visual_style"],
            "reason": "landing with contact form",
        },
        questions=QUESTIONS,
        fallback_profile=FALLBACK_STATIC,
    )

    assert result["ok"] is True
    assert result["source"] == "model"
    assert result["profile"] == "landing"
    assert result["skipped_questions"] == ["database", "auth", "payments"]


def test_normalize_dynamic_intake_policy_falls_back_on_low_confidence():
    result = normalize_dynamic_intake_policy(
        {
            "profile": "landing",
            "confidence": 0.2,
            "skipped_questions": ["database"],
            "required_questions": ["app_type"],
            "reason": "weak",
        },
        questions=QUESTIONS,
        fallback_profile=FALLBACK_STATIC,
    )

    assert result["ok"] is False
    assert result["source"] == "fallback"
    assert set(result["skipped_questions"]) == {"backend", "database", "auth", "payments"}


def test_normalize_dynamic_intake_policy_blocks_full_app_skipping_technical_questions():
    result = normalize_dynamic_intake_policy(
        {
            "profile": "full_app",
            "confidence": 0.95,
            "skipped_questions": ["backend"],
            "required_questions": ["app_type"],
            "reason": "bad skip",
        },
        questions=QUESTIONS,
        fallback_profile=FALLBACK_STATIC,
    )

    assert result["ok"] is False
    assert result["source"] == "fallback"


@pytest.mark.asyncio
async def test_resolve_dynamic_intake_policy_uses_adapter():
    result = await resolve_dynamic_intake_policy(
        user_message="landing con formulario",
        questions=QUESTIONS,
        fallback_profile=FALLBACK_STATIC,
        adapter_factory=lambda: _FakeAdapter(),
    )

    assert result["ok"] is True
    assert result["source"] == "model"
    assert result["profile"] == "landing"
    assert result["skipped_questions"] == ["database", "auth", "payments"]


def test_normalize_dynamic_intake_policy_accepts_safe_question_overrides():
    result = normalize_dynamic_intake_policy(
        {
            "profile": "landing",
            "confidence": 0.92,
            "skipped_questions": ["database", "auth", "payments"],
            "required_questions": ["app_type", "backend", "visual_style"],
            "reason": "landing with form",
            "question_overrides": {
                "visual_style": {
                    "title": "Estilo para peluquería",
                    "prompt": "¿Qué estilo visual debería tener la landing de la peluquería?",
                    "options": ["Elegante", "Moderno", "Cálido", "Minimalista"],
                },
                "unknown_id": {
                    "title": "No usar",
                    "prompt": "No usar",
                    "options": ["A", "B"],
                },
                "auth": {
                    "title": "No usar",
                    "prompt": "No usar",
                    "options": ["A", "B"],
                },
            },
        },
        questions=QUESTIONS,
        fallback_profile=FALLBACK_STATIC,
    )

    assert result["ok"] is True
    assert result["question_overrides"]["visual_style"]["title"] == "Estilo para peluquería"
    assert "unknown_id" not in result["question_overrides"]
    assert "auth" not in result["question_overrides"]


def test_normalize_dynamic_intake_policy_rejects_invalid_question_override_shape():
    result = normalize_dynamic_intake_policy(
        {
            "profile": "landing",
            "confidence": 0.92,
            "skipped_questions": [],
            "required_questions": ["app_type", "visual_style"],
            "reason": "landing",
            "question_overrides": {
                "visual_style": {
                    "title": "Estilo",
                    "prompt": "¿Qué estilo?",
                    "options": ["Única"],
                },
            },
        },
        questions=QUESTIONS,
        fallback_profile=FALLBACK_STATIC,
    )

    assert result["ok"] is True
    assert result["question_overrides"] == {}


def test_normalize_dynamic_intake_policy_blocks_full_app_skipping_any_question():
    result = normalize_dynamic_intake_policy(
        {
            "profile": "full_app",
            "confidence": 0.95,
            "skipped_questions": ["visual_style"],
            "required_questions": ["app_type", "backend", "database", "auth", "payments"],
            "reason": "bad skip",
        },
        questions=QUESTIONS,
        fallback_profile={
            "profile": "full_app",
            "confidence": 0.75,
            "skipped_questions": [],
            "reason": "full app fallback",
        },
    )

    assert result["ok"] is False
    assert result["source"] == "fallback"
    assert result["profile"] == "full_app"
    assert result["skipped_questions"] == []
