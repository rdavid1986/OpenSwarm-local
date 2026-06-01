from backend.apps.swarms.context_clarification import (
    build_model_context_clarification_prompt,
    resolve_context_clarification,
)
from backend.apps.swarms.system_prompt import build_mode_prompt, build_openswarm_system_prompt


def test_app_builder_mode_prompt_mentions_reasoned_intake_and_output_evidence():
    prompt = build_mode_prompt("app_builder").lower()

    assert "project orientation" in prompt
    assert "approval gate" in prompt
    assert "intake razonado" in prompt
    assert "preguntas irrelevantes" in prompt
    assert "no digas que hay app creada" in prompt
    assert "output/evidence/metadata real" in prompt
    assert "guards autorizan o bloquean" in prompt


def test_debug_mode_prompt_requires_error_log_or_context_before_strong_diagnosis():
    prompt = build_mode_prompt("debug").lower()

    assert "project orientation" in prompt
    assert "herramientas permitidas" in prompt
    assert "error" in prompt
    assert "log" in prompt
    assert "contexto reproducible" in prompt
    assert "no afirmes fix sin evidence" in prompt
    assert "diagnosticar fuerte" in prompt


def test_refine_mode_prompt_mentions_candidate_iteration_evidence_and_accept_discard():
    prompt = build_mode_prompt("refine").lower()

    assert "candidate" in prompt
    assert "iteration" in prompt
    assert "evidence" in prompt
    assert "accept/discard" in prompt
    assert "candidate_iteration_id" in prompt


def test_unknown_mode_uses_safe_fallback_prompt():
    prompt = build_mode_prompt("unknown-mode").lower()

    assert "fallback/unknown" in prompt
    assert "no ejecutes acciones" in prompt
    assert "no inventes estado" in prompt
    assert "guards autorizan o bloquean" in prompt


def test_plan_and_skill_builder_prompts_use_project_orientation_without_execution():
    plan_prompt = build_mode_prompt("plan").lower()
    skill_prompt = build_mode_prompt("skill_builder").lower()

    assert "project orientation" in plan_prompt
    assert "single agent" in plan_prompt
    assert "multiagent" in plan_prompt
    assert "no ejecutes tareas" in plan_prompt
    assert "project orientation" in skill_prompt
    assert "crear skill" in skill_prompt
    assert "importar skill" in skill_prompt
    assert "no crees una skill real" in skill_prompt


def test_master_prompt_composes_specific_mode_without_duplicating_contracts():
    prompt = build_openswarm_system_prompt(mode="swarm_card", task_kind="context_clarification").lower()

    assert "sos openswarm" in prompt
    assert "modo swarm_card" in prompt
    assert "project orientation" in prompt
    assert "revisable/aprobable" in prompt
    assert "pending actions y outputs" in prompt
    assert "contrato de salida para context_clarification" in prompt
    assert "el modelo razona, pero no inventa estado" in prompt


def test_context_clarification_still_composes_master_prompt_and_json_contract():
    fallback = resolve_context_clarification(user_message="Quiero crear una app", swarm_mode="app_builder")

    prompt = build_model_context_clarification_prompt(
        user_message="Quiero crear una app",
        swarm_mode="app_builder",
        fallback_decision=fallback,
        available_context={},
    ).lower()

    assert "openswarm_system_prompt" in prompt
    assert "modo app_builder" in prompt
    assert "expected_json_shape" in prompt
    assert "clarification_options" in prompt


def test_master_prompt_mentions_structured_code_actions_without_execution_claims():
    prompt = build_openswarm_system_prompt(mode="debug", task_kind="code_action").lower()

    assert "code actions" in prompt
    assert "contrato estructurado" in prompt
    assert "no afirmes ejecucion" in prompt
    assert "diff" in prompt
    assert "validation" in prompt
