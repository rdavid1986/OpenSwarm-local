from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from backend.apps.swarms.swarm_timeline import build_swarm_timeline_event


SENSITIVE_KEYS = {
    "chain_of_thought",
    "cot",
    "private_reasoning",
    "hidden_reasoning",
    "prompt",
    "raw_prompt",
    "raw_response",
    "response",
    "secret",
    "token",
    "api_key",
    "password",
    "credential",
    "authorization",
    "cookie",
}
HANDOFF_VERSION = "openswarm.miniagent_handoff.v1"
HANDOFF_CONTEXT_VERSION = "openswarm.miniagent_handoff_context.v1"
HANDOFF_STORE_VERSION = "openswarm.miniagent_handoff_store.v1"
HANDOFF_STATUSES = {"draft", "ready", "blocked", "received", "used", "invalid"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").lower().replace("-", "_")
    if normalized in {"contains_private_reasoning"}:
        return False
    return normalized in SENSITIVE_KEYS or any(
        token in normalized
        for token in (
            "chain_of_thought",
            "private_reasoning",
            "hidden_reasoning",
            "raw_prompt",
            "raw_response",
            "secret",
            "token",
            "api_key",
            "password",
            "credential",
            "authorization",
            "cookie",
        )
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if not _is_sensitive_key(k)}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, str):
        return value[:4000].rstrip() + ("..." if len(value) > 4000 else "")
    return value


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return _safe(value)
    if isinstance(value, tuple):
        return _safe(list(value))
    return [_safe(value)]


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _dedupe(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    output: list[Any] = []
    for value in values:
        safe_value = _safe(value)
        key = repr(safe_value)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(safe_value)
    return output


def _handoff_identity(handoff: dict[str, Any]) -> str:
    return _text(
        handoff.get("handoff_id")
        or "|".join(
            [
                _text(handoff.get("source_agent_id")),
                _text(handoff.get("target_agent_id")),
                _text(handoff.get("source_task_id")),
                _text(handoff.get("target_task_id")),
                _text(handoff.get("created_at")),
            ]
        ),
        uuid4().hex,
    )


def normalize_handoff_status(value: Any) -> str:
    text = _text(value, "draft").lower()
    return text if text in HANDOFF_STATUSES else "draft"


def build_miniagent_handoff(**kwargs: Any) -> dict[str, Any]:
    blockers = _list(kwargs.get("blockers"))
    status = normalize_handoff_status(kwargs.get("status") or ("blocked" if blockers else "ready"))
    handoff_id = _text(kwargs.get("handoff_id"), uuid4().hex)

    return _safe({
        "handoff_kind": "miniagent_handoff",
        "handoff_version": HANDOFF_VERSION,
        "handoff_id": handoff_id,
        "status": status,
        "source_agent_id": _text(kwargs.get("source_agent_id")),
        "target_agent_id": _text(kwargs.get("target_agent_id")),
        "source_task_id": _text(kwargs.get("source_task_id")),
        "target_task_id": _text(kwargs.get("target_task_id")),
        "completed_work_summary": _text(kwargs.get("completed_work_summary"), "No completed work summary provided."),
        "evidence_refs": _dedupe(_list(kwargs.get("evidence_refs"))),
        "artifacts": _dedupe(_list(kwargs.get("artifacts"))),
        "files_changed": _dedupe(_list(kwargs.get("files_changed"))),
        "files_inspected": _dedupe(_list(kwargs.get("files_inspected"))),
        "decisions": _dedupe(_list(kwargs.get("decisions"))),
        "assumptions": _dedupe(_list(kwargs.get("assumptions"))),
        "blockers": _dedupe(blockers),
        "risks": _dedupe(_list(kwargs.get("risks"))),
        "recommended_next_steps": _dedupe(_list(kwargs.get("recommended_next_steps"))),
        "required_context_for_next_agent": _dedupe(_list(kwargs.get("required_context_for_next_agent"))),
        "skill_context_for_next_agent": _dedupe(_list(kwargs.get("skill_context_for_next_agent"))),
        "validation_summary": _text(kwargs.get("validation_summary"), "Validation not recorded."),
        "created_at": _text(kwargs.get("created_at"), _now()),
        "received_at": _text(kwargs.get("received_at")),
        "used_at": _text(kwargs.get("used_at")),
        "metadata": _safe(kwargs.get("metadata") if isinstance(kwargs.get("metadata"), dict) else {}),
        "can_execute": False,
        "can_mutate_state": False,
        "contains_private_reasoning": False,
    })


def summarize_miniagent_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(handoff or {}))
    return {
        "summary_kind": "miniagent_handoff_summary",
        "handoff_id": snapshot.get("handoff_id", ""),
        "status": snapshot.get("status", "draft"),
        "source_agent_id": snapshot.get("source_agent_id", ""),
        "target_agent_id": snapshot.get("target_agent_id", ""),
        "source_task_id": snapshot.get("source_task_id", ""),
        "target_task_id": snapshot.get("target_task_id", ""),
        "completed_work_summary": snapshot.get("completed_work_summary", "No completed work summary provided."),
        "evidence_count": len(_list(snapshot.get("evidence_refs"))),
        "artifact_count": len(_list(snapshot.get("artifacts"))),
        "decision_count": len(_list(snapshot.get("decisions"))),
        "blocker_count": len(_list(snapshot.get("blockers"))),
        "validation_summary": snapshot.get("validation_summary", "Validation not recorded."),
    }


