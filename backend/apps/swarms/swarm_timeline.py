
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

TIMELINE_EVENT_TYPES = {
    "context_retrieval", "task_planned", "skill_assigned", "miniagent_started", "action_executed",
    "evidence_added", "handoff_created", "validation_completed", "blocker_found", "reviewer_summary",
    "integrator_summary", "swarm_completed",
}
SEVERITIES = {"info", "warning", "error"}


def build_swarm_timeline_event(**kwargs: Any) -> dict[str, Any]:
    event_type = _text(kwargs.get("event_type"), "context_retrieval")
    if event_type not in TIMELINE_EVENT_TYPES:
        event_type = "context_retrieval"
    severity = _text(kwargs.get("severity"), "info")
    if severity not in SEVERITIES:
        severity = "info"
    return _safe({
        "event_id": _text(kwargs.get("event_id"), uuid4().hex),
        "event_type": event_type,
        "title": _text(kwargs.get("title"), event_type.replace("_", " ").title()),
        "summary": _text(kwargs.get("summary"), "No summary provided."),
        "agent_id": _text(kwargs.get("agent_id")),
        "miniagent_id": _text(kwargs.get("miniagent_id")),
        "task_id": _text(kwargs.get("task_id")),
        "skill_id": _text(kwargs.get("skill_id")),
        "evidence_refs": _list(kwargs.get("evidence_refs")),
        "artifact_refs": _list(kwargs.get("artifact_refs")),
        "created_at": _text(kwargs.get("created_at"), _now()),
        "severity": severity,
        "visible_to_user": bool(kwargs.get("visible_to_user", True)),
        "internal_only": bool(kwargs.get("internal_only", False)),
    })


def build_swarm_timeline(*, swarm_id: str = "", events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sorted_events = sorted([deepcopy(_safe(e)) for e in (events or [])], key=lambda e: str(e.get("created_at", "")))
    return {"timeline_kind": "swarm_timeline", "swarm_id": swarm_id, "events": sorted_events, "created_at": _now()}


def append_swarm_timeline_event(timeline: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(_safe(timeline or {"timeline_kind": "swarm_timeline", "events": []}))
    events = _list(updated.get("events"))
    events.append(deepcopy(_safe(event)))
    updated["events"] = sorted(events, key=lambda e: str(e.get("created_at", "")))
    return updated


def summarize_swarm_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(timeline or {}))
    events = _list(snapshot.get("events"))
    return {
        "summary_kind": "swarm_timeline_summary",
        "swarm_id": snapshot.get("swarm_id", ""),
        "event_count": len(events),
        "event_types": [event.get("event_type") for event in events],
        "evidence_count": sum(len(_list(event.get("evidence_refs"))) for event in events),
        "artifact_count": sum(len(_list(event.get("artifact_refs"))) for event in events),
        "error_count": sum(1 for event in events if event.get("severity") == "error"),
        "warning_count": sum(1 for event in events if event.get("severity") == "warning"),
    }
