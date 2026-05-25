"""Context clarification decision layer.

U.1 keeps this module side-effect free: it never mutates SwarmState, executes
tools, or prepares actions. It only decides whether a user request has enough
context to continue safely.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid5, NAMESPACE_URL


CLEAR_ENOUGH_MODES = {"ask", "chat"}
PROJECT_MODES = {"plan", "app_builder", "debug", "skill_builder"}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _as_text(value).lower()


def _has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def build_clarification_question(*, mode: str, reason: str) -> str:
    normalized_mode = _lower(mode or "ask")
    if reason == "empty_user_message":
        return {
            "plan": "¿Qué querés planear?",
            "app_builder": "¿Qué querés construir?",
            "debug": "¿Qué error, archivo, app o salida querés revisar?",
            "skill_builder": "¿Qué skill querés crear o mejorar?",
        }.get(normalized_mode, "¿Qué querés hacer?")

    if reason == "debug_request_without_target_context":
        return "¿Qué error, archivo, app o salida querés revisar?"

    if reason == "project_mode_request_too_vague":
        return {
            "plan": "¿Qué querés planear y con qué objetivo?",
            "app_builder": "¿Qué tipo de app o web querés construir?",
            "debug": "¿Qué problema querés corregir y dónde ocurre?",
            "skill_builder": "¿Qué skill querés crear o mejorar y para qué tarea?",
        }.get(normalized_mode, "¿Qué querés construir, planear o corregir?")

    return "¿Qué información falta para continuar?"


def build_clarification_options(*, mode: str, reason: str) -> list[dict[str, str]]:
    normalized_mode = _lower(mode or "ask")
    base_options = {
        "plan": [
            {"label": "Plan técnico", "value": "plan técnico", "kind": "recommended"},
            {"label": "Roadmap por fases", "value": "roadmap por fases", "kind": "possible"},
            {"label": "Arquitectura", "value": "arquitectura", "kind": "possible"},
        ],
        "app_builder": [
            {"label": "Landing simple", "value": "landing simple", "kind": "recommended"},
            {"label": "Web/app completa", "value": "web app completa", "kind": "possible"},
            {"label": "Dashboard", "value": "dashboard", "kind": "possible"},
        ],
        "debug": [
            {"label": "Pegar error", "value": "pegar error", "kind": "recommended"},
            {"label": "Revisar archivo", "value": "revisar archivo", "kind": "possible"},
            {"label": "Revisar Output", "value": "revisar output", "kind": "possible"},
        ],
        "skill_builder": [
            {"label": "Nueva skill", "value": "nueva skill", "kind": "recommended"},
            {"label": "Mejorar skill existente", "value": "mejorar skill existente", "kind": "possible"},
            {"label": "Debug de skill", "value": "debug de skill", "kind": "possible"},
        ],
    }.get(normalized_mode, [
        {"label": "Explicar", "value": "explicar", "kind": "recommended"},
        {"label": "Planear", "value": "planear", "kind": "possible"},
        {"label": "Crear", "value": "crear", "kind": "possible"},
    ])

    options = list(base_options)
    options.append({"label": "Otra opción", "value": "__custom__", "kind": "custom"})
    return options


def build_clarification_state(*, mode: str, reason: str, question: str, options: list[dict[str, str]]) -> dict[str, Any]:
    clarification_id = uuid5(NAMESPACE_URL, f"openswarm:clarification:{mode}:{reason}:{question}").hex
    return {
        "status": "pending_clarification",
        "clarification_id": clarification_id,
        "mode": mode,
        "reason": reason,
        "question": question,
        "options": options,
    }


def _clarification_payload(*, mode: str, reason: str, risk: str) -> dict[str, Any]:
    question = build_clarification_question(mode=mode, reason=reason)
    options = build_clarification_options(mode=mode, reason=reason)
    clarification_state = build_clarification_state(
        mode=mode,
        reason=reason,
        question=question,
        options=options,
    )
    return {
        "ok": False,
        "source": "deterministic",
        "needs_clarification": True,
        "reason": reason,
        "clarification_question": question,
        "clarification_options": options,
        "clarification_state": clarification_state,
        "mode": mode,
        "risk": risk,
    }


def resolve_context_clarification(
    *,
    user_message: str,
    swarm_mode: str | None = None,
    intent: str | None = None,
    available_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic clarification decision.

    The result is intentionally conservative. It only asks for clarification when
    the request is too vague for the selected mode or when debug/refinement-like
    requests lack a target.
    """

    message = _lower(user_message)
    mode = _lower(swarm_mode or intent or "ask")
    context = available_context if isinstance(available_context, dict) else {}

    has_output = bool(context.get("output_id") or context.get("preview_output_id") or context.get("active_output"))
    has_error = bool(context.get("error") or context.get("stack_trace") or context.get("logs"))
    has_files = bool(context.get("files") or context.get("workspace_path"))

    if not message:
        return _clarification_payload(mode=mode, reason="empty_user_message", risk="low")

    vague_terms = {"hacer algo", "arreglalo", "mejoralo", "continuar", "seguir", "hazlo", "hacelo"}
    project_terms = {"app", "web", "landing", "dashboard", "programa", "sistema", "skill", "debug", "error"}
    debug_terms = {"debug", "error", "falla", "bug", "no funciona", "rompe", "crashea", "traceback"}

    if _has_any(message, debug_terms) and not (has_error or has_output or has_files):
        return _clarification_payload(mode=mode, reason="debug_request_without_target_context", risk="medium")

    if mode in PROJECT_MODES and _has_any(message, vague_terms) and not _has_any(message, project_terms):
        return _clarification_payload(mode=mode, reason="project_mode_request_too_vague", risk="low")

    return {
        "ok": True,
        "source": "deterministic",
        "needs_clarification": False,
        "reason": "context_sufficient",
        "clarification_question": None,
        "clarification_options": [],
        "clarification_state": {},
        "mode": mode if mode else "ask",
        "risk": "low",
    }
