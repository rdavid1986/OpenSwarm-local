"""Context clarification decision layer.

U.1 keeps this module side-effect free: it never mutates SwarmState, executes
tools, or prepares actions. It only decides whether a user request has enough
context to continue safely.
"""

from __future__ import annotations

import json
from typing import Any, Callable
from uuid import uuid5, NAMESPACE_URL

from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.providers.provider_health import check_local_model_provider_health, is_local_model
from backend.apps.agents.runtime.provider import ProviderTurnContext
from backend.apps.swarms.system_prompt import build_openswarm_system_prompt


CLEAR_ENOUGH_MODES = {"ask", "chat"}
PROJECT_MODES = {"plan", "app_builder", "debug", "skill_builder"}
CREATION_TYPES = {
    "web",
    "web_app",
    "desktop",
    "mobile",
    "game",
    "cli",
    "automation",
    "skill",
    "unknown",
}
CONFIDENCE_THRESHOLD = 0.70
OPTION_KINDS = {"recommended", "possible", "risky", "custom"}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _as_text(value).lower()


def _has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(raw[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def infer_creation_type(user_message: str) -> str:
    text = _lower(user_message)

    if _has_any(text, {"videojuego", "juego", "unity", "godot", "unreal", "game"}):
        return "game"

    if _has_any(text, {"android", "ios", "mobile", "móvil", "movil", "app móvil", "app movil"}):
        return "mobile"

    if _has_any(text, {"windows", "mac", "macos", "linux", "desktop", "escritorio", "programa de windows", "programa para windows"}):
        return "desktop"

    if _has_any(text, {"cli", "consola", "terminal", "comando", "script"}):
        return "cli"

    if _has_any(text, {"automatización", "automatizacion", "automatizar", "bot", "workflow"}):
        return "automation"

    if _has_any(text, {"skill", "herramienta de openswarm"}):
        return "skill"

    if _has_any(text, {"web app", "webapp", "saas", "dashboard", "crud", "login", "usuarios", "backend", "base de datos"}):
        return "web_app"

    if _has_any(text, {"web", "landing", "sitio", "pagina", "página"}):
        return "web"

    return "unknown"


def build_creation_type_options() -> list[dict[str, str]]:
    return [
        {"label": "Web simple", "value": "web", "kind": "possible"},
        {"label": "Web app", "value": "web_app", "kind": "recommended"},
        {"label": "App de escritorio", "value": "desktop", "kind": "possible"},
        {"label": "App móvil", "value": "mobile", "kind": "possible"},
        {"label": "Videojuego", "value": "game", "kind": "possible"},
        {"label": "CLI / consola", "value": "cli", "kind": "possible"},
        {"label": "Automatización", "value": "automation", "kind": "possible"},
        {"label": "Skill de OpenSwarm", "value": "skill", "kind": "possible"},
        {"label": "Otra opción", "value": "__custom__", "kind": "custom"},
    ]


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

    if reason == "creation_type_unclear":
        return "¿Qué tipo de proyecto querés crear?"

    if reason == "project_mode_request_too_vague":
        return {
            "plan": "¿Qué querés planear y con qué objetivo?",
            "app_builder": "¿Qué tipo de app o web querés construir?",
            "debug": "¿Qué problema querés corregir y dónde ocurre?",
            "skill_builder": "¿Qué skill querés crear o mejorar y para qué tarea?",
        }.get(normalized_mode, "¿Qué querés construir, planear o corregir?")

    return "¿Qué información falta para continuar?"


def build_clarification_options(*, mode: str, reason: str) -> list[dict[str, str]]:
    if reason == "creation_type_unclear":
        return build_creation_type_options()

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

    creation_type = infer_creation_type(user_message)

    if not message:
        result = _clarification_payload(mode=mode, reason="empty_user_message", risk="low")
        result["creation_type"] = creation_type
        return result

    generic_creation_terms = {"crear una app", "crear app", "hacer una app", "hacer app", "crear un programa", "hacer un programa", "crear algo"}
    if mode in PROJECT_MODES and _has_any(message, generic_creation_terms) and creation_type == "unknown":
        result = _clarification_payload(mode=mode, reason="creation_type_unclear", risk="medium")
        result["creation_type"] = creation_type
        return result

    vague_terms = {"hacer algo", "arreglalo", "mejoralo", "continuar", "seguir", "hazlo", "hacelo", "ok", "dale", "confirmo", "sí", "si"}
    project_terms = {"app", "web", "landing", "dashboard", "programa", "sistema", "skill", "debug", "error"}
    debug_terms = {"debug", "error", "falla", "bug", "no funciona", "rompe", "crashea", "traceback"}

    if _has_any(message, debug_terms) and not (has_error or has_output or has_files):
        result = _clarification_payload(mode=mode, reason="debug_request_without_target_context", risk="medium")
        result["creation_type"] = creation_type
        return result

    if mode in PROJECT_MODES and _has_any(message, vague_terms) and not _has_any(message, project_terms):
        result = _clarification_payload(mode=mode, reason="project_mode_request_too_vague", risk="low")
        result["creation_type"] = creation_type
        return result

    return {
        "ok": True,
        "source": "deterministic",
        "needs_clarification": False,
        "reason": "context_sufficient",
        "clarification_question": None,
        "clarification_options": [],
        "clarification_state": {},
        "creation_type": creation_type,
        "mode": mode if mode else "ask",
        "risk": "low",
    }


def build_model_context_clarification_prompt(
    *,
    user_message: str,
    swarm_mode: str | None,
    fallback_decision: dict[str, Any],
    available_context: dict[str, Any] | None = None,
) -> str:
    master_prompt = build_openswarm_system_prompt(mode=swarm_mode or "ask", task_kind="context_clarification")
    payload = {
        "task": "Reason about whether OpenSwarm needs clarification before responding or acting.",
        "openswarm_system_prompt": master_prompt,
        "user_message": user_message,
        "swarm_mode": swarm_mode or "ask",
        "available_context": available_context if isinstance(available_context, dict) else {},
        "fallback_decision": fallback_decision,
        "allowed_creation_types": sorted(CREATION_TYPES),
        "allowed_option_kinds": sorted(OPTION_KINDS),
        "rules": [
            "Return only one JSON object.",
            "Follow openswarm_system_prompt.",
            "Do not execute tools.",
            "Do not claim actions were executed.",
            "The model reasons, but must not invent state.",
            "Ask the minimum necessary question only if context is insufficient.",
            "If the user request is clear enough, set needs_clarification=false.",
            "Do not ask irrelevant questions.",
            "For generic creation requests, classify the creation_type or ask which type.",
            "Options must be short UI labels with value and kind.",
            "Use kind=recommended for the best next answer, possible for alternatives, risky only if the option is unsafe or likely too broad, custom for __custom__.",
            "If unsure, keep the deterministic fallback decision.",
        ],
        "expected_json_shape": {
            "needs_clarification": True,
            "creation_type": "web | web_app | desktop | mobile | game | cli | automation | skill | unknown",
            "confidence": 0.0,
            "reason": "short reason",
            "clarification_question": "short question or null",
            "clarification_options": [
                {"label": "short label", "value": "short value", "kind": "recommended | possible | risky | custom"}
            ],
            "risk": "low | medium | high",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_model_options(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    options: list[dict[str, str]] = []
    seen_values: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            continue
        label = _as_text(raw.get("label"))[:80]
        option_value = _as_text(raw.get("value"))[:80]
        kind = _as_text(raw.get("kind")) or "possible"
        if kind not in OPTION_KINDS:
            kind = "possible"
        if not label or not option_value or option_value in seen_values:
            continue
        options.append({"label": label, "value": option_value, "kind": kind})
        seen_values.add(option_value)

    if "__custom__" not in seen_values:
        options.append({"label": "Otra opción", "value": "__custom__", "kind": "custom"})

    return options[:8]


def normalize_model_context_clarification(
    model_output: Any,
    *,
    fallback_decision: dict[str, Any],
) -> dict[str, Any]:
    parsed = model_output if isinstance(model_output, dict) else _extract_json_object(str(model_output or ""))

    def fallback(reason: str) -> dict[str, Any]:
        result = dict(fallback_decision)
        result["source"] = "fallback"
        result["model_reason"] = reason
        return result

    if not parsed:
        return fallback("Model did not return a valid JSON object.")

    try:
        confidence = float(parsed.get("confidence"))
    except Exception:
        confidence = 0.0

    if confidence < CONFIDENCE_THRESHOLD:
        return fallback("Model confidence is below the safety threshold.")

    creation_type = _as_text(parsed.get("creation_type")) or _as_text(fallback_decision.get("creation_type")) or "unknown"
    if creation_type not in CREATION_TYPES:
        return fallback("Model returned an unknown creation_type.")

    needs_clarification = bool(parsed.get("needs_clarification"))
    if needs_clarification and fallback_decision.get("needs_clarification") is False:
        return fallback("Model tried to ask clarification even though deterministic context is sufficient.")

    question = _as_text(parsed.get("clarification_question")) or None
    risk = _as_text(parsed.get("risk")) or _as_text(fallback_decision.get("risk")) or "low"
    if risk not in {"low", "medium", "high"}:
        risk = "medium"

    options = _normalize_model_options(parsed.get("clarification_options"))
    if needs_clarification and not question:
        return fallback("Model requested clarification without a question.")
    if needs_clarification and not options:
        return fallback("Model requested clarification without valid options.")

    result = {
        "ok": not needs_clarification,
        "source": "model",
        "needs_clarification": needs_clarification,
        "reason": _as_text(parsed.get("reason")) or "Model-assisted context clarification.",
        "clarification_question": question,
        "clarification_options": options if needs_clarification else [],
        "clarification_state": {},
        "creation_type": creation_type,
        "mode": _as_text(fallback_decision.get("mode")) or "ask",
        "risk": risk,
        "confidence": max(0.0, min(confidence, 1.0)),
    }

    if needs_clarification:
        result["clarification_state"] = build_clarification_state(
            mode=result["mode"],
            reason=result["reason"],
            question=question or "",
            options=options,
        )

    return result


async def resolve_model_context_clarification(
    *,
    user_message: str,
    swarm_mode: str | None = None,
    intent: str | None = None,
    available_context: dict[str, Any] | None = None,
    model: str = "qwen2.5-coder:14b",
    adapter_factory: Callable[[], OllamaAdapter] | None = None,
) -> dict[str, Any]:
    fallback_decision = resolve_context_clarification(
        user_message=user_message,
        swarm_mode=swarm_mode,
        intent=intent,
        available_context=available_context,
    )
    adapter = adapter_factory() if adapter_factory else OllamaAdapter(allow_network=True, supports_json_mode=True)

    if (adapter_factory is None or isinstance(adapter, OllamaAdapter)) and is_local_model(model):
        health = check_local_model_provider_health(
            model=model,
            base_url=getattr(adapter, "base_url", None),
            timeout_seconds=2.0,
        )
        if not health.get("ok"):
            fallback = dict(fallback_decision)
            fallback["source"] = "fallback"
            fallback["provider_health"] = health
            fallback["model_reason"] = _as_text(health.get("reason")) or "Provider is unavailable."
            return fallback

    context = ProviderTurnContext(
        session_id="context-clarification",
        agent_id="context-clarification",
        model=model,
        system_prompt=build_openswarm_system_prompt(mode=swarm_mode or intent or "ask", task_kind="context_clarification"),
        messages=[
            {
                "role": "user",
                "content": build_model_context_clarification_prompt(
                    user_message=user_message,
                    swarm_mode=swarm_mode,
                    fallback_decision=fallback_decision,
                    available_context=available_context,
                ),
            }
        ],
        tools=[],
    )

    assistant_content = ""
    try:
        async for event in adapter.run_turn(context):
            if event.type == "message_final":
                message = event.payload.get("message") if isinstance(event.payload, dict) else {}
                assistant_content = _as_text((message or {}).get("content"))
            elif event.type == "error":
                return normalize_model_context_clarification(
                    {"confidence": 0.0},
                    fallback_decision=fallback_decision,
                )
    except Exception:
        return normalize_model_context_clarification(
            {"confidence": 0.0},
            fallback_decision=fallback_decision,
        )

    return normalize_model_context_clarification(
        assistant_content,
        fallback_decision=fallback_decision,
    )