def validate_miniagent_handoff(
    handoff: dict[str, Any],
    *,
    require_target: bool = True,
    require_evidence: bool = False,
    require_next_inputs: bool = True,
) -> dict[str, Any]:
    snapshot = deepcopy(_safe(handoff or {}))
    missing: list[str] = []
    warnings: list[str] = []
    required_actions: list[str] = []

    if snapshot.get("handoff_kind") != "miniagent_handoff":
        missing.append("handoff_kind")
    if snapshot.get("handoff_version") != HANDOFF_VERSION:
        warnings.append("handoff_version_mismatch")
    if require_target and not _text(snapshot.get("target_agent_id")) and not _text(snapshot.get("target_task_id")):
        missing.append("target_agent_or_task")
    if not _text(snapshot.get("completed_work_summary")) or snapshot.get("completed_work_summary") == "No completed work summary provided.":
        missing.append("completed_work_summary")
    if require_evidence and not _list(snapshot.get("evidence_refs")):
        missing.append("evidence_refs")
    if require_next_inputs and not any(
        _list(snapshot.get(key))
        for key in ("recommended_next_steps", "required_context_for_next_agent", "skill_context_for_next_agent")
    ):
        missing.append("next_agent_inputs")

    blockers = _list(snapshot.get("blockers"))
    if blockers:
        warnings.append("handoff_contains_blockers")
        required_actions.append("resolve_or_acknowledge_handoff_blockers")

    if missing:
        status = "blocked"
        required_actions.append("complete_handoff_required_fields")
    elif blockers:
        status = "blocked"
    else:
        status = "valid"

    return _safe({
        "validation_kind": "miniagent_handoff_validation",
        "handoff_id": snapshot.get("handoff_id") or _handoff_identity(snapshot),
        "status": status,
        "valid": status == "valid",
        "missing_fields": _dedupe(missing),
        "warnings": _dedupe(warnings),
        "required_actions": _dedupe(required_actions),
        "blocker_count": len(blockers),
        "evidence_count": len(_list(snapshot.get("evidence_refs"))),
        "decision_count": len(_list(snapshot.get("decisions"))),
        "can_continue_without_review": status == "valid",
        "created_at": _now(),
    })


def merge_handoffs_for_agent(handoffs: list[dict[str, Any]], target_agent_id: str | None = None) -> list[dict[str, Any]]:
    merged = []
    seen: set[str] = set()
    for handoff in handoffs or []:
        safe_handoff = deepcopy(_safe(handoff))
        if target_agent_id and safe_handoff.get("target_agent_id") != target_agent_id:
            continue
        identity = _handoff_identity(safe_handoff)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(safe_handoff)
    return merged


