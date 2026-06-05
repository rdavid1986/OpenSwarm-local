"""Task envelope contract for OpenSwarm orchestration runtime.

ORCH-RUNTIME.1A keeps this module side-effect free:
- it does not mutate SwarmState
- it does not execute tools
- it does not create agents
- it does not run DAG phases
- it does not apply filesystem/settings/network side effects

The envelope is a normalized contract consumed by later orchestration phases.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.apps.modes.mode_ids import normalize_mode_id
from backend.apps.swarms.context_clarification import infer_creation_type, resolve_context_clarification


KNOWN_INPUT_MODALITIES = {"text", "image", "file", "multimodal", "unknown"}
KNOWN_RISK_PROFILES = {"low", "medium", "high", "unknown"}
KNOWN_SIDE_EFFECT_POLICIES = {"none", "requires_approval", "blocked", "unknown"}
KNOWN_AUTONOMY_LEVELS = {"direct", "supervised", "approval_required", "unknown"}


def _as_text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _clean_list(value: Any, *, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _as_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text[:400])
        if len(result) >= limit:
            break
    return result


def _clean_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def infer_input_modality(*, user_message: str, available_context: dict[str, Any] | None = None) -> str:
    context = available_context if isinstance(available_context, dict) else {}
    has_image = bool(context.get("image") or context.get("images") or context.get("image_asset_pointer"))
    has_file = bool(context.get("file") or context.get("files") or context.get("artifact_refs") or context.get("attachments"))
    has_text = bool(_as_text(user_message))

    if has_image and (has_file or has_text):
        return "multimodal"
    if has_image:
        return "image"
    if has_file and has_text:
        return "multimodal"
    if has_file:
        return "file"
    if has_text:
        return "text"
    return "unknown"


def infer_side_effect_policy(*, user_message: str, available_context: dict[str, Any] | None = None) -> str:
    text = _as_text(user_message).lower()
    context = available_context if isinstance(available_context, dict) else {}

    if context.get("side_effect_policy") in KNOWN_SIDE_EFFECT_POLICIES:
        return str(context["side_effect_policy"])

    blocked_terms = {
        "borrar todo",
        "eliminar todo",
        "delete everything",
        "format",
        "destruir",
    }
    approval_terms = {
        "aplica",
        "aplicar",
        "apply",
        "commit",
        "push",
        "instala",
        "instalar",
        "install",
        "ejecuta",
        "ejecutar",
        "run command",
        "modifica",
        "modificar",
        "escribe archivo",
        "write file",
        "borra",
        "borrar",
        "delete",
        "rollback",
    }

    if any(term in text for term in blocked_terms):
        return "blocked"
    if any(term in text for term in approval_terms):
        return "requires_approval"
    return "none"


def infer_risk_profile(*, side_effect_policy: str, clarification: dict[str, Any]) -> str:
    if side_effect_policy == "blocked":
        return "high"
    if side_effect_policy == "requires_approval":
        return "medium"

    clarification_risk = _as_text(clarification.get("risk"), fallback="low").lower()
    if clarification_risk in KNOWN_RISK_PROFILES:
        return clarification_risk
    return "low"


def infer_autonomy_level(*, side_effect_policy: str, risk_profile: str) -> str:
    if side_effect_policy in {"blocked", "requires_approval"}:
        return "approval_required"
    if risk_profile in {"medium", "high"}:
        return "supervised"
    return "direct"


def default_clarification_budget(*, mode: str, risk_profile: str) -> int:
    if risk_profile == "high":
        return 1
    if mode == "app_builder":
        return 3
    if mode in {"plan", "debug", "skill_builder"}:
        return 2
    return 1


@dataclass(frozen=True)
class TaskEnvelope:
    objective: str
    mode: str = "ask"
    creation_type: str = "unknown"
    input_modality: str = "unknown"
    artifact_refs: list[str] = field(default_factory=list)
    risk_profile: str = "low"
    side_effect_policy: str = "none"
    clarification_budget: int = 1
    success_criteria: list[str] = field(default_factory=list)
    autonomy_level: str = "direct"
    requested_outputs: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    model_requirements: dict[str, Any] = field(default_factory=dict)
    trace_context: dict[str, Any] = field(default_factory=dict)
    clarification: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_task_envelope_from_swarm_input(
    *,
    user_message: str,
    swarm_mode: str | None = None,
    intent: str | None = None,
    available_context: dict[str, Any] | None = None,
    requested_outputs: list[str] | None = None,
    constraints: list[str] | None = None,
    success_criteria: list[str] | None = None,
    model_requirements: dict[str, Any] | None = None,
    trace_context: dict[str, Any] | None = None,
) -> TaskEnvelope:
    """Build a normalized, side-effect-free task envelope from Swarm input."""

    mode = normalize_mode_id(swarm_mode or intent, default="ask")
    context = available_context if isinstance(available_context, dict) else {}
    objective = _as_text(user_message, fallback=_as_text(context.get("objective"), fallback=""))

    clarification = resolve_context_clarification(
        user_message=user_message,
        swarm_mode=mode,
        intent=intent,
        available_context=context,
    )

    creation_type = _as_text(clarification.get("creation_type"), fallback=infer_creation_type(user_message))
    input_modality = infer_input_modality(user_message=user_message, available_context=context)
    artifact_refs = _clean_list(context.get("artifact_refs") or context.get("files") or context.get("attachments"))
    side_effect_policy = infer_side_effect_policy(user_message=user_message, available_context=context)
    risk_profile = infer_risk_profile(side_effect_policy=side_effect_policy, clarification=clarification)
    autonomy_level = infer_autonomy_level(side_effect_policy=side_effect_policy, risk_profile=risk_profile)

    budget_value = context.get("clarification_budget")
    try:
        clarification_budget = int(budget_value)
    except Exception:
        clarification_budget = default_clarification_budget(mode=mode, risk_profile=risk_profile)

    clarification_budget = max(0, min(clarification_budget, 5))

    envelope_trace_context = {
        "source": "task_envelope",
        "mode": mode,
        "clarification_reason": clarification.get("reason"),
        "needs_clarification": bool(clarification.get("needs_clarification")),
    }
    envelope_trace_context.update(_clean_dict(trace_context))

    return TaskEnvelope(
        objective=objective,
        mode=mode,
        creation_type=creation_type,
        input_modality=input_modality,
        artifact_refs=artifact_refs,
        risk_profile=risk_profile,
        side_effect_policy=side_effect_policy,
        clarification_budget=clarification_budget,
        success_criteria=_clean_list(success_criteria or context.get("success_criteria")),
        autonomy_level=autonomy_level,
        requested_outputs=_clean_list(requested_outputs or context.get("requested_outputs")),
        constraints=_clean_list(constraints or context.get("constraints")),
        model_requirements=_clean_dict(model_requirements or context.get("model_requirements")),
        trace_context=envelope_trace_context,
        clarification=clarification,
    )


def dump_task_envelope(envelope: TaskEnvelope | dict[str, Any]) -> dict[str, Any]:
    if isinstance(envelope, TaskEnvelope):
        return envelope.as_dict()
    return dict(envelope) if isinstance(envelope, dict) else {}
