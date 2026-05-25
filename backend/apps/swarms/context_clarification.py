"""Context clarification decision layer.

U.1 keeps this module side-effect free: it never mutates SwarmState, executes
tools, or prepares actions. It only decides whether a user request has enough
context to continue safely.
"""

from __future__ import annotations

from typing import Any


CLEAR_ENOUGH_MODES = {"ask", "chat"}
PROJECT_MODES = {"plan", "app_builder", "debug", "skill_builder"}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _as_text(value).lower()


def _has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


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
        return {
            "ok": False,
            "source": "deterministic",
            "needs_clarification": True,
            "reason": "empty_user_message",
            "clarification_question": "¿Qué querés hacer?",
            "mode": mode,
            "risk": "low",
        }

    vague_terms = {"hacer algo", "arreglalo", "mejoralo", "continuar", "seguir", "hazlo", "hacelo"}
    project_terms = {"app", "web", "landing", "dashboard", "programa", "sistema", "skill", "debug", "error"}
    debug_terms = {"debug", "error", "falla", "bug", "no funciona", "rompe", "crashea", "traceback"}

    if _has_any(message, debug_terms) and not (has_error or has_output or has_files):
        return {
            "ok": False,
            "source": "deterministic",
            "needs_clarification": True,
            "reason": "debug_request_without_target_context",
            "clarification_question": "¿Qué error, archivo, app o salida querés revisar?",
            "mode": mode,
            "risk": "medium",
        }

    if mode in PROJECT_MODES and _has_any(message, vague_terms) and not _has_any(message, project_terms):
        return {
            "ok": False,
            "source": "deterministic",
            "needs_clarification": True,
            "reason": "project_mode_request_too_vague",
            "clarification_question": "¿Qué querés construir, planear o corregir?",
            "mode": mode,
            "risk": "low",
        }

    return {
        "ok": True,
        "source": "deterministic",
        "needs_clarification": False,
        "reason": "context_sufficient",
        "clarification_question": None,
        "mode": mode if mode else "ask",
        "risk": "low",
    }