def build_handoff_context_for_next_agent(handoffs: list[dict[str, Any]], target_agent_id: str | None = None) -> dict[str, Any]:
    selected = merge_handoffs_for_agent(handoffs, target_agent_id)
    validations = [validate_miniagent_handoff(handoff, require_target=False, require_evidence=False, require_next_inputs=False) for handoff in selected]
    blockers = [item for handoff in selected for item in _list(handoff.get("blockers"))]
    required_actions = [action for validation in validations for action in _list(validation.get("required_actions"))]

    return _safe({
        "context_kind": "miniagent_handoff_context",
        "context_version": HANDOFF_CONTEXT_VERSION,
        "status": "blocked" if blockers or required_actions else "ready",
        "target_agent_id": target_agent_id or "",
        "handoff_count": len(selected),
        "handoff_ids": [_handoff_identity(handoff) for handoff in selected],
        "summaries": [handoff.get("completed_work_summary", "") for handoff in selected],
        "evidence_refs": _dedupe([ref for handoff in selected for ref in _list(handoff.get("evidence_refs"))]),
        "artifact_refs": _dedupe([ref for handoff in selected for ref in _list(handoff.get("artifacts"))]),
        "decisions": _dedupe([item for handoff in selected for item in _list(handoff.get("decisions"))]),
        "blockers": _dedupe(blockers),
        "risks": _dedupe([item for handoff in selected for item in _list(handoff.get("risks"))]),
        "required_context": _dedupe([item for handoff in selected for item in _list(handoff.get("required_context_for_next_agent"))]),
        "skill_context": _dedupe([item for handoff in selected for item in _list(handoff.get("skill_context_for_next_agent"))]),
        "recommended_next_steps": _dedupe([item for handoff in selected for item in _list(handoff.get("recommended_next_steps"))]),
        "validations": validations,
        "required_actions": _dedupe(required_actions),
        "can_inject_into_next_agent": not blockers and not required_actions,
        "contains_private_reasoning": False,
    })


