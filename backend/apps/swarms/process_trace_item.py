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
TURN_TRACE_KIND = "process_trace_turn_container"
TURN_TRACE_VERSION = "openswarm.process_trace_turn_container.v1"

ALLOWED_KINDS = {
    "reasoning",
    "thinking",
    "context",
    "memory",
    "skill",
    "mode",
    "action",
    "tool",
    "file",
    "diff",
    "workspace",
    "evidence",
    "handoff",
    "miniagent",
    "metric",
    "review",
    "browser",
    "config",
    "model",
    "timeline",
    "worklog",
    "validation",
    "output",
    "artifact",
    "debug",
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
ALLOWED_REASONING_SUMMARY_SOURCES = {
    "native_ollama_thinking",
    "provider_reasoning_summary",
    "operational_summary",
    "fallback",
}
ALLOWED_REASONING_LEVELS = {"auto", "off", "minimal", "low", "medium", "high", "xhigh"}


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




def _normalize_reasoning_summary_source(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_REASONING_SUMMARY_SOURCES else "fallback"


def _normalize_reasoning_level(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_REASONING_LEVELS else "auto"


def build_humanized_reasoning_trace_item(
    *,
    trace_id: Any = None,
    summary: Any = None,
    source: Any = "operational_summary",
    status: Any = "completed",
    requested_level: Any = "auto",
    applied_level: Any = "auto",
    provider: Any = None,
    model: Any = None,
    capability_supported: Any = None,
    duration_ms: Any = None,
    related_agent_id: Any = None,
    related_task_id: Any = None,
    output_message_id: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a user-safe ReasoningCore trace item.

    This helper stores a human-readable reasoning summary. It must not expose
    private chain-of-thought. Native thinking text may only be represented here
    after provider separation and redaction.
    """

    normalized_source = _normalize_reasoning_summary_source(source)
    normalized_requested_level = _normalize_reasoning_level(requested_level)
    normalized_applied_level = _normalize_reasoning_level(applied_level)
    safe_summary = _text(summary, "Reasoning summary unavailable.")
    support_value = None if capability_supported is None else bool(capability_supported)

    merged_metadata = {
        "summary_source": normalized_source,
        "requested_reasoning_level": normalized_requested_level,
        "applied_reasoning_level": normalized_applied_level,
        "capability_supported": support_value,
        "provider": _optional_text(provider),
        "model": _optional_text(model),
        "output_message_id": _optional_text(output_message_id),
        **dict(metadata or {}),
    }

    return build_process_trace_item(
        trace_id=trace_id,
        kind="reasoning",
        subsystem="ReasoningCore",
        icon_id="reasoning-core",
        title="Reasoning summary",
        summary=safe_summary,
        status=status,
        duration_ms=duration_ms,
        badge=normalized_source,
        related_agent_id=related_agent_id,
        related_task_id=related_task_id,
        details={
            "summary_source": normalized_source,
            "requested_reasoning_level": normalized_requested_level,
            "applied_reasoning_level": normalized_applied_level,
            "capability_supported": support_value,
            "provider": _optional_text(provider),
            "model": _optional_text(model),
        },
        metadata=merged_metadata,
    )


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


def build_process_trace_turn_container(
    *,
    items: list[dict[str, Any]] | None = None,
    turn_trace_id: Any = None,
    title: Any = "Thought",
    status: Any = "completed",
    turn_id: Any = None,
    message_id: Any = None,
    action_id: Any = None,
    started_at: Any = None,
    finished_at: Any = None,
    duration_ms: Any = None,
    child_trace_ids: Any = None,
    output_message_id: Any = None,
    related_task_ids: Any = None,
    related_agent_ids: Any = None,
    related_miniagent_ids: Any = None,
    evidence_refs: Any = None,
    artifact_refs: Any = None,
    default_collapsed_after_finish: bool = True,
    default_expanded_while_running: bool = False,
    visible_to_user: bool = True,
    internal_only: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one privacy-safe turn/action work trace container.

    The turn container is the parent object for a chat turn or action. It groups
    ProcessTraceItem children such as ReasoningCore, ModelCore, ToolCore,
    FileCore, EvidenceCore, ValidationCore, and Debug JSON. It is intentionally
    side-effect-free and does not persist, call models, read files, or mutate
    runtime state.
    """

    safe_items = [deepcopy(_safe(item)) for item in (items or [])]
    inferred_child_ids = [
        str(item.get("trace_id"))
        for item in safe_items
        if isinstance(item, dict) and str(item.get("trace_id") or "").strip()
    ]
    normalized_status = _normalize_status(status)
    normalized_child_ids = _list(child_trace_ids) if child_trace_ids is not None else inferred_child_ids
    created_at = _now()

    return _safe({
        "turn_trace_kind": TURN_TRACE_KIND,
        "turn_trace_version": TURN_TRACE_VERSION,
        "turn_trace_id": _text(turn_trace_id, uuid4().hex),
        "title": _text(title, "Thought"),
        "status": normalized_status,
        "turn_id": _text(turn_id),
        "message_id": _text(message_id),
        "action_id": _text(action_id),
        "started_at": _optional_text(started_at),
        "finished_at": _optional_text(finished_at),
        "duration_ms": _int_or_none(duration_ms),
        "default_collapsed_after_finish": bool(default_collapsed_after_finish),
        "default_expanded_while_running": bool(default_expanded_while_running),
        "child_trace_ids": normalized_child_ids,
        "item_count": len(safe_items),
        "items": safe_items,
        "output_message_id": _text(output_message_id),
        "related_task_ids": _list(related_task_ids),
        "related_agent_ids": _list(related_agent_ids),
        "related_miniagent_ids": _list(related_miniagent_ids),
        "evidence_refs": _list(evidence_refs),
        "artifact_refs": _list(artifact_refs),
        "visible_to_user": bool(visible_to_user),
        "internal_only": bool(internal_only),
        "metadata": _safe(dict(metadata or {})),
        "created_at": created_at,
    })


def append_process_trace_turn_item(container: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(_safe(container or build_process_trace_turn_container()))
    safe_item = deepcopy(_safe(item))
    items = _list(updated.get("items"))
    items.append(safe_item)
    updated["items"] = items
    updated["item_count"] = len(items)

    trace_id = safe_item.get("trace_id") if isinstance(safe_item, dict) else None
    child_trace_ids = _list(updated.get("child_trace_ids"))
    if trace_id and trace_id not in child_trace_ids:
        child_trace_ids.append(trace_id)
    updated["child_trace_ids"] = child_trace_ids
    return updated


def summarize_process_trace_turn_container(container: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(container or {}))
    items = _list(snapshot.get("items"))
    return {
        "summary_kind": "process_trace_turn_container_summary",
        "turn_trace_id": snapshot.get("turn_trace_id", ""),
        "title": snapshot.get("title", "Thought"),
        "status": snapshot.get("status", "planned"),
        "duration_ms": snapshot.get("duration_ms"),
        "item_count": len(items),
        "child_trace_count": len(_list(snapshot.get("child_trace_ids"))),
        "evidence_count": len(_list(snapshot.get("evidence_refs"))),
        "artifact_count": len(_list(snapshot.get("artifact_refs"))),
        "visible_to_user": bool(snapshot.get("visible_to_user", True)),
        "internal_only": bool(snapshot.get("internal_only", False)),
    }


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
