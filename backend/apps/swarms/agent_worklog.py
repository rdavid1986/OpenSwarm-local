
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

WORKLOG_VERSION = "openswarm.agent_worklog.v1"
STATUSES = {"planned", "running", "completed", "blocked", "failed", "skipped"}


def build_empty_agent_worklog(**kwargs: Any) -> dict[str, Any]:
    status = _text(kwargs.get("status"), "planned")
    if status not in STATUSES:
        status = "planned"
    entry = {
        "worklog_kind": "agent_worklog_entry",
        "worklog_version": WORKLOG_VERSION,
        "swarm_id": _text(kwargs.get("swarm_id")),
        "agent_id": _text(kwargs.get("agent_id")),
        "miniagent_id": _text(kwargs.get("miniagent_id")),
        "task_id": _text(kwargs.get("task_id")),
        "task_title": _text(kwargs.get("task_title"), "Untitled task"),
        "assigned_skill_id": _text(kwargs.get("assigned_skill_id")),
        "assigned_skill_name": _text(kwargs.get("assigned_skill_name")),
        "assigned_skill_reason": _text(kwargs.get("assigned_skill_reason"), "No skill assignment reason recorded."),
        "context_used": _list(kwargs.get("context_used")),
        "memory_context_used": _list(kwargs.get("memory_context_used")),
        "files_inspected": _list(kwargs.get("files_inspected")),
        "actions_executed": _list(kwargs.get("actions_executed")),
        "commands_executed": _list(kwargs.get("commands_executed")),
        "artifacts_created": _list(kwargs.get("artifacts_created")),
        "evidence_refs": _list(kwargs.get("evidence_refs")),
        "decisions": _list(kwargs.get("decisions")),
        "blockers": _list(kwargs.get("blockers")),
        "validation_results": _list(kwargs.get("validation_results")),
        "handoff_summary": _text(kwargs.get("handoff_summary"), "No handoff summary recorded yet."),
        "next_agent_inputs": _list(kwargs.get("next_agent_inputs")),
        "events": _list(kwargs.get("events")),
        "created_at": _text(kwargs.get("created_at"), _now()),
        "status": status,
    }
    return _safe(entry)


def build_agent_worklog_entry(**kwargs: Any) -> dict[str, Any]:
    return build_empty_agent_worklog(**kwargs)


def append_agent_worklog_event(entry: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(_safe(entry or {}))
    events = _list(updated.get("events"))
    safe_event = _safe({"event_id": str(event.get("event_id") or uuid4().hex), "created_at": event.get("created_at") or _now(), **(event or {})})
    events.append(safe_event)
    updated["events"] = events
    return updated


def summarize_agent_worklog_entry(entry: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(entry or {}))
    return {
        "summary_kind": "agent_worklog_summary",
        "swarm_id": snapshot.get("swarm_id", ""),
        "agent_id": snapshot.get("agent_id", ""),
        "miniagent_id": snapshot.get("miniagent_id", ""),
        "task_id": snapshot.get("task_id", ""),
        "task_title": snapshot.get("task_title", "Untitled task"),
        "assigned_skill_name": snapshot.get("assigned_skill_name", ""),
        "status": snapshot.get("status", "planned"),
        "context_count": len(_list(snapshot.get("context_used"))) + len(_list(snapshot.get("memory_context_used"))),
        "action_count": len(_list(snapshot.get("actions_executed"))),
        "command_count": len(_list(snapshot.get("commands_executed"))),
        "evidence_count": len(_list(snapshot.get("evidence_refs"))),
        "blocker_count": len(_list(snapshot.get("blockers"))),
        "handoff_summary": snapshot.get("handoff_summary", "No handoff summary recorded yet."),
    }
