"""Model-assisted pending action intent resolution for Swarm chat.

This module is backend-only and side-effect free: it may ask a local model to
classify the user intent, but it never executes actions, mutates swarm state, or
calls tools. Callers must apply their own safety guards before preparing or
executing anything.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.providers.provider_health import check_local_model_provider_health, is_local_model
from backend.apps.agents.runtime.provider import ProviderTurnContext
from backend.apps.swarms.response_intelligence import RIStateSnapshot, build_ri_state_snapshot


PENDING_ACTION_CLASSIFICATIONS = {
    "confirm_pending_action",
    "update_pending_action",
    "cancel_pending_action",
    "explain_pending_action",
    "needs_clarification",
    "no_pending_action",
}

PENDING_ACTIONS = {"confirm_refinement", "run_refinement_pipeline"}
CONFIDENCE_THRESHOLD = 0.70


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_refinement_request(swarm: Any) -> dict[str, Any]:
    final_result = _as_dict(getattr(swarm, "final_result", None))
    refinement = final_result.get("refinement_request")
    return dict(refinement) if isinstance(refinement, dict) else {}


def _recent_chat_messages(swarm: Any, *, limit: int = 8) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for message in list(getattr(swarm, "messages", []) or [])[-limit:]:
        payload = _as_dict(getattr(message, "payload", None))
        role = _as_text(payload.get("role")) or _as_text(getattr(message, "from_agent_id", None)) or "unknown"
        content = _as_text(payload.get("content"))
        if content:
            messages.append({"role": role, "content": content[:1200]})
    return messages


def _default_resolution(
    *,
    classification: str = "needs_clarification",
    pending_action: str | None = None,
    output_id: str | None = None,
    requested_change: str | None = None,
    confidence: float = 0.0,
    safe_to_prepare: bool = False,
    reason: str = "Unable to safely resolve pending action intent.",
    clarification_question: str | None = "Queres confirmar, actualizar, cancelar o solo revisar este refinamiento pendiente?",
    provider_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "classification": classification,
        "pending_action": pending_action,
        "output_id": output_id,
        "requested_change": requested_change,
        "confidence": confidence,
        "safe_to_prepare": safe_to_prepare,
        "reason": reason,
        "clarification_question": clarification_question,
    }
    if provider_health is not None:
        result["provider_health"] = provider_health
    return result


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


def _normalize_model_resolution(
    model_output: Any,
    *,
    canonical_refinement: dict[str, Any],
    ri_state: RIStateSnapshot,
) -> dict[str, Any]:
    parsed = model_output if isinstance(model_output, dict) else _extract_json_object(str(model_output or ""))
    output_id = _as_text(canonical_refinement.get("output_id")) or None
    current_change = _as_text(canonical_refinement.get("requested_change")) or None
    pending_action = ri_state.pending_action if ri_state.pending_action in PENDING_ACTIONS else None

    if not parsed:
        return _default_resolution(
            pending_action=pending_action,
            output_id=output_id,
            requested_change=current_change,
            reason="Model did not return valid JSON.",
        )

    classification = _as_text(parsed.get("classification"))
    if classification not in PENDING_ACTION_CLASSIFICATIONS:
        return _default_resolution(
            pending_action=pending_action,
            output_id=output_id,
            requested_change=current_change,
            reason="Model returned an unknown classification.",
        )

    try:
        confidence = float(parsed.get("confidence"))
    except Exception:
        confidence = 0.0

    resolved_pending_action = parsed.get("pending_action")
    if resolved_pending_action is not None:
        resolved_pending_action = _as_text(resolved_pending_action)
    if resolved_pending_action not in PENDING_ACTIONS:
        resolved_pending_action = pending_action

    resolved_output_id = _as_text(parsed.get("output_id")) or output_id
    resolved_change = _as_text(parsed.get("requested_change")) or current_change
    safe_to_prepare = bool(parsed.get("safe_to_prepare"))
    reason = _as_text(parsed.get("reason")) or "Model-assisted pending action resolution."
    clarification_question = _as_text(parsed.get("clarification_question")) or None

    if classification == "no_pending_action":
        return _default_resolution(
            classification="no_pending_action",
            pending_action=None,
            output_id=None,
            requested_change=None,
            confidence=max(0.0, min(confidence, 1.0)),
            safe_to_prepare=False,
            reason=reason,
            clarification_question=None,
        )

    if confidence < CONFIDENCE_THRESHOLD:
        return _default_resolution(
            pending_action=pending_action,
            output_id=output_id,
            requested_change=current_change,
            confidence=max(0.0, min(confidence, 1.0)),
            reason="Model confidence is below the safety threshold.",
        )

    if classification == "confirm_pending_action":
        if not output_id or resolved_output_id != output_id or not current_change:
            return _default_resolution(
                pending_action=pending_action,
                output_id=resolved_output_id or output_id,
                requested_change=resolved_change or current_change,
                confidence=max(0.0, min(confidence, 1.0)),
                reason="Confirmation target does not match the pending refinement.",
            )
        if resolved_change and current_change and resolved_change != current_change:
            return _default_resolution(
                pending_action=pending_action,
                output_id=output_id,
                requested_change=current_change,
                confidence=max(0.0, min(confidence, 1.0)),
                reason="Confirmation changed the pending refinement request.",
            )
        safe_to_prepare = safe_to_prepare and resolved_pending_action in PENDING_ACTIONS
    else:
        safe_to_prepare = False

    if classification == "update_pending_action" and not resolved_change:
        return _default_resolution(
            pending_action=pending_action,
            output_id=output_id,
            requested_change=current_change,
            confidence=max(0.0, min(confidence, 1.0)),
            reason="Update intent did not include a usable requested_change.",
        )

    if classification in {"needs_clarification", "explain_pending_action"} and not clarification_question:
        clarification_question = "Queres confirmar, actualizar o cancelar este refinamiento pendiente?"

    return {
        "classification": classification,
        "pending_action": resolved_pending_action,
        "output_id": resolved_output_id or None,
        "requested_change": resolved_change or None,
        "confidence": max(0.0, min(confidence, 1.0)),
        "safe_to_prepare": safe_to_prepare,
        "reason": reason,
        "clarification_question": clarification_question,
    }


def build_pending_action_resolver_prompt(
    *,
    user_message: str,
    swarm_mode: str | None,
    canonical_refinement: dict[str, Any],
    ri_state: RIStateSnapshot,
    recent_messages: list[dict[str, str]],
) -> str:
    resolver_input = {
        "user_message": user_message,
        "swarm_mode": swarm_mode,
        "pending_action": ri_state.pending_action,
        "target_output_id": ri_state.target_output_id,
        "available_actions": ri_state.available_actions,
        "refinement_request": canonical_refinement,
        "recent_messages": recent_messages,
    }
    return json.dumps(resolver_input, ensure_ascii=False, indent=2)


async def resolve_pending_action_intent(
    *,
    swarm: Any,
    user_message: str,
    swarm_mode: str | None = None,
    model: str = "qwen2.5-coder:14b",
    adapter_factory: Callable[[], OllamaAdapter] | None = None,
) -> dict[str, Any]:
    """Classify a pending action message without mutating or executing state."""

    canonical_refinement = _canonical_refinement_request(swarm)
    ri_state = build_ri_state_snapshot(swarm, route="refinement_request", user_message=user_message)
    output_id = _as_text(canonical_refinement.get("output_id")) or None
    requested_change = _as_text(canonical_refinement.get("requested_change")) or None

    if not output_id:
        return _default_resolution(
            classification="no_pending_action",
            pending_action=None,
            output_id=None,
            requested_change=None,
            reason="No canonical pending refinement is available.",
            clarification_question=None,
        )

    adapter = adapter_factory() if adapter_factory else OllamaAdapter(allow_network=True, supports_json_mode=True)
    if (adapter_factory is None or isinstance(adapter, OllamaAdapter)) and is_local_model(model):
        health = check_local_model_provider_health(
            model=model,
            base_url=getattr(adapter, "base_url", None),
            timeout_seconds=2.0,
        )
        if not health.get("ok"):
            return _default_resolution(
                pending_action=ri_state.pending_action,
                output_id=output_id,
                requested_change=requested_change,
                reason=_as_text(health.get("reason")) or "Local model provider is unavailable.",
                provider_health=health,
            )

    prompt = build_pending_action_resolver_prompt(
        user_message=user_message,
        swarm_mode=swarm_mode,
        canonical_refinement=canonical_refinement,
        ri_state=ri_state,
        recent_messages=_recent_chat_messages(swarm),
    )
    context = ProviderTurnContext(
        session_id=str(getattr(swarm, "id", "") or "pending-action-resolution"),
        agent_id=getattr(swarm, "coordinator_contract_id", None) or "swarm",
        model=model,
        system_prompt=(
            "You are OpenSwarm's pending action intent resolver. Return only one JSON object. "
            "Do not execute tools. Decide whether the latest user message confirms, updates, cancels, "
            "asks to explain, needs clarification, or has no pending action. Exact words are not enough; "
            "use the provided canonical state as source of truth. Never set safe_to_prepare true unless "
            "the user clearly confirms the existing pending refinement, output_id matches, and requested_change is unchanged."
        ),
        messages=[{"role": "user", "content": prompt}],
        tools=[],
    )

    assistant_content = ""
    try:
        async for event in adapter.run_turn(context):
            if event.type == "message_final":
                message = _as_dict(event.payload.get("message"))
                assistant_content = _as_text(message.get("content"))
            elif event.type == "error":
                return _default_resolution(
                    pending_action=ri_state.pending_action,
                    output_id=output_id,
                    requested_change=requested_change,
                    reason=_as_text(event.payload.get("error")) or "Model resolver failed.",
                )
    except Exception as exc:
        return _default_resolution(
            pending_action=ri_state.pending_action,
            output_id=output_id,
            requested_change=requested_change,
            reason=f"Model resolver failed: {exc}",
        )

    return _normalize_model_resolution(
        assistant_content,
        canonical_refinement=canonical_refinement,
        ri_state=ri_state,
    )
