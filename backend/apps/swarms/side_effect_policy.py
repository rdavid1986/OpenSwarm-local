from __future__ import annotations

"""Human-gate side effect policy contract.

Side effects are not executed here. This module only normalizes policy decisions
and keeps the policy state side-effect free.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


KNOWN_SIDE_EFFECT_DECISIONS = {"none", "requires_approval", "blocked", "unknown"}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "as_dict") and callable(value.as_dict):
        candidate = value.as_dict()
        return dict(candidate) if isinstance(candidate, dict) else {}
    return {}


@dataclass(slots=True)
class SideEffectPolicy:
    policy_id: str
    decision: str = "unknown"
    blocked: bool = False
    requires_approval: bool = False
    reason: str = ""
    approval_id: str | None = None
    policy_matrix_ref: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    task_envelope: dict[str, Any] = field(default_factory=dict)
    source: str = "task_envelope"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_side_effect_policy_from_task_envelope(
    task_envelope: dict[str, Any] | Any,
    *,
    policy_matrix_ref: str | None = None,
    approval_id: str | None = None,
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
) -> SideEffectPolicy:
    envelope = _as_dict(task_envelope)
    decision = str(envelope.get("side_effect_policy") or "unknown").strip().lower()
    if decision not in KNOWN_SIDE_EFFECT_DECISIONS:
        decision = "unknown"

    blocked = decision == "blocked"
    requires_approval = decision == "requires_approval"

    reason = str(
        envelope.get("side_effect_reason")
        or envelope.get("risk_reason")
        or envelope.get("clarification_reason")
        or envelope.get("reason")
        or ""
    ).strip()

    policy_id = str(
        envelope.get("task_id")
        or envelope.get("policy_id")
        or envelope.get("trace_id")
        or envelope.get("objective")
        or "side-effect-policy"
    ).strip() or "side-effect-policy"

    return SideEffectPolicy(
        policy_id=policy_id,
        decision=decision,
        blocked=blocked,
        requires_approval=requires_approval,
        reason=reason,
        approval_id=approval_id or _as_dict(envelope.get("pending_action")).get("approval_id"),
        policy_matrix_ref=policy_matrix_ref or _as_dict(envelope.get("pending_action")).get("policy_matrix_ref"),
        tool_name=tool_name,
        tool_input=dict(tool_input or {}),
        task_envelope=envelope,
    )


def dump_side_effect_policy(policy: SideEffectPolicy | dict[str, Any]) -> dict[str, Any]:
    if isinstance(policy, SideEffectPolicy):
        return policy.as_dict()
    if isinstance(policy, dict):
        return dict(policy)
    raise TypeError("Unsupported side effect policy payload")
