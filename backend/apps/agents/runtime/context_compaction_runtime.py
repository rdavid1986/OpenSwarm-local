"""Side-effect-free context compaction runtime contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

ALLOWED_COMPACTION_STATUSES = {
    "normal",
    "near_limit",
    "compacting",
    "compacted",
    "compaction_failed",
    "recovery_required",
    "skipped",
}
SENSITIVE_KEYS = {
    "prompt",
    "raw_prompt",
    "response",
    "raw_response",
    "content",
    "body",
    "text",
    "raw",
    "chain_of_thought",
    "cot",
    "private_reasoning",
    "hidden_reasoning",
    "secret",
    "token",
    "api_key",
    "apikey",
    "password",
    "credential",
    "credentials",
    "authorization",
    "private_key",
}


@dataclass(frozen=True)
class ContextCompactionState:
    compaction_id: str
    session_id: str | None = None
    conversation_id: str | None = None
    swarm_id: str | None = None
    agent_id: str | None = None
    miniagent_id: str | None = None
    status: str = "normal"
    reason: str = "not_needed"
    compacted_through_msg_id: str | None = None
    compacted_message_count: int = 0
    original_message_count: int = 0
    preserved_recent_message_count: int = 0
    trigger_ratio: float | None = None
    context_limit: int | None = None
    estimated_input_tokens: int | None = None
    created_at: str = ""
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextCompactionPinnedContext:
    pinned_ids: list[str] = field(default_factory=list)
    output_ids: list[str] = field(default_factory=list)
    candidate_iteration_ids: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    agent_ids: list[str] = field(default_factory=list)
    swarm_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    handoff_refs: list[str] = field(default_factory=list)
    validation_refs: list[str] = field(default_factory=list)
    decision_refs: list[str] = field(default_factory=list)
    blocker_refs: list[str] = field(default_factory=list)
    approval_refs: list[str] = field(default_factory=list)
    selected_model: str | None = None
    provider_id: str | None = None
    policy_gates: list[str] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextCompactionSummary:
    summary_id: str
    status: str
    summary_text: str
    summary_kind: str = "evidence_preserving_context_compaction"
    compacted_through_msg_id: str | None = None
    source_message_ids: list[str] = field(default_factory=list)
    preserved_message_ids: list[str] = field(default_factory=list)
    pinned_context: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    handoff_refs: list[str] = field(default_factory=list)
    validation_refs: list[str] = field(default_factory=list)
    decision_refs: list[str] = field(default_factory=list)
    blocker_refs: list[str] = field(default_factory=list)
    missing_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextCompactionLoopGuard:
    status: str
    last_compacted_through_msg_id: str | None = None
    requested_compacted_through_msg_id: str | None = None
    repeated_compaction_count: int = 0
    max_repeated_compactions: int = 2
    should_block: bool = False
    reason: str = "allowed"
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextCompactionRecovery:
    status: str
    reason: str
    preserved_refs: list[str] = field(default_factory=list)
    missing_refs: list[str] = field(default_factory=list)
    uncertain_refs: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_continue: bool = True
    should_pause: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(marker in normalized for marker in ("secret", "token", "password", "api_key", "credential", "authorization", "private_key"))


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if not _is_sensitive_key(k)}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return [_safe(v) for v in sorted(value, key=str)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "__dataclass_fields__"):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return _safe(deepcopy(value))
    return {}


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _add_unique(target: list[str], value: Any) -> None:
    values = value if isinstance(value, list) else list(value) if isinstance(value, tuple | set) else [value]
    for item in values:
        if isinstance(item, dict):
            candidate = item.get("ref") or item.get("id") or item.get("decision_id") or item.get("blocker_id") or item.get("approval_id")
        else:
            candidate = item
        text = _text(candidate)
        if text and text not in target:
            target.append(text)


def normalize_compaction_status(value: Any) -> str:
    normalized = _text(value).lower()
    return normalized if normalized in ALLOWED_COMPACTION_STATUSES else "normal"


def estimate_compaction_token_count(value: Any, chars_per_token: int = 4) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        divisor = max(1, int(chars_per_token or 4))
        return max(1, (len(value) + divisor - 1) // divisor) if value else 0
    if isinstance(value, dict):
        return sum(estimate_compaction_token_count(k, chars_per_token) + estimate_compaction_token_count(v, chars_per_token) for k, v in _safe(value).items())
    if isinstance(value, (list, tuple, set)):
        return sum(estimate_compaction_token_count(item, chars_per_token) for item in value)
    return estimate_compaction_token_count(str(value), chars_per_token)


def _walk(payload: Any):
    if isinstance(payload, dict):
        safe = _safe(payload)
        yield safe
        for value in safe.values():
            yield from _walk(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk(item)


def collect_pinned_context(payload: Any) -> ContextCompactionPinnedContext:
    pinned = ContextCompactionPinnedContext()
    data = asdict(pinned)
    selected_model = None
    provider_id = None
    for item in _walk(payload):
        for key, target in (
            ("pinned_id", "pinned_ids"), ("pinned_ids", "pinned_ids"),
            ("output_id", "output_ids"), ("output_ids", "output_ids"),
            ("candidate_iteration_id", "candidate_iteration_ids"), ("candidate_iteration_ids", "candidate_iteration_ids"), ("candidate_id", "candidate_iteration_ids"),
            ("task_id", "task_ids"), ("task_ids", "task_ids"),
            ("agent_id", "agent_ids"), ("agent_ids", "agent_ids"),
            ("swarm_id", "swarm_ids"), ("swarm_ids", "swarm_ids"),
            ("evidence_ref", "evidence_refs"), ("evidence_refs", "evidence_refs"), ("evidence_id", "evidence_refs"),
            ("handoff_ref", "handoff_refs"), ("handoff_refs", "handoff_refs"), ("handoff_id", "handoff_refs"),
            ("validation_ref", "validation_refs"), ("validation_refs", "validation_refs"), ("validation_id", "validation_refs"),
            ("decision_ref", "decision_refs"), ("decision_refs", "decision_refs"), ("decision_id", "decision_refs"), ("decisions", "decision_refs"),
            ("blocker_ref", "blocker_refs"), ("blocker_refs", "blocker_refs"), ("blocker_id", "blocker_refs"), ("blockers", "blocker_refs"),
            ("approval_ref", "approval_refs"), ("approval_refs", "approval_refs"), ("approval_id", "approval_refs"), ("approvals", "approval_refs"),
            ("policy_gate", "policy_gates"), ("policy_gates", "policy_gates"),
            ("safety_note", "safety_notes"), ("safety_notes", "safety_notes"),
        ):
            if key in item:
                _add_unique(data[target], item.get(key))
        selected_model = selected_model or _text(item.get("selected_model") or item.get("model")) or None
        provider_id = provider_id or _text(item.get("provider_id") or item.get("provider")) or None
    data["selected_model"] = selected_model
    data["provider_id"] = provider_id
    data["metadata"] = _safe({"source": "collect_pinned_context"})
    return ContextCompactionPinnedContext(**data)


def build_context_compaction_state(**kwargs: Any) -> ContextCompactionState:
    trigger_ratio = _float(kwargs.get("trigger_ratio"))
    original_count = _int(kwargs.get("original_message_count")) or len(kwargs.get("messages") or [])
    compacted_count = _int(kwargs.get("compacted_message_count")) or 0
    preserved_count = _int(kwargs.get("preserved_recent_message_count")) or 0
    status = normalize_compaction_status(kwargs.get("status"))
    warnings = list(kwargs.get("warnings") or [])
    required_actions = list(kwargs.get("required_actions") or [])
    if not kwargs.get("status"):
        if compacted_count > 0 or kwargs.get("compacted_through_msg_id"):
            status = "compacted"
        elif trigger_ratio is not None and trigger_ratio >= 0.65:
            status = "near_limit"
            warnings.append("context_near_compaction_threshold")
            required_actions.append("prepare_context_compaction")
        elif original_count == 0:
            status = "skipped"
        else:
            status = "normal"
    return ContextCompactionState(
        compaction_id=_text(kwargs.get("compaction_id")) or uuid4().hex,
        session_id=_text(kwargs.get("session_id")) or None,
        conversation_id=_text(kwargs.get("conversation_id")) or None,
        swarm_id=_text(kwargs.get("swarm_id")) or None,
        agent_id=_text(kwargs.get("agent_id")) or None,
        miniagent_id=_text(kwargs.get("miniagent_id")) or None,
        status=status,
        reason=_text(kwargs.get("reason")) or status,
        compacted_through_msg_id=_text(kwargs.get("compacted_through_msg_id")) or None,
        compacted_message_count=compacted_count,
        original_message_count=original_count,
        preserved_recent_message_count=preserved_count,
        trigger_ratio=trigger_ratio,
        context_limit=_int(kwargs.get("context_limit")),
        estimated_input_tokens=_int(kwargs.get("estimated_input_tokens")),
        created_at=_text(kwargs.get("created_at")) or _now(),
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(required_actions)),
        metadata=_safe(kwargs.get("metadata") if isinstance(kwargs.get("metadata"), dict) else {}),
    )


def build_evidence_preserving_summary(messages: list[dict[str, Any]] | None = None, *, compacted_through_msg_id: str | None = None, preserved_message_ids: list[str] | None = None, metadata: dict[str, Any] | None = None, **kwargs: Any) -> ContextCompactionSummary:
    source = [msg for msg in (messages or []) if isinstance(msg, dict)]
    pinned = collect_pinned_context({"messages": source, **(metadata or {}), **kwargs})
    pinned_data = _dump(pinned)
    source_ids = []
    for msg in source:
        _add_unique(source_ids, msg.get("id") or msg.get("message_id"))
    preserved_ids = []
    _add_unique(preserved_ids, preserved_message_ids or [])
    missing_refs: list[str] = []
    warnings: list[str] = []
    required_actions: list[str] = []

    evidence_count = _int(kwargs.get("evidence_count") or (metadata or {}).get("evidence_count"))
    if evidence_count and not pinned.evidence_refs:
        warnings.append("evidence_count_without_evidence_refs")
        missing_refs.append("evidence_refs")
    for field_name in ("output_ids", "candidate_iteration_ids", "task_ids"):
        if pinned_data.get(field_name) and not pinned.evidence_refs and not pinned.validation_refs and not pinned.handoff_refs:
            warnings.append(f"{field_name}_without_associated_refs")
            _add_unique(missing_refs, f"refs_for_{field_name}")

    if not source and not any(pinned_data.get(key) for key in ("evidence_refs", "handoff_refs", "validation_refs", "decision_refs", "blocker_refs")):
        status = "skipped"
        warnings.append("no_compaction_content")
    elif missing_refs:
        status = "recovery_required"
        required_actions.append("recover_missing_compaction_refs")
    else:
        status = "compacted"

    summary_parts = [
        f"Compacted {len(source_ids)} message(s) through {compacted_through_msg_id or 'unknown'}.",
        f"Preserved evidence={len(pinned.evidence_refs)}, handoffs={len(pinned.handoff_refs)}, decisions={len(pinned.decision_refs)}, blockers={len(pinned.blocker_refs)}, validations={len(pinned.validation_refs)}.",
    ]
    if pinned.selected_model or pinned.provider_id:
        summary_parts.append(f"Runtime model={pinned.selected_model or 'unknown'} provider={pinned.provider_id or 'unknown'}.")
    if warnings:
        summary_parts.append("Warnings require recovery review.")

    return ContextCompactionSummary(
        summary_id=_text(kwargs.get("summary_id")) or uuid4().hex,
        status=status,
        summary_text=" ".join(summary_parts),
        compacted_through_msg_id=_text(compacted_through_msg_id) or None,
        source_message_ids=source_ids,
        preserved_message_ids=preserved_ids,
        pinned_context=pinned_data,
        evidence_refs=pinned.evidence_refs,
        handoff_refs=pinned.handoff_refs,
        validation_refs=pinned.validation_refs,
        decision_refs=pinned.decision_refs,
        blocker_refs=pinned.blocker_refs,
        missing_refs=list(dict.fromkeys(missing_refs)),
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(required_actions)),
        metadata=_safe(metadata or {}),
    )


def build_compaction_loop_guard(*, last_compacted_through_msg_id: str | None = None, requested_compacted_through_msg_id: str | None = None, repeated_compaction_count: int = 0, max_repeated_compactions: int = 2, previous_status: str | None = None, force: bool = False, recovery_action: bool = False, metadata: dict[str, Any] | None = None) -> ContextCompactionLoopGuard:
    repeated = _int(repeated_compaction_count) or 0
    max_repeats = _int(max_repeated_compactions) or 2
    warnings: list[str] = []
    required: list[str] = []
    status = "allowed"
    reason = "allowed"
    should_block = False
    if normalize_compaction_status(previous_status) in {"compaction_failed", "recovery_required"} and not recovery_action:
        status = "blocked_recovery_required"
        reason = "previous_compaction_requires_recovery"
        should_block = True
        required.append("complete_compaction_recovery")
    elif requested_compacted_through_msg_id and requested_compacted_through_msg_id == last_compacted_through_msg_id and not force:
        status = "blocked_repeated_target"
        reason = "requested_target_already_compacted"
        should_block = True
        warnings.append("repeated_compaction_target")
        required.append("advance_compaction_target_or_force")
    elif repeated >= max_repeats and not force:
        status = "blocked_max_repeats"
        reason = "max_repeated_compactions_reached"
        should_block = True
        warnings.append("max_repeated_compactions_reached")
        required.append("manual_recovery_review")
    return ContextCompactionLoopGuard(status=status, last_compacted_through_msg_id=last_compacted_through_msg_id, requested_compacted_through_msg_id=requested_compacted_through_msg_id, repeated_compaction_count=repeated, max_repeated_compactions=max_repeats, should_block=should_block, reason=reason, warnings=warnings, required_actions=required, metadata=_safe(metadata or {}))


def build_compaction_recovery(*, required_refs: list[str] | None = None, preserved_refs: list[str] | None = None, uncertain_refs: list[str] | None = None, metadata: dict[str, Any] | None = None) -> ContextCompactionRecovery:
    required = []
    preserved = []
    uncertain = []
    _add_unique(required, required_refs or [])
    _add_unique(preserved, preserved_refs or [])
    _add_unique(uncertain, uncertain_refs or [])
    missing = [ref for ref in required if ref not in preserved]
    actions: list[str] = []
    if missing:
        status = "recovery_required"
        reason = "missing_critical_refs"
        actions.append("restore_or_relink_missing_refs")
        can_continue = False
        should_pause = True
    elif uncertain:
        status = "partial_recovery"
        reason = "uncertain_refs_require_review"
        actions.append("review_uncertain_refs")
        can_continue = True
        should_pause = False
    else:
        status = "ready"
        reason = "all_required_refs_preserved"
        can_continue = True
        should_pause = False
    return ContextCompactionRecovery(status=status, reason=reason, preserved_refs=preserved, missing_refs=missing, uncertain_refs=uncertain, required_actions=actions, can_continue=can_continue, should_pause=should_pause, metadata=_safe(metadata or {}))


def dump_context_compaction_state(state: ContextCompactionState | dict[str, Any]) -> dict[str, Any]:
    return _dump(state)


def dump_context_compaction_summary(summary: ContextCompactionSummary | dict[str, Any]) -> dict[str, Any]:
    return _dump(summary)


def dump_compaction_loop_guard(guard: ContextCompactionLoopGuard | dict[str, Any]) -> dict[str, Any]:
    return _dump(guard)


def dump_compaction_recovery(recovery: ContextCompactionRecovery | dict[str, Any]) -> dict[str, Any]:
    return _dump(recovery)


def build_context_compaction_trace_source(*, state: ContextCompactionState | dict[str, Any] | None = None, summary: ContextCompactionSummary | dict[str, Any] | None = None, loop_guard: ContextCompactionLoopGuard | dict[str, Any] | None = None, recovery: ContextCompactionRecovery | dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    state_data = dump_context_compaction_state(state) if state is not None else {}
    summary_data = dump_context_compaction_summary(summary) if summary is not None else {}
    guard_data = dump_compaction_loop_guard(loop_guard) if loop_guard is not None else {}
    recovery_data = dump_compaction_recovery(recovery) if recovery is not None else {}
    warnings: list[str] = []
    required: list[str] = []
    for item in (state_data, summary_data, guard_data, recovery_data):
        warnings.extend(item.get("warnings") or [])
        required.extend(item.get("required_actions") or [])
    return _safe({
        "source_kind": "context_compaction",
        "compaction_kind": "context_compaction_runtime",
        "state": state_data or None,
        "summary": summary_data or None,
        "pinned_context": summary_data.get("pinned_context") if summary_data else None,
        "loop_guard": guard_data or None,
        "recovery": recovery_data or None,
        "warnings": list(dict.fromkeys(warnings)),
        "required_actions": list(dict.fromkeys(required)),
        "metadata": metadata or {},
    })


def attach_context_compaction_to_metadata(metadata: dict[str, Any] | None, *, summary: ContextCompactionSummary | dict[str, Any] | None = None, state: ContextCompactionState | dict[str, Any] | None = None, recovery: ContextCompactionRecovery | dict[str, Any] | None = None) -> dict[str, Any]:
    clone = deepcopy(metadata) if isinstance(metadata, dict) else {}
    clone["context_compaction"] = _safe({
        "state": dump_context_compaction_state(state) if state is not None else None,
        "summary": dump_context_compaction_summary(summary) if summary is not None else None,
        "recovery": dump_compaction_recovery(recovery) if recovery is not None else None,
    })
    return _safe(clone)
