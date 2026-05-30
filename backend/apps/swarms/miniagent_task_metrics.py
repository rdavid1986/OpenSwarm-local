"""Side-effect-free MiniAgent task runtime metrics contract.

SWARM-CANVAS.TIMER.4.A defines the in-memory/read-only metric shape for
MiniAgent task execution. It does not persist metrics, emit events, call models,
execute tools, mutate SwarmState, or update UI state.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.apps.runtime_timing import (
    RuntimeTimerRecord,
    dump_runtime_timer,
    fail_runtime_timer,
    finish_runtime_timer,
    runtime_timer_duration_ms,
    start_runtime_timer,
)

METRIC_KIND = "miniagent_task_runtime_metric"
METRIC_VERSION = "openswarm.miniagent_task_runtime_metric.v1"

STATUSES = {"planned", "running", "completed", "failed", "cancelled", "blocked", "skipped"}
SENSITIVE_KEYS = {"chain_of_thought", "cot", "private_reasoning", "hidden_reasoning"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _status(value: Any, default: str = "planned") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in STATUSES else default


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, parsed)


def _bool(value: Any) -> bool:
    return bool(value)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if str(k) not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return [_safe(v) for v in sorted(value, key=str)]
    return value


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return _safe(value)
    return [_safe(value)]


def build_miniagent_task_runtime_metric(**kwargs: Any) -> dict[str, Any]:
    """Build a safe metric snapshot for a MiniAgent task.

    This is only a contract snapshot. Runtime integration and persistence are
    handled by later phases.
    """

    status = _status(kwargs.get("status"), "planned")
    started_at = _text(kwargs.get("started_at"), _now())
    finished_at = _optional_text(kwargs.get("finished_at") or kwargs.get("ended_at"))
    duration_ms = _int_or_none(kwargs.get("duration_ms"))

    if duration_ms is None and finished_at:
        duration_ms = runtime_timer_duration_ms(started_at, finished_at)

    runtime_timer = kwargs.get("runtime_timer")
    if isinstance(runtime_timer, RuntimeTimerRecord) and duration_ms is None:
        duration_ms = runtime_timer.duration_ms

    metric = {
        "metric_kind": METRIC_KIND,
        "metric_version": METRIC_VERSION,
        "metric_id": _text(kwargs.get("metric_id"), uuid4().hex),
        "swarm_id": _text(kwargs.get("swarm_id")),
        "agent_id": _text(kwargs.get("agent_id")),
        "miniagent_id": _text(kwargs.get("miniagent_id")),
        "task_id": _text(kwargs.get("task_id")),
        "attempt_id": _text(kwargs.get("attempt_id")),
        "skill_id": _text(kwargs.get("skill_id")),
        "skill_name": _text(kwargs.get("skill_name")),
        "mode_id": _text(kwargs.get("mode_id")),
        "model": _text(kwargs.get("model")),
        "provider": _text(kwargs.get("provider")),
        "started_at": started_at,
        "finished_at": finished_at,
        "ended_at": finished_at,
        "duration_ms": duration_ms,
        "wait_ms": _int_or_none(kwargs.get("wait_ms")),
        "model_ms": _int_or_none(kwargs.get("model_ms")),
        "tool_ms": _int_or_none(kwargs.get("tool_ms")),
        "action_ms": _int_or_none(kwargs.get("action_ms")),
        "validation_ms": _int_or_none(kwargs.get("validation_ms")),
        "handoff_ms": _int_or_none(kwargs.get("handoff_ms")),
        "status": status,
        "retry_count": _int_or_none(kwargs.get("retry_count")) or 0,
        "evidence_count": _int_or_none(kwargs.get("evidence_count")) or len(_list(kwargs.get("evidence_refs"))),
        "files_changed_count": _int_or_none(kwargs.get("files_changed_count")) or len(_list(kwargs.get("files_changed"))),
        "artifacts_count": _int_or_none(kwargs.get("artifacts_count")) or len(_list(kwargs.get("artifacts"))),
        "blockers_count": _int_or_none(kwargs.get("blockers_count")) or len(_list(kwargs.get("blockers"))),
        "evidence_refs": _list(kwargs.get("evidence_refs")),
        "artifact_refs": _list(kwargs.get("artifact_refs")),
        "files_changed": _list(kwargs.get("files_changed")),
        "blockers": _list(kwargs.get("blockers")),
        "warnings": _list(kwargs.get("warnings")),
        "metadata": _safe(dict(kwargs.get("metadata") or {})),
        "runtime_timer": dump_runtime_timer(runtime_timer) if isinstance(runtime_timer, RuntimeTimerRecord) else None,
    }
    return _safe(metric)


def start_miniagent_task_runtime_metric(**kwargs: Any) -> dict[str, Any]:
    started_at = _text(kwargs.get("started_at"), _now())
    runtime_timer = start_runtime_timer(
        scope="mini_agent",
        label=_text(kwargs.get("label"), "MiniAgent task"),
        state=_text(kwargs.get("state"), "working"),
        started_at=started_at,
        timer_id=kwargs.get("timer_id"),
        swarm_id=kwargs.get("swarm_id"),
        agent_id=kwargs.get("agent_id"),
        mini_agent_id=kwargs.get("miniagent_id") or kwargs.get("mini_agent_id"),
        task_id=kwargs.get("task_id"),
        model=kwargs.get("model"),
        route=kwargs.get("route"),
        flow=kwargs.get("flow"),
        evidence_refs=_list(kwargs.get("evidence_refs")),
        metadata=_safe(dict(kwargs.get("metadata") or {})),
    )
    metric_kwargs = dict(kwargs)
    metric_kwargs.pop("started_at", None)
    metric_kwargs.pop("status", None)
    metric_kwargs.pop("runtime_timer", None)
    return build_miniagent_task_runtime_metric(
        **metric_kwargs,
        started_at=started_at,
        status="running",
        runtime_timer=runtime_timer,
    )


def finish_miniagent_task_runtime_metric(
    metric: dict[str, Any],
    *,
    finished_at: str | datetime | None = None,
    **updates: Any,
) -> dict[str, Any]:
    snapshot = deepcopy(_safe(metric or {}))
    finished = finished_at.isoformat() if isinstance(finished_at, datetime) else (finished_at or _now())
    runtime_timer = snapshot.get("runtime_timer")
    timer_record = None
    if isinstance(updates.get("runtime_timer"), RuntimeTimerRecord):
        timer_record = finish_runtime_timer(updates["runtime_timer"], finished_at=finished)
    elif isinstance(metric.get("_runtime_timer"), RuntimeTimerRecord):
        timer_record = finish_runtime_timer(metric["_runtime_timer"], finished_at=finished)

    merged = {
        **snapshot,
        **updates,
        "finished_at": finished,
        "ended_at": finished,
        "status": _status(updates.get("status"), "completed"),
    }
    if timer_record is not None:
        merged["runtime_timer"] = dump_runtime_timer(timer_record)
    elif runtime_timer is not None:
        merged["runtime_timer"] = runtime_timer

    merged["duration_ms"] = _int_or_none(updates.get("duration_ms")) or runtime_timer_duration_ms(snapshot.get("started_at"), finished)
    return build_miniagent_task_runtime_metric(**merged)


def fail_miniagent_task_runtime_metric(
    metric: dict[str, Any],
    *,
    error: str | None = None,
    finished_at: str | datetime | None = None,
    **updates: Any,
) -> dict[str, Any]:
    snapshot = deepcopy(_safe(metric or {}))
    finished = finished_at.isoformat() if isinstance(finished_at, datetime) else (finished_at or _now())
    merged_metadata = {**dict(snapshot.get("metadata") or {}), "error": _text(error, "miniagent_task_failed")}
    merged = {
        **snapshot,
        **updates,
        "finished_at": finished,
        "ended_at": finished,
        "status": "failed",
        "metadata": merged_metadata,
        "duration_ms": _int_or_none(updates.get("duration_ms")) or runtime_timer_duration_ms(snapshot.get("started_at"), finished),
    }
    return build_miniagent_task_runtime_metric(**merged)


def summarize_miniagent_task_runtime_metrics(metrics: list[dict[str, Any]] | None) -> dict[str, Any]:
    safe_metrics = [build_miniagent_task_runtime_metric(**deepcopy(_safe(item))) for item in (metrics or [])]
    durations = [item["duration_ms"] for item in safe_metrics if isinstance(item.get("duration_ms"), int)]
    return {
        "summary_kind": "miniagent_task_runtime_metrics_summary",
        "metric_count": len(safe_metrics),
        "completed_count": sum(1 for item in safe_metrics if item.get("status") == "completed"),
        "failed_count": sum(1 for item in safe_metrics if item.get("status") == "failed"),
        "blocked_count": sum(1 for item in safe_metrics if item.get("status") == "blocked"),
        "running_count": sum(1 for item in safe_metrics if item.get("status") == "running"),
        "total_duration_ms": sum(durations),
        "average_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "max_duration_ms": max(durations) if durations else None,
        "min_duration_ms": min(durations) if durations else None,
        "total_evidence_count": sum(int(item.get("evidence_count") or 0) for item in safe_metrics),
        "total_artifacts_count": sum(int(item.get("artifacts_count") or 0) for item in safe_metrics),
        "total_blockers_count": sum(int(item.get("blockers_count") or 0) for item in safe_metrics),
    }


def build_miniagent_task_runtime_timeline_event(metric: dict[str, Any]) -> dict[str, Any]:
    snapshot = build_miniagent_task_runtime_metric(**deepcopy(_safe(metric or {})))
    status = snapshot.get("status") or "planned"
    severity = "error" if status == "failed" else "warning" if status == "blocked" else "info"
    return {
        "event_type": "miniagent_runtime_metric",
        "title": f"MiniAgent task {status}",
        "summary": f"Task {snapshot.get('task_id') or 'unknown'} {status} in {snapshot.get('duration_ms')}ms.",
        "agent_id": snapshot.get("agent_id", ""),
        "miniagent_id": snapshot.get("miniagent_id", ""),
        "task_id": snapshot.get("task_id", ""),
        "skill_id": snapshot.get("skill_id", ""),
        "evidence_refs": snapshot.get("evidence_refs", []),
        "artifact_refs": snapshot.get("artifact_refs", []),
        "created_at": snapshot.get("finished_at") or snapshot.get("started_at") or _now(),
        "severity": severity,
        "visible_to_user": True,
        "internal_only": False,
    }
