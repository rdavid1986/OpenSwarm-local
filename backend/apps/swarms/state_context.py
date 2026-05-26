"""Unified side-effect-free state context helpers for Swarm prompts.

RI-X.3 centralizes how model-assisted flows describe the real state they have
available. These helpers never query storage, call providers, execute tools, or
mutate SwarmState; they only normalize caller-provided values.
"""

from __future__ import annotations

import json
from typing import Any


MISSING = "missing"
UNKNOWN = "unknown"
MAX_TEXT = 600
MAX_LIST_ITEMS = 12
MAX_DICT_ITEMS = 24


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_state_context_value(value: Any) -> Any:
    """Return a JSON-safe, bounded representation without inventing values."""

    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text[:MAX_TEXT]
    if isinstance(value, (list, tuple, set)):
        return [normalize_state_context_value(item) for item in list(value)[:MAX_LIST_ITEMS]]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for index, key in enumerate(sorted(value.keys(), key=lambda item: str(item))):
            if index >= MAX_DICT_ITEMS:
                normalized["__truncated__"] = True
                break
            normalized[str(key)[:120]] = normalize_state_context_value(value.get(key))
        return normalized
    return _as_text(value)[:MAX_TEXT]


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _as_text(value)
        if text:
            return text
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _count_or_zero(value: Any) -> int:
    try:
        number = int(value)
        return number if number >= 0 else 0
    except Exception:
        return 0


def _evidence_status(*, evidence_status: str | None, available_context: dict[str, Any], artifact_count: int) -> str:
    explicit = _as_text(evidence_status)
    if explicit:
        return explicit
    if available_context.get("evidence") or available_context.get("final_evidence"):
        return "present"
    if artifact_count > 0:
        return "artifacts_present"
    return MISSING


def _available_context_summary(available_context: dict[str, Any]) -> dict[str, Any]:
    if not available_context:
        return {"status": MISSING, "keys": [], "values": {}}
    keys = sorted(str(key) for key in available_context.keys())[:MAX_LIST_ITEMS]
    return {
        "status": "present",
        "keys": keys,
        "values": normalize_state_context_value({key: available_context.get(key) for key in keys}),
    }


def build_state_context_payload(
    *,
    mode: str | None = None,
    route: str | None = None,
    user_message: str | None = None,
    creation_type: str | None = None,
    project_intake_status: str | None = None,
    pending_action_type: str | None = None,
    output_id: str | None = None,
    candidate_iteration_id: str | None = None,
    evidence_status: str | None = None,
    artifact_count: int | None = None,
    provider_health: dict[str, Any] | None = None,
    model_name: str | None = None,
    guard_status: str | None = None,
    available_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized snapshot from caller-provided state only."""

    context = _as_dict(available_context)
    provider = _as_dict(provider_health or context.get("provider_health"))
    resolved_artifact_count = _count_or_zero(
        artifact_count if artifact_count is not None else context.get("artifact_count") or context.get("artifacts_count")
    )
    resolved_pending_action = _first_text(pending_action_type, context.get("pending_action_type"), context.get("pending_action"))
    resolved_output_id = _first_text(output_id, context.get("output_id"), context.get("preview_output_id"), context.get("active_output"))
    resolved_candidate_iteration_id = _first_text(
        candidate_iteration_id,
        context.get("candidate_iteration_id"),
        context.get("iteration_id"),
    )

    payload = {
        "mode": _first_text(mode, context.get("mode")) or MISSING,
        "route": _first_text(route, context.get("route")) or MISSING,
        "user_message": _as_text(user_message) or MISSING,
        "creation_type": _first_text(creation_type, context.get("creation_type")) or UNKNOWN,
        "project_intake_status": _first_text(project_intake_status, context.get("project_intake_status")) or MISSING,
        "pending_action_type": resolved_pending_action,
        "has_pending_action": bool(resolved_pending_action),
        "output_id": resolved_output_id,
        "candidate_iteration_id": resolved_candidate_iteration_id,
        "has_candidate_iteration": bool(resolved_candidate_iteration_id),
        "evidence_status": _evidence_status(
            evidence_status=evidence_status,
            available_context=context,
            artifact_count=resolved_artifact_count,
        ),
        "artifact_count": resolved_artifact_count,
        "provider_health_status": _first_text(provider.get("status"), context.get("provider_health_status")) or MISSING,
        "model_name": _first_text(model_name, provider.get("model"), context.get("model_name")) or MISSING,
        "guard_status": _first_text(guard_status, context.get("guard_status"), context.get("claim_guard_status")) or MISSING,
        "available_context_summary": _available_context_summary(context),
    }
    return normalize_state_context_value(payload)


def build_state_context_prompt(context: dict[str, Any]) -> str:
    """Render state context with explicit missing/unknown semantics."""

    normalized = normalize_state_context_value(context)
    return "\n".join(
        [
            "OpenSwarm real state context:",
            "- Treat missing/null/empty fields as unavailable state, not permission to invent values.",
            "- Treat unknown fields as unknown until the system provides evidence.",
            "- The model may reason over this context, but guards authorize or block actions.",
            json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True),
        ]
    )
