"""Reusable model response contract helpers for RI-X flows.

The helpers in this module are side-effect free: they do not execute tools,
mutate state, call providers, or authorize actions. They normalize a generic
safe response envelope that future model-assisted flows can compose with their
existing task-specific contracts.
"""

from __future__ import annotations

import json
from typing import Any


DEFAULT_SAFE_ACTION = "ask_clarification"
NO_ACTION = "no_action"
LOW_CONFIDENCE_THRESHOLD = 0.5
MAX_TEXT = 1200
MAX_ITEMS = 12
BASE_CONTRACT_FIELDS = {
    "answer",
    "needs_clarification",
    "clarification_question",
    "next_action",
    "allowed_actions",
    "risks",
    "evidence_refs",
    "confidence",
    "reason",
}


def _as_text(value: Any, *, max_chars: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:max_chars]


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:MAX_ITEMS]:
        text = _as_text(item, max_chars=240)
        if text and text not in result:
            result.append(text)
    return result


def _bounded_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except Exception:
        confidence = 0.0
    return max(0.0, min(confidence, 1.0))


def _extract_json_object(raw: dict[str, Any] | str | None) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _fallback_contract(*, task_kind: str | None = None, reason: str = "Invalid model response contract.") -> dict[str, Any]:
    task = _as_text(task_kind, max_chars=80) or "generic"
    return {
        "answer": "",
        "needs_clarification": True,
        "clarification_question": "Necesito mas contexto para continuar con seguridad.",
        "next_action": DEFAULT_SAFE_ACTION,
        "allowed_actions": [NO_ACTION, DEFAULT_SAFE_ACTION],
        "risks": ["invalid_or_missing_model_response"],
        "evidence_refs": [],
        "confidence": 0.0,
        "reason": f"{reason} task_kind={task}",
    }


def build_model_response_contract_prompt(task_kind: str | None = None) -> str:
    """Return a textual JSON contract block for safe model responses."""

    task = _as_text(task_kind, max_chars=80) or "generic"
    contract = {
        "answer": "string; concise answer grounded in provided state",
        "needs_clarification": "boolean; true when missing state blocks safe continuation",
        "clarification_question": "string or null; minimum necessary question",
        "next_action": "string; must be no_action, ask_clarification, or an action explicitly allowed by the caller",
        "allowed_actions": ["no_action", "ask_clarification"],
        "risks": ["string risk labels, no invented facts"],
        "evidence_refs": ["ids/paths explicitly present in provided evidence only"],
        "confidence": "float between 0.0 and 1.0",
        "reason": "short reason grounded in state_context",
    }
    return "\n".join(
        [
            f"Model response contract for {task}:",
            "Return one JSON object with exactly this safe envelope unless a task-specific schema overrides it.",
            "Do not execute tools, mutate state, or authorize actions from this contract alone.",
            "Do not invent evidence_refs; use only evidence explicitly present in state_context.",
            "If information is missing or confidence is low, use next_action=ask_clarification or no_action.",
            json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True),
        ]
    )


def normalize_model_response_contract(raw: dict[str, Any] | str | None, *, task_kind: str | None = None) -> dict[str, Any]:
    """Normalize raw model output into the base response contract."""

    parsed = _extract_json_object(raw)
    if not parsed:
        return _fallback_contract(task_kind=task_kind, reason="Model response was not valid JSON.")

    confidence = _bounded_confidence(parsed.get("confidence"))
    needs_clarification = bool(parsed.get("needs_clarification"))
    allowed_actions = _as_list(parsed.get("allowed_actions"))
    if not allowed_actions:
        allowed_actions = [NO_ACTION, DEFAULT_SAFE_ACTION]

    next_action = _as_text(parsed.get("next_action"), max_chars=120) or DEFAULT_SAFE_ACTION
    if confidence < LOW_CONFIDENCE_THRESHOLD and next_action not in {NO_ACTION, DEFAULT_SAFE_ACTION}:
        next_action = DEFAULT_SAFE_ACTION if needs_clarification else NO_ACTION

    return {
        "answer": _as_text(parsed.get("answer")),
        "needs_clarification": needs_clarification,
        "clarification_question": _as_text(parsed.get("clarification_question")) or None,
        "next_action": next_action,
        "allowed_actions": allowed_actions,
        "risks": _as_list(parsed.get("risks")),
        "evidence_refs": _as_list(parsed.get("evidence_refs")),
        "confidence": confidence,
        "reason": _as_text(parsed.get("reason"), max_chars=600) or "Model response contract normalized.",
    }


def validate_model_response_contract(
    response: dict[str, Any],
    *,
    allowed_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Validate and clamp a normalized response contract to allowed actions."""

    normalized = normalize_model_response_contract(response)
    caller_allowed = _as_list(allowed_actions) if allowed_actions is not None else []
    if caller_allowed:
        normalized["allowed_actions"] = [action for action in normalized["allowed_actions"] if action in caller_allowed]
        if NO_ACTION in caller_allowed and NO_ACTION not in normalized["allowed_actions"]:
            normalized["allowed_actions"].insert(0, NO_ACTION)
        if DEFAULT_SAFE_ACTION in caller_allowed and DEFAULT_SAFE_ACTION not in normalized["allowed_actions"]:
            normalized["allowed_actions"].append(DEFAULT_SAFE_ACTION)
        if normalized["next_action"] not in caller_allowed:
            if DEFAULT_SAFE_ACTION in caller_allowed:
                normalized["next_action"] = DEFAULT_SAFE_ACTION
            elif NO_ACTION in caller_allowed:
                normalized["next_action"] = NO_ACTION
            else:
                normalized["next_action"] = caller_allowed[0]
            normalized["reason"] = f"{normalized['reason']} Next action was not allowed by caller."

    if normalized["confidence"] < LOW_CONFIDENCE_THRESHOLD and normalized["next_action"] not in {NO_ACTION, DEFAULT_SAFE_ACTION}:
        if DEFAULT_SAFE_ACTION in normalized["allowed_actions"]:
            normalized["next_action"] = DEFAULT_SAFE_ACTION
        elif NO_ACTION in normalized["allowed_actions"]:
            normalized["next_action"] = NO_ACTION

    return normalized
