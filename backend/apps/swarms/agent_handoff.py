
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

SENSITIVE_KEYS = {"chain_of_thought", "cot", "private_reasoning", "hidden_reasoning"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if str(k) not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    return value


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return _safe(value)
    return [_safe(value)]


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default

HANDOFF_VERSION = "openswarm.miniagent_handoff.v1"


def build_miniagent_handoff(**kwargs: Any) -> dict[str, Any]:
    return _safe({
        "handoff_kind": "miniagent_handoff",
        "handoff_version": HANDOFF_VERSION,
        "source_agent_id": _text(kwargs.get("source_agent_id")),
        "target_agent_id": _text(kwargs.get("target_agent_id")),
        "source_task_id": _text(kwargs.get("source_task_id")),
        "target_task_id": _text(kwargs.get("target_task_id")),
        "completed_work_summary": _text(kwargs.get("completed_work_summary"), "No completed work summary provided."),
        "evidence_refs": _list(kwargs.get("evidence_refs")),
        "artifacts": _list(kwargs.get("artifacts")),
        "files_changed": _list(kwargs.get("files_changed")),
        "files_inspected": _list(kwargs.get("files_inspected")),
        "decisions": _list(kwargs.get("decisions")),
        "assumptions": _list(kwargs.get("assumptions")),
        "blockers": _list(kwargs.get("blockers")),
        "risks": _list(kwargs.get("risks")),
        "recommended_next_steps": _list(kwargs.get("recommended_next_steps")),
        "required_context_for_next_agent": _list(kwargs.get("required_context_for_next_agent")),
        "skill_context_for_next_agent": _list(kwargs.get("skill_context_for_next_agent")),
        "validation_summary": _text(kwargs.get("validation_summary"), "Validation not recorded."),
        "created_at": _text(kwargs.get("created_at"), _now()),
    })


def summarize_miniagent_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(handoff or {}))
    return {
        "summary_kind": "miniagent_handoff_summary",
        "source_agent_id": snapshot.get("source_agent_id", ""),
        "target_agent_id": snapshot.get("target_agent_id", ""),
        "completed_work_summary": snapshot.get("completed_work_summary", "No completed work summary provided."),
        "evidence_count": len(_list(snapshot.get("evidence_refs"))),
        "artifact_count": len(_list(snapshot.get("artifacts"))),
        "blocker_count": len(_list(snapshot.get("blockers"))),
        "validation_summary": snapshot.get("validation_summary", "Validation not recorded."),
    }


def merge_handoffs_for_agent(handoffs: list[dict[str, Any]], target_agent_id: str | None = None) -> list[dict[str, Any]]:
    merged = []
    for handoff in handoffs or []:
        safe_handoff = deepcopy(_safe(handoff))
        if target_agent_id and safe_handoff.get("target_agent_id") != target_agent_id:
            continue
        merged.append(safe_handoff)
    return merged


def build_handoff_context_for_next_agent(handoffs: list[dict[str, Any]], target_agent_id: str | None = None) -> dict[str, Any]:
    selected = merge_handoffs_for_agent(handoffs, target_agent_id)
    return {
        "context_kind": "miniagent_handoff_context",
        "target_agent_id": target_agent_id or "",
        "handoff_count": len(selected),
        "summaries": [handoff.get("completed_work_summary", "") for handoff in selected],
        "evidence_refs": [ref for handoff in selected for ref in _list(handoff.get("evidence_refs"))],
        "decisions": [item for handoff in selected for item in _list(handoff.get("decisions"))],
        "blockers": [item for handoff in selected for item in _list(handoff.get("blockers"))],
        "required_context": [item for handoff in selected for item in _list(handoff.get("required_context_for_next_agent"))],
        "skill_context": [item for handoff in selected for item in _list(handoff.get("skill_context_for_next_agent"))],
    }
