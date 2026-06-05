"""Model assignment contracts for ORCH-RUNTIME.9.

This module stays side-effect free.
It does not call a model, mutate swarm state, or touch the frontend.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_MODEL = "qwen2.5-coder:14b"
KNOWN_RISK_PROFILES = {"low", "medium", "high", "unknown"}
KNOWN_SIDE_EFFECT_POLICIES = {"none", "requires_approval", "blocked", "unknown"}


def _as_text(value: Any, *, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        text = value.strip()
        return text or fallback
    text = str(value).strip()
    return text or fallback


def _clean_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        key_text = _as_text(key)
        if key_text:
            cleaned[key_text] = item
    return cleaned


def _first_non_empty_text(*values: Any, fallback: str = DEFAULT_MODEL) -> str:
    for value in values:
        text = _as_text(value)
        if text:
            return text
    return fallback


def _resolve_preferred_model(
    preferred_models: dict[str, Any],
    *,
    phase: str,
    risk_profile: str,
    requested_model: str | None,
    fallback_model: str | None,
) -> tuple[str, str]:
    phase_key = _as_text(phase, fallback="unknown").lower()
    risk_key = _as_text(risk_profile, fallback="unknown").lower()

    candidates = [
        preferred_models.get(phase_key),
        preferred_models.get(risk_key),
        preferred_models.get("selected_model"),
        preferred_models.get("suggested_model"),
        preferred_models.get("model"),
        preferred_models.get("default"),
        preferred_models.get("preferred"),
        preferred_models.get("fallback"),
        requested_model,
        fallback_model,
    ]
    suggested = _first_non_empty_text(*candidates, fallback=DEFAULT_MODEL)

    fallback_candidates = [
        fallback_model,
        preferred_models.get("fallback"),
        preferred_models.get("default"),
        preferred_models.get("model"),
    ]
    fallback_value = _first_non_empty_text(*fallback_candidates, fallback=DEFAULT_MODEL)
    return suggested, fallback_value


@dataclass(frozen=True)
class PhaseModelRequirement:
    phase: str = "unknown"
    suggested_model: str = DEFAULT_MODEL
    fallback_model: str = DEFAULT_MODEL
    selected_model: str = DEFAULT_MODEL
    risk_profile: str = "unknown"
    side_effect_policy: str = "none"
    source: str = "task_envelope"
    reason: str = "default phase model assignment"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_phase_model_requirement(
    *,
    phase: str,
    risk_profile: str,
    side_effect_policy: str,
    available_context: dict[str, Any] | None = None,
    requested_model: str | None = None,
    fallback_model: str | None = None,
    trace_context: dict[str, Any] | None = None,
) -> PhaseModelRequirement:
    context = available_context if isinstance(available_context, dict) else {}
    preferred_models = _clean_dict(context.get("preferred_models"))
    phase_value = _as_text(phase, fallback="unknown").lower() or "unknown"
    risk_value = _as_text(risk_profile, fallback="unknown").lower() or "unknown"
    side_effect_value = _as_text(side_effect_policy, fallback="none").lower() or "none"

    suggested_model, fallback_value = _resolve_preferred_model(
        preferred_models,
        phase=phase_value,
        risk_profile=risk_value,
        requested_model=requested_model or context.get("selected_model") or context.get("default_model") or context.get("model"),
        fallback_model=fallback_model or context.get("fallback_model") or context.get("default_model") or context.get("model"),
    )

    if side_effect_value in {"blocked", "requires_approval"}:
        suggested_model = _first_non_empty_text(
            preferred_models.get("approval_required"),
            preferred_models.get("safe"),
            preferred_models.get("default"),
            suggested_model,
            fallback=suggested_model,
        )
        fallback_value = _first_non_empty_text(
            preferred_models.get("fallback"),
            fallback_value,
            fallback=DEFAULT_MODEL,
        )

    metadata = _clean_dict(context.get("model_assignment_metadata") or trace_context)
    metadata.setdefault("phase", phase_value)
    metadata.setdefault("risk_profile", risk_value)
    metadata.setdefault("side_effect_policy", side_effect_value)
    metadata.setdefault("known_risk_profiles", sorted(KNOWN_RISK_PROFILES))
    metadata.setdefault("known_side_effect_policies", sorted(KNOWN_SIDE_EFFECT_POLICIES))
    if preferred_models:
        metadata.setdefault("preferred_models", preferred_models)

    reason_parts = [f"phase={phase_value}"]
    if risk_value != "unknown":
        reason_parts.append(f"risk={risk_value}")
    if side_effect_value != "none":
        reason_parts.append(f"side_effect={side_effect_value}")
    if suggested_model == DEFAULT_MODEL:
        reason_parts.append("default model applied")
    elif requested_model:
        reason_parts.append("requested model applied")
    else:
        reason_parts.append("preferred model resolved")

    return PhaseModelRequirement(
        phase=phase_value,
        suggested_model=suggested_model,
        fallback_model=fallback_value,
        selected_model=suggested_model,
        risk_profile=risk_value,
        side_effect_policy=side_effect_value,
        source="task_envelope",
        reason="; ".join(reason_parts),
        metadata=metadata,
    )


def dump_phase_model_requirement(requirement: PhaseModelRequirement | dict[str, Any]) -> dict[str, Any]:
    if isinstance(requirement, PhaseModelRequirement):
        return requirement.as_dict()
    if isinstance(requirement, dict):
        return dict(requirement)
    return {}