def build_handoff_context_section(context: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(context or {}))
    content_parts = []
    for summary in _list(snapshot.get("summaries")):
        if _text(summary):
            content_parts.append(f"Summary: {_text(summary)}")
    for decision in _list(snapshot.get("decisions")):
        content_parts.append(f"Decision: {_text(decision) if not isinstance(decision, dict) else _text(decision.get('summary'), repr(decision))}")
    for blocker in _list(snapshot.get("blockers")):
        content_parts.append(f"Blocker: {_text(blocker) if not isinstance(blocker, dict) else _text(blocker.get('summary'), repr(blocker))}")
    for item in _list(snapshot.get("required_context")):
        content_parts.append(f"Required context: {_text(item) if not isinstance(item, dict) else repr(item)}")
    if not content_parts:
        content_parts.append("No handoff context available.")

    return _safe({
        "kind": "miniagent_handoff_context",
        "source": "HandoffCore",
        "content": "\n".join(content_parts),
        "metadata": {
            "context_kind": snapshot.get("context_kind"),
            "context_version": snapshot.get("context_version"),
            "target_agent_id": snapshot.get("target_agent_id"),
            "handoff_count": snapshot.get("handoff_count", 0),
            "handoff_ids": snapshot.get("handoff_ids", []),
            "evidence_refs": snapshot.get("evidence_refs", []),
            "artifact_refs": snapshot.get("artifact_refs", []),
            "blocker_count": len(_list(snapshot.get("blockers"))),
            "injection_authorizes_actions": False,
            "can_execute": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
    })


def build_blocked_handoff_state(handoff: dict[str, Any], validation: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = deepcopy(_safe(handoff or {}))
    validation_data = deepcopy(_safe(validation or validate_miniagent_handoff(snapshot)))
    return _safe({
        "blocked_kind": "miniagent_handoff_blocked_state",
        "handoff_id": snapshot.get("handoff_id") or _handoff_identity(snapshot),
        "status": "blocked",
        "source_agent_id": snapshot.get("source_agent_id", ""),
        "target_agent_id": snapshot.get("target_agent_id", ""),
        "source_task_id": snapshot.get("source_task_id", ""),
        "target_task_id": snapshot.get("target_task_id", ""),
        "missing_fields": validation_data.get("missing_fields", []),
        "blockers": _list(snapshot.get("blockers")),
        "required_actions": _dedupe(_list(validation_data.get("required_actions")) or ["review_handoff_blocker"]),
        "can_continue": False,
        "can_inject_into_next_agent": False,
        "created_at": _now(),
    })


def persist_miniagent_handoff_state(state: dict[str, Any] | None, handoff: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(_safe(state or {}))
    handoffs = [deepcopy(_safe(item)) for item in _list(updated.get("handoffs")) if isinstance(item, dict)]
    safe_handoff = deepcopy(_safe(handoff or {}))
    identity = _handoff_identity(safe_handoff)

    replaced = False
    next_handoffs: list[dict[str, Any]] = []
    for item in handoffs:
        if _handoff_identity(item) == identity:
            next_handoffs.append(safe_handoff)
            replaced = True
        else:
            next_handoffs.append(item)
    if not replaced:
        next_handoffs.append(safe_handoff)

    updated["handoff_store_kind"] = HANDOFF_STORE_VERSION
    updated["handoffs"] = next_handoffs
    updated["handoff_count"] = len(next_handoffs)
    updated["updated_at"] = _now()
    return updated


def build_handoff_timeline_events(handoff: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = deepcopy(_safe(handoff or {}))
    handoff_id = snapshot.get("handoff_id") or _handoff_identity(snapshot)
    evidence_refs = _list(snapshot.get("evidence_refs"))
    artifact_refs = _list(snapshot.get("artifacts"))
    base = {
        "agent_id": snapshot.get("source_agent_id"),
        "miniagent_id": snapshot.get("source_agent_id"),
        "task_id": snapshot.get("source_task_id"),
        "evidence_refs": evidence_refs,
        "artifact_refs": artifact_refs,
        "visible_to_user": True,
        "internal_only": False,
    }

    created = build_swarm_timeline_event(
        event_type="handoff_created",
        title="MiniAgent handoff created",
        summary=snapshot.get("completed_work_summary") or "MiniAgent handoff created.",
        severity="warning" if snapshot.get("blockers") else "info",
        **base,
    )
    received = build_swarm_timeline_event(
        event_type="handoff_received",
        title="MiniAgent handoff received",
        summary=f"Handoff {handoff_id} prepared for target {snapshot.get('target_agent_id') or snapshot.get('target_task_id') or 'unknown target'}.",
        agent_id=snapshot.get("target_agent_id"),
        miniagent_id=snapshot.get("target_agent_id"),
        task_id=snapshot.get("target_task_id"),
        evidence_refs=evidence_refs,
        artifact_refs=artifact_refs,
        severity="warning" if snapshot.get("blockers") else "info",
        visible_to_user=True,
        internal_only=False,
    )
    used = build_swarm_timeline_event(
        event_type="handoff_used",
        title="MiniAgent handoff used",
        summary=f"Handoff {handoff_id} was made available as next-agent context.",
        agent_id=snapshot.get("target_agent_id"),
        miniagent_id=snapshot.get("target_agent_id"),
        task_id=snapshot.get("target_task_id"),
        evidence_refs=evidence_refs,
        artifact_refs=artifact_refs,
        severity="warning" if snapshot.get("blockers") else "info",
        visible_to_user=True,
        internal_only=False,
    )

    return _safe([
        {**created, "handoff_id": handoff_id},
        {**received, "handoff_id": handoff_id},
        {**used, "handoff_id": handoff_id},
    ])


def attach_handoff_context_to_metadata(metadata: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(_safe(metadata or {}))
    updated["handoff_context"] = deepcopy(_safe(context or {}))
    return updated
