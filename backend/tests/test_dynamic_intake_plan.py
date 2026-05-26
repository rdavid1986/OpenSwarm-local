import pytest

from backend.apps.agents.runtime.provider import ProviderEvent
from backend.apps.swarms.dynamic_intake_plan import (
    build_dynamic_plan_enrichment_prompt,
    normalize_dynamic_plan_enrichment,
    enrich_dynamic_intake_plan,
)


class _FakeAdapter:
    async def run_turn(self, context):
        assert "sos openswarm" in context.system_prompt.lower()
        assert "modo app_builder" in context.system_prompt.lower()
        assert "el modelo razona, pero no inventa estado" in context.system_prompt.lower()
        yield ProviderEvent(
            type="message_final",
            payload={
                "message": {
                    "content": '{"confidence":0.91,"mvp_scope":["Crear landing estática","Agregar formulario visual"],"recommended_stack_reason":"HTML/CSS simple alcanza para el primer MVP.","implementation_notes":["Priorizar contenido visible"],"risks":["El formulario no enviará datos sin backend"],"out_of_scope_reason":"Pagos y login no son necesarios."}'
                }
            },
        )


def test_build_dynamic_plan_enrichment_prompt_includes_plan_and_rules():
    prompt = build_dynamic_plan_enrichment_prompt(
        generated_plan={"app_type": "Landing + formulario", "backend": "Sin backend por ahora"},
        intake_state={"intake_mode": "model_assisted", "answers": {"app_type": "Landing"}},
    )

    assert "Landing + formulario" in prompt
    assert "openswarm_system_prompt" in prompt
    assert "modo app_builder" in prompt.lower()
    assert "state_context" in prompt
    assert "state_context_prompt" in prompt
    assert "model_response_contract_prompt" in prompt
    assert "Do not change app_type" in prompt
    assert "expected_json_shape" in prompt


def test_build_dynamic_plan_enrichment_prompt_includes_state_context_route():
    prompt = build_dynamic_plan_enrichment_prompt(
        generated_plan={"app_type": "Landing + formulario"},
        intake_state={"intake_mode": "model_assisted", "intake_profile": "landing"},
    )

    assert '"route": "dynamic_intake_plan_enrichment"' in prompt
    assert '"creation_type": "Landing + formulario"' in prompt
    assert "Use state_context as the real state snapshot." in prompt


def test_build_dynamic_plan_enrichment_prompt_can_include_project_memory():
    prompt = build_dynamic_plan_enrichment_prompt(
        generated_plan={"app_type": "Landing + formulario"},
        intake_state={"intake_mode": "model_assisted", "intake_profile": "landing"},
        project_memory_manifest={
            "swarm_id": "swarm-1",
            "current_goal": "Landing previa",
            "decisions": [{"id": "decision-1", "kind": "plan"}],
        },
    )

    assert '"project_memory_status": "present"' in prompt
    assert '"current_goal": "Landing previa"' in prompt
    assert '"decision_ids": [' in prompt
    assert '"decision-1"' in prompt


def test_normalize_dynamic_plan_enrichment_accepts_safe_enrichment():
    result = normalize_dynamic_plan_enrichment({
        "confidence": 0.92,
        "mvp_scope": ["Landing", "Formulario visual"],
        "recommended_stack_reason": "HTML/CSS simple es suficiente.",
        "implementation_notes": ["Usar contenido editable"],
        "risks": ["Sin backend no hay envío real"],
        "out_of_scope_reason": "Login queda fuera.",
    })

    assert result["ok"] is True
    assert result["source"] == "model"
    assert result["plan_enrichment"]["mvp_scope"] == ["Landing", "Formulario visual"]
    assert result["plan_enrichment"]["risks"] == ["Sin backend no hay envío real"]


def test_normalize_dynamic_plan_enrichment_falls_back_on_low_confidence():
    result = normalize_dynamic_plan_enrichment({
        "confidence": 0.2,
        "mvp_scope": ["No usar"],
    })

    assert result["ok"] is False
    assert result["source"] == "fallback"
    assert result["plan_enrichment"] == {}


@pytest.mark.asyncio
async def test_enrich_dynamic_intake_plan_uses_adapter():
    result = await enrich_dynamic_intake_plan(
        generated_plan={"app_type": "Landing + formulario"},
        intake_state={"intake_mode": "model_assisted"},
        adapter_factory=lambda: _FakeAdapter(),
    )

    assert result["ok"] is True
    assert result["source"] == "model"
    assert "recommended_stack_reason" in result["plan_enrichment"]


def test_build_dynamic_plan_enrichment_prompt_can_include_intent_brief():
    prompt = build_dynamic_plan_enrichment_prompt(
        generated_plan={"app_type": "Dashboard"},
        intake_state={"intake_mode": "model_assisted", "intake_profile": "dashboard"},
        intent_brief={
            "kind": "intent_brief",
            "primary_goal": "Crear dashboard local con auth",
            "known_constraints": ["backend: FastAPI"],
        },
    )

    assert '"intent_brief": {' in prompt
    assert '"primary_goal": "Crear dashboard local con auth"' in prompt
    assert "backend: FastAPI" in prompt
