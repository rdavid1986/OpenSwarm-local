"""Privacy-safe ProcessTraceItem contract for backend trace dropdowns.

This module is intentionally side-effect-free: it does not persist, call models,
read files, or mutate runtime state. It only builds redacted dictionaries for UI
integration phases that run later.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.apps.runtime_timing import RuntimeTimerRecord, dump_runtime_timer

TRACE_KIND = "process_trace_item"
TRACE_VERSION = "openswarm.process_trace_item.v1"
PANEL_KIND = "process_trace_panel"
PANEL_VERSION = "openswarm.process_trace_panel.v1"

ALLOWED_KINDS = {
    "context",
    "memory",
    "skill",
    "mode",
    "action",
    "tool",
    "evidence",
    "handoff",
    "metric",
    "review",
    "browser",
    "config",
    "model",
    "timeline",
    "worklog",
    "validation",
    "summary",
    "unknown",
}
ALLOWED_STATUSES = {"planned", "running", "completed", "failed", "blocked", "skipped", "cancelled", "warning"}
SENSITIVE_KEYS = {
    "chain_of_thought",
    "cot",
    "private_reasoning",
    "hidden_reasoning",
    "prompt",
    "raw_prompt",
    "response",
    "raw_response",
    "content",
    "message",
    "messages",
    "body",
    "text",
    "raw",
    "request",
    "api_key",
    "apikey",
    "token",
    "password",
    "secret",
    "credential",
    "credentials",
    "private_key",
    "authorization",
    "cookie",
    "set-cookie",
    "set_cookie",
}
SENSITIVE_MARKERS = ("password", "secret", "token", "api_key", "apikey", "private_key", "authorization", "credential")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return _safe(value)
    if isinstance(value, tuple):
        return _safe(list(value))
    if isinstance(value, set):
        return _safe(sorted(value, key=str))
    return [_safe(value)]


def _normalize_kind(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_KINDS else "unknown"


def _normalize_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_STATUSES else "planned"


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(marker in normalized for marker in SENSITIVE_MARKERS)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if not _is_sensitive_key(k)}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return [_safe(v) for v in sorted(value, key=str)]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, parsed)


def build_process_trace_item(**kwargs: Any) -> dict[str, Any]:
    """Build one redacted ProcessTraceItem dictionary with safe defaults."""

    kind = _normalize_kind(kwargs.get("kind"))
    status = _normalize_status(kwargs.get("status"))
    created_at = _text(kwargs.get("created_at"), _now())
    return _safe({
        "trace_kind": TRACE_KIND,
        "trace_version": TRACE_VERSION,
        "trace_id": _text(kwargs.get("trace_id"), uuid4().hex),
        "kind": kind,
        "subsystem": _text(kwargs.get("subsystem"), "TraceCore"),
        "title": _text(kwargs.get("title"), kind.replace("_", " ").title() or "Trace item"),
        "summary": _text(kwargs.get("summary"), "No summary recorded."),
        "status": status,
        "started_at": _optional_text(kwargs.get("started_at")),
        "finished_at": _optional_text(kwargs.get("finished_at")),
        "duration_ms": _int_or_none(kwargs.get("duration_ms")),
        "icon_id": _text(kwargs.get("icon_id")),
        "badge": _text(kwargs.get("badge")),
        "details": _safe(dict(kwargs.get("details") or {})),
        "evidence_refs": _list(kwargs.get("evidence_refs")),
        "artifact_refs": _list(kwargs.get("artifact_refs")),
        "related_task_id": _text(kwargs.get("related_task_id")),
        "related_agent_id": _text(kwargs.get("related_agent_id")),
        "related_miniagent_id": _text(kwargs.get("related_miniagent_id")),
        "related_skill_id": _text(kwargs.get("related_skill_id")),
        "related_action_id": _text(kwargs.get("related_action_id")),
        "created_at": created_at,
        "visible_to_user": bool(kwargs.get("visible_to_user", True)),
        "internal_only": bool(kwargs.get("internal_only", False)),
        "metadata": _safe(dict(kwargs.get("metadata") or {})),
    })


def summarize_process_trace_item(item: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(item or {}))
    return {
        "summary_kind": "process_trace_item_summary",
        "trace_id": snapshot.get("trace_id", ""),
        "kind": snapshot.get("kind", "unknown"),
        "subsystem": snapshot.get("subsystem", "TraceCore"),
        "title": snapshot.get("title", "Trace item"),
        "summary": snapshot.get("summary", "No summary recorded."),
        "status": snapshot.get("status", "planned"),
        "duration_ms": snapshot.get("duration_ms"),
        "evidence_count": len(_list(snapshot.get("evidence_refs"))),
        "artifact_count": len(_list(snapshot.get("artifact_refs"))),
        "visible_to_user": bool(snapshot.get("visible_to_user", True)),
        "internal_only": bool(snapshot.get("internal_only", False)),
    }


def build_process_trace_panel(items: list[dict[str, Any]] | None = None, panel_title: str = "Process Trace") -> dict[str, Any]:
    safe_items = [deepcopy(_safe(item)) for item in (items or [])]
    return {
        "panel_kind": PANEL_KIND,
        "panel_version": PANEL_VERSION,
        "title": _text(panel_title, "Process Trace"),
        "item_count": len(safe_items),
        "items": safe_items,
        "visible_to_user": True,
        "created_at": _now(),
    }


def append_process_trace_item(panel: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(_safe(panel or build_process_trace_panel()))
    items = _list(updated.get("items"))
    items.append(deepcopy(_safe(item)))
    updated["items"] = items
    updated["item_count"] = len(items)
    return updated


def _status_from_severity(severity: Any) -> str:
    normalized = str(severity or "").strip().lower()
    if normalized == "error":
        return "failed"
    if normalized == "warning":
        return "warning"
    return "completed"


def _kind_from_timeline_event_type(event_type: Any) -> str:
    event = str(event_type or "").strip().lower()
    if "context" in event:
        return "context"
    if "skill" in event:
        return "skill"
    if "action" in event:
        return "action"
    if "tool" in event:
        return "tool"
    if "evidence" in event:
        return "evidence"
    if "handoff" in event:
        return "handoff"
    if "validation" in event:
        return "validation"
    if "blocker" in event:
        return "validation"
    if "review" in event or "audit" in event or "integrator" in event:
        return "review"
    if "metric" in event or "timer" in event:
        return "metric"
    if "complete" in event or "summary" in event:
        return "summary"
    return "timeline"


def process_trace_item_from_timeline_event(event: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(event or {}))
    kind = _kind_from_timeline_event_type(snapshot.get("event_type"))
    status = "blocked" if snapshot.get("event_type") == "blocker_found" else _status_from_severity(snapshot.get("severity"))
    return build_process_trace_item(
        trace_id=snapshot.get("event_id"),
        kind=kind,
        title=snapshot.get("title"),
        summary=snapshot.get("summary"),
        status=status,
        started_at=snapshot.get("created_at"),
        finished_at=snapshot.get("created_at"),
        evidence_refs=snapshot.get("evidence_refs"),
        artifact_refs=snapshot.get("artifact_refs"),
        related_task_id=snapshot.get("task_id"),
        related_agent_id=snapshot.get("agent_id"),
        related_miniagent_id=snapshot.get("miniagent_id"),
        related_skill_id=snapshot.get("skill_id"),
        created_at=snapshot.get("created_at"),
        visible_to_user=snapshot.get("visible_to_user", True),
        internal_only=snapshot.get("internal_only", False),
        details={"event_type": snapshot.get("event_type"), "severity": snapshot.get("severity")},
    )


def process_trace_item_from_runtime_metric(metric: RuntimeTimerRecord | dict[str, Any]) -> dict[str, Any]:
    snapshot = dump_runtime_timer(metric) if isinstance(metric, RuntimeTimerRecord) else deepcopy(_safe(metric or {}))
    trace_id = snapshot.get("timer_id") or snapshot.get("metric_id") or snapshot.get("response_metric_id")
    return build_process_trace_item(
        trace_id=trace_id,
        kind="metric",
        title=snapshot.get("label") or snapshot.get("task_id") or snapshot.get("metric_kind") or "Runtime metric",
        summary=f"Runtime status: {_text(snapshot.get('status'), 'unknown')}.",
        status=snapshot.get("status"),
        started_at=snapshot.get("started_at"),
        finished_at=snapshot.get("finished_at") or snapshot.get("ended_at"),
        duration_ms=snapshot.get("duration_ms"),
        evidence_refs=snapshot.get("evidence_refs"),
        artifact_refs=snapshot.get("artifact_refs"),
        related_task_id=snapshot.get("task_id"),
        related_agent_id=snapshot.get("agent_id"),
        related_miniagent_id=snapshot.get("miniagent_id") or snapshot.get("mini_agent_id"),
        related_skill_id=snapshot.get("skill_id"),
        details={
            "scope": snapshot.get("scope"),
            "state": snapshot.get("state"),
            "model": snapshot.get("model"),
            "provider": snapshot.get("provider"),
            "metric_kind": snapshot.get("metric_kind"),
            "error": snapshot.get("error"),
        },
        metadata=snapshot.get("metadata") if isinstance(snapshot.get("metadata"), dict) else {},
    )
