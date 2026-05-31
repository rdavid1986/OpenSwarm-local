"""Side-effect-free temporal runtime contracts for Swarm traces and context."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.apps.runtime_timing import runtime_timer_duration_ms

TEMPORAL_RUNTIME_VERSION = "openswarm.temporal_runtime.v1"
DEFAULT_TIMEZONE = "UTC"
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "body",
    "chain_of_thought",
    "content",
    "credential",
    "credentials",
    "hidden_reasoning",
    "message",
    "messages",
    "password",
    "private_key",
    "private_reasoning",
    "prompt",
    "raw",
    "raw_prompt",
    "raw_response",
    "request",
    "response",
    "secret",
    "text",
    "token",
}
EXECUTION_KINDS = {"tool", "action", "script", "mcp", "qa", "model", "unknown"}
FRESHNESS_STATES = {"fresh", "stale", "expiring", "unknown"}


@dataclass(frozen=True)
class TemporalCoreRecord:
    temporal_kind: str = "temporal_core"
    temporal_version: str = TEMPORAL_RUNTIME_VERSION
    record_id: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    metadata_updated_at: str | None = None
    last_activity_at: str | None = None
    last_message_at: str | None = None
    last_user_message_at: str | None = None
    last_assistant_message_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    interrupted_at: str | None = None
    archived_at: str | None = None
    compacted_at: str | None = None
    duration_ms: int | None = None
    running_duration_ms: int | None = None
    timezone: str = DEFAULT_TIMEZONE
    local_time_label: str = ""
    monotonic_sequence: int = 0
    stale_after: str | None = None
    last_verified_at: str | None = None
    last_used_at: str | None = None
    last_refreshed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionTemporalState:
    session_id: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    metadata_updated_at: str | None = None
    last_activity_at: str | None = None
    last_message_at: str | None = None
    last_user_message_at: str | None = None
    last_assistant_message_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    interrupted_at: str | None = None
    archived_at: str | None = None
    compacted_at: str | None = None
    duration_ms: int | None = None
    running_duration_ms: int | None = None
    timezone: str = DEFAULT_TIMEZONE
    local_time_label: str = ""
    monotonic_sequence: int = 0
    stale_after: str | None = None
    last_verified_at: str | None = None
    last_used_at: str | None = None
    last_refreshed_at: str | None = None
    message_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MessageTemporalState:
    message_id: str = ""
    role: str = "unknown"
    created_at: str | None = None
    updated_at: str | None = None
    metadata_updated_at: str | None = None
    last_activity_at: str | None = None
    last_message_at: str | None = None
    last_user_message_at: str | None = None
    last_assistant_message_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    interrupted_at: str | None = None
    archived_at: str | None = None
    compacted_at: str | None = None
    duration_ms: int | None = None
    running_duration_ms: int | None = None
    timezone: str = DEFAULT_TIMEZONE
    local_time_label: str = ""
    monotonic_sequence: int = 0
    stale_after: str | None = None
    last_verified_at: str | None = None
    last_used_at: str | None = None
    last_refreshed_at: str | None = None
    elapsed_since_previous_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PartTemporalState:
    part_id: str = ""
    message_id: str = ""
    part_kind: str = "unknown"
    created_at: str | None = None
    updated_at: str | None = None
    metadata_updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    timezone: str = DEFAULT_TIMEZONE
    local_time_label: str = ""
    monotonic_sequence: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalExecutionState:
    execution_id: str = ""
    execution_kind: str = "unknown"
    status: str = "running"
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    interrupted_at: str | None = None
    duration_ms: int | None = None
    running_duration_ms: int | None = None
    timezone: str = DEFAULT_TIMEZONE
    local_time_label: str = ""
    monotonic_sequence: int = 0
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalContextSnapshot:
    snapshot_id: str = ""
    created_at: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    local_time_label: str = ""
    ai_visible_context: dict[str, Any] = field(default_factory=dict)
    compact_label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalFreshnessState:
    freshness_id: str = ""
    status: str = "unknown"
    created_at: str | None = None
    stale_after: str | None = None
    last_verified_at: str | None = None
    last_used_at: str | None = None
    last_refreshed_at: str | None = None
    age_ms: int | None = None
    ttl_ms: int | None = None
    stale_reason: str = ""
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalTraceSource:
    source_kind: str = "temporal_runtime"
    temporal_kind: str = "temporal_trace_source"
    trace_id: str = ""
    status: str = "recorded"
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    interrupted_at: str | None = None
    duration_ms: int | None = None
    running_duration_ms: int | None = None
    stale_after: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    local_time_label: str = ""
    session: dict[str, Any] = field(default_factory=dict)
    message: dict[str, Any] = field(default_factory=dict)
    part: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    freshness: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def normalize_temporal_timestamp(value: str | datetime | None = None, *, fallback_now: bool = False) -> str | None:
    parsed = _parse_datetime(value) or (_parse_datetime(_now()) if fallback_now else None)
    if not parsed:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _zoneinfo(value: Any) -> tuple[str, ZoneInfo | timezone]:
    name = str(value or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    if name.upper() == "UTC":
        return "UTC", timezone.utc
    try:
        return name, ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return "UTC", timezone.utc


def build_local_time_label(timestamp: str | datetime | None = None, *, timezone_name: str = DEFAULT_TIMEZONE) -> str:
    normalized = normalize_temporal_timestamp(timestamp, fallback_now=True)
    parsed = _parse_datetime(normalized)
    zone_name, zone = _zoneinfo(timezone_name)
    if not parsed:
        return ""
    return f"{parsed.astimezone(zone).strftime('%Y-%m-%d %H:%M:%S')} {zone_name}"


def temporal_duration_ms(started_at: Any = None, completed_at: Any = None, *, interrupted_at: Any = None, now: Any = None) -> int | None:
    finish = completed_at or interrupted_at or now
    if not started_at or not finish:
        return None
    return runtime_timer_duration_ms(started_at, finish)


def temporal_gap_ms(previous_at: Any = None, current_at: Any = None) -> int | None:
    return temporal_duration_ms(previous_at, current_at)


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(token in normalized for token in ("secret", "token", "password", "api_key", "credential", "authorization", "private_key"))


def sanitize_temporal_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): sanitize_temporal_metadata(v) for k, v in value.items() if not _is_sensitive_key(k)}
    if isinstance(value, list):
        return [sanitize_temporal_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_temporal_metadata(item) for item in value]
    if isinstance(value, set):
        return [sanitize_temporal_metadata(item) for item in sorted(value, key=str)]
    if isinstance(value, datetime):
        return normalize_temporal_timestamp(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "__dataclass_fields__"):
        return sanitize_temporal_metadata(asdict(value))
    if isinstance(value, dict):
        return sanitize_temporal_metadata(deepcopy(value))
    return {}


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return max(0, parsed)


def _seq(value: Any) -> int:
    parsed = _int(value)
    return parsed if parsed is not None else 0


def _status_from_execution(completed_at: str | None, interrupted_at: str | None, default: str = "running") -> str:
    if interrupted_at:
        return "interrupted"
    if completed_at:
        return "completed"
    return default


def build_temporal_core_record(**kwargs: Any) -> TemporalCoreRecord:
    created = normalize_temporal_timestamp(kwargs.get("created_at"), fallback_now=True)
    updated = normalize_temporal_timestamp(kwargs.get("updated_at")) or created
    started = normalize_temporal_timestamp(kwargs.get("started_at"))
    completed = normalize_temporal_timestamp(kwargs.get("completed_at"))
    interrupted = normalize_temporal_timestamp(kwargs.get("interrupted_at"))
    tz_name, _ = _zoneinfo(kwargs.get("timezone"))
    duration = _int(kwargs.get("duration_ms"))
    if duration is None:
        duration = temporal_duration_ms(started, completed, interrupted_at=interrupted)
    running = _int(kwargs.get("running_duration_ms"))
    if running is None and started and not completed and not interrupted:
        running = temporal_duration_ms(started, now=kwargs.get("now") or _now())
    return TemporalCoreRecord(
        record_id=str(kwargs.get("record_id") or uuid4().hex),
        created_at=created,
        updated_at=updated,
        metadata_updated_at=normalize_temporal_timestamp(kwargs.get("metadata_updated_at")),
        last_activity_at=normalize_temporal_timestamp(kwargs.get("last_activity_at")),
        last_message_at=normalize_temporal_timestamp(kwargs.get("last_message_at")),
        last_user_message_at=normalize_temporal_timestamp(kwargs.get("last_user_message_at")),
        last_assistant_message_at=normalize_temporal_timestamp(kwargs.get("last_assistant_message_at")),
        started_at=started,
        completed_at=completed,
        interrupted_at=interrupted,
        archived_at=normalize_temporal_timestamp(kwargs.get("archived_at")),
        compacted_at=normalize_temporal_timestamp(kwargs.get("compacted_at")),
        duration_ms=duration,
        running_duration_ms=running,
        timezone=tz_name,
        local_time_label=build_local_time_label(updated, timezone_name=tz_name),
        monotonic_sequence=_seq(kwargs.get("monotonic_sequence")),
        stale_after=normalize_temporal_timestamp(kwargs.get("stale_after")),
        last_verified_at=normalize_temporal_timestamp(kwargs.get("last_verified_at")),
        last_used_at=normalize_temporal_timestamp(kwargs.get("last_used_at")),
        last_refreshed_at=normalize_temporal_timestamp(kwargs.get("last_refreshed_at")),
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )


def build_session_temporal_state(**kwargs: Any) -> SessionTemporalState:
    core = build_temporal_core_record(**kwargs)
    return SessionTemporalState(
        session_id=str(kwargs.get("session_id") or core.record_id),
        **{field_name: getattr(core, field_name) for field_name in SessionTemporalState.__dataclass_fields__ if hasattr(core, field_name)},
        message_count=_seq(kwargs.get("message_count")),
    )


def apply_session_temporal_update(state: SessionTemporalState | dict[str, Any], *, event_kind: str, role: str | None = None, at: str | datetime | None = None, metadata: dict[str, Any] | None = None) -> SessionTemporalState:
    data = _dump(state)
    timestamp = normalize_temporal_timestamp(at, fallback_now=True)
    sequence = _seq(data.get("monotonic_sequence")) + 1
    updates: dict[str, Any] = {**data, "updated_at": timestamp, "monotonic_sequence": sequence}
    if event_kind == "metadata_update":
        updates["metadata_updated_at"] = timestamp
    elif event_kind == "activity":
        updates["last_activity_at"] = timestamp
    elif event_kind == "message":
        updates["last_activity_at"] = timestamp
        updates["last_message_at"] = timestamp
        if role == "user":
            updates["last_user_message_at"] = timestamp
        elif role == "assistant":
            updates["last_assistant_message_at"] = timestamp
        updates["message_count"] = _seq(data.get("message_count")) + 1
    updates["metadata"] = sanitize_temporal_metadata({**(data.get("metadata") or {}), **(metadata or {})})
    return build_session_temporal_state(**updates)


def build_message_temporal_state(**kwargs: Any) -> MessageTemporalState:
    core = build_temporal_core_record(**kwargs)
    created = core.created_at
    previous = normalize_temporal_timestamp(kwargs.get("previous_message_at"))
    return MessageTemporalState(
        message_id=str(kwargs.get("message_id") or core.record_id),
        role=str(kwargs.get("role") or "unknown").strip() or "unknown",
        **{field_name: getattr(core, field_name) for field_name in MessageTemporalState.__dataclass_fields__ if hasattr(core, field_name)},
        elapsed_since_previous_ms=temporal_gap_ms(previous, created) if previous and created else None,
    )


def build_part_temporal_state(**kwargs: Any) -> PartTemporalState:
    core = build_temporal_core_record(**kwargs)
    return PartTemporalState(
        part_id=str(kwargs.get("part_id") or core.record_id),
        message_id=str(kwargs.get("message_id") or ""),
        part_kind=str(kwargs.get("part_kind") or "unknown"),
        created_at=core.created_at,
        updated_at=core.updated_at,
        metadata_updated_at=core.metadata_updated_at,
        started_at=core.started_at,
        completed_at=core.completed_at,
        duration_ms=core.duration_ms,
        timezone=core.timezone,
        local_time_label=core.local_time_label,
        monotonic_sequence=core.monotonic_sequence,
        metadata=core.metadata,
    )


def build_temporal_execution_state(**kwargs: Any) -> TemporalExecutionState:
    core = build_temporal_core_record(**kwargs)
    kind = str(kwargs.get("execution_kind") or kwargs.get("kind") or "unknown").strip().lower()
    if kind not in EXECUTION_KINDS:
        kind = "unknown"
    status = str(kwargs.get("status") or _status_from_execution(core.completed_at, core.interrupted_at)).strip().lower()
    warnings = list(kwargs.get("warnings") or [])
    required_actions = list(kwargs.get("required_actions") or [])
    return TemporalExecutionState(
        execution_id=str(kwargs.get("execution_id") or core.record_id),
        execution_kind=kind,
        status=status,
        created_at=core.created_at,
        updated_at=core.updated_at,
        started_at=core.started_at,
        completed_at=core.completed_at,
        interrupted_at=core.interrupted_at,
        duration_ms=core.duration_ms,
        running_duration_ms=core.running_duration_ms,
        timezone=core.timezone,
        local_time_label=core.local_time_label,
        monotonic_sequence=core.monotonic_sequence,
        warnings=warnings,
        required_actions=required_actions,
        metadata=core.metadata,
    )


def build_temporal_freshness_state(**kwargs: Any) -> TemporalFreshnessState:
    created = normalize_temporal_timestamp(kwargs.get("created_at"), fallback_now=True)
    now = normalize_temporal_timestamp(kwargs.get("now"), fallback_now=True)
    stale_after = normalize_temporal_timestamp(kwargs.get("stale_after"))
    last_verified = normalize_temporal_timestamp(kwargs.get("last_verified_at"))
    last_used = normalize_temporal_timestamp(kwargs.get("last_used_at"))
    last_refreshed = normalize_temporal_timestamp(kwargs.get("last_refreshed_at"))
    ttl_seconds = _int(kwargs.get("ttl_seconds"))
    ttl_ms = _int(kwargs.get("ttl_ms")) or (ttl_seconds * 1000 if ttl_seconds is not None else None)
    reference = last_refreshed or last_verified or created
    age_ms = temporal_duration_ms(reference, now) if reference and now else None
    warnings: list[str] = list(kwargs.get("warnings") or [])
    required: list[str] = list(kwargs.get("required_actions") or [])
    status = str(kwargs.get("status") or "").strip().lower()
    if status not in FRESHNESS_STATES:
        if stale_after and now and _parse_datetime(now) and _parse_datetime(stale_after) and _parse_datetime(now) > _parse_datetime(stale_after):
            status = "stale"
        elif ttl_ms is not None and age_ms is not None and age_ms > ttl_ms:
            status = "stale"
        elif ttl_ms is not None and age_ms is not None and age_ms >= int(ttl_ms * 0.85):
            status = "expiring"
        elif reference:
            status = "fresh"
        else:
            status = "unknown"
    if status == "stale":
        warnings.append("temporal_context_stale")
        required.append("refresh_or_verify_context")
    elif status == "expiring":
        warnings.append("temporal_context_near_stale")
    return TemporalFreshnessState(
        freshness_id=str(kwargs.get("freshness_id") or uuid4().hex),
        status=status,
        created_at=created,
        stale_after=stale_after,
        last_verified_at=last_verified,
        last_used_at=last_used,
        last_refreshed_at=last_refreshed,
        age_ms=age_ms,
        ttl_ms=ttl_ms,
        stale_reason=str(kwargs.get("stale_reason") or ("ttl_expired" if status == "stale" else "")),
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(required)),
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )


def build_temporal_context_snapshot(*, session: SessionTemporalState | dict[str, Any] | None = None, freshness: TemporalFreshnessState | dict[str, Any] | None = None, timezone_name: str = DEFAULT_TIMEZONE, now: str | datetime | None = None, metadata: dict[str, Any] | None = None) -> TemporalContextSnapshot:
    created = normalize_temporal_timestamp(now, fallback_now=True)
    tz_name, _ = _zoneinfo(timezone_name)
    session_data = _dump(session)
    freshness_data = _dump(freshness)
    context = sanitize_temporal_metadata({
        "current_utc": created,
        "local_time": build_local_time_label(created, timezone_name=tz_name),
        "timezone": tz_name,
        "session_started_at": session_data.get("started_at"),
        "last_activity_at": session_data.get("last_activity_at"),
        "last_message_at": session_data.get("last_message_at"),
        "last_user_message_at": session_data.get("last_user_message_at"),
        "last_assistant_message_at": session_data.get("last_assistant_message_at"),
        "freshness_status": freshness_data.get("status"),
        "stale_after": freshness_data.get("stale_after"),
    })
    compact_label = f"now={context.get('current_utc')} local={context.get('local_time')} freshness={context.get('freshness_status') or 'unknown'}"
    return TemporalContextSnapshot(
        snapshot_id=str((metadata or {}).get("snapshot_id") or uuid4().hex),
        created_at=created,
        timezone=tz_name,
        local_time_label=build_local_time_label(created, timezone_name=tz_name),
        ai_visible_context=context,
        compact_label=compact_label,
        metadata=sanitize_temporal_metadata(metadata or {}),
    )


def build_temporal_trace_source(*, session: SessionTemporalState | dict[str, Any] | None = None, message: MessageTemporalState | dict[str, Any] | None = None, part: PartTemporalState | dict[str, Any] | None = None, execution: TemporalExecutionState | dict[str, Any] | None = None, context: TemporalContextSnapshot | dict[str, Any] | None = None, freshness: TemporalFreshnessState | dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    session_data = _dump(session)
    message_data = _dump(message)
    part_data = _dump(part)
    execution_data = _dump(execution)
    context_data = _dump(context)
    freshness_data = _dump(freshness)
    warnings: list[str] = []
    required: list[str] = []
    for item in (execution_data, freshness_data):
        warnings.extend(item.get("warnings") or [])
        required.extend(item.get("required_actions") or [])
    started = execution_data.get("started_at") or session_data.get("started_at") or message_data.get("started_at")
    completed = execution_data.get("completed_at") or session_data.get("completed_at") or message_data.get("completed_at")
    interrupted = execution_data.get("interrupted_at") or session_data.get("interrupted_at") or message_data.get("interrupted_at")
    duration = execution_data.get("duration_ms") or session_data.get("duration_ms") or message_data.get("duration_ms")
    trace = TemporalTraceSource(
        trace_id=str((metadata or {}).get("trace_id") or execution_data.get("execution_id") or message_data.get("message_id") or session_data.get("session_id") or uuid4().hex),
        status=execution_data.get("status") or freshness_data.get("status") or "recorded",
        created_at=normalize_temporal_timestamp((metadata or {}).get("created_at"), fallback_now=True),
        started_at=started,
        completed_at=completed,
        interrupted_at=interrupted,
        duration_ms=duration,
        running_duration_ms=execution_data.get("running_duration_ms") or session_data.get("running_duration_ms") or message_data.get("running_duration_ms"),
        stale_after=freshness_data.get("stale_after") or session_data.get("stale_after"),
        timezone=context_data.get("timezone") or session_data.get("timezone") or DEFAULT_TIMEZONE,
        local_time_label=context_data.get("local_time_label") or session_data.get("local_time_label") or "",
        session=session_data,
        message=message_data,
        part=part_data,
        execution=execution_data,
        context=context_data,
        freshness=freshness_data,
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(required)),
        metadata=sanitize_temporal_metadata(metadata or {}),
    )
    return dump_temporal_trace_source(trace)


def dump_temporal_core_record(value: TemporalCoreRecord | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_session_temporal_state(value: SessionTemporalState | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_message_temporal_state(value: MessageTemporalState | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_part_temporal_state(value: PartTemporalState | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_temporal_execution_state(value: TemporalExecutionState | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_temporal_context_snapshot(value: TemporalContextSnapshot | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_temporal_freshness_state(value: TemporalFreshnessState | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_temporal_trace_source(value: TemporalTraceSource | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)
