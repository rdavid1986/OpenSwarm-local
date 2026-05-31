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


@dataclass(frozen=True)
class TemporalLogPolicy:
    policy_id: str = ""
    timestamp_format: str = "%Y%m%dT%H%M%SZ"
    retention_count: int = 10
    max_log_size_bytes: int = 5_000_000
    local_path_label: str = "runtime/logs"
    redaction_enabled: bool = True
    extract_evidence: bool = False
    include_chain_of_thought: bool = False
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalLogFileCandidate:
    candidate_id: str = ""
    filename: str = ""
    timestamp: str | None = None
    local_path_label: str = ""
    should_rotate: bool = False
    rotation_reason: str = "none"
    retention_count: int = 10
    max_log_size_bytes: int = 5_000_000
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalTimelineOrderingDecision:
    decision_id: str = ""
    order_key: str = "created_at"
    order_timestamp: str | None = None
    reason: str = "created_at_fallback"
    last_message_at: str | None = None
    last_activity_at: str | None = None
    metadata_updated_at: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalTimezonePolicy:
    policy_id: str = ""
    timezone: str = DEFAULT_TIMEZONE
    locale: str = "en-US"
    hour_cycle: str = "24h"
    utc_debug_mode: bool = False
    storage_timezone: str = "UTC"
    local_time_label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalTitleFallback:
    title: str = ""
    title_status: str = "fallback"
    reason: str = "title_generation_failed"
    allow_regenerate: bool = True
    timestamp: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalRetryBackoffState:
    retry_id: str = ""
    attempt_count: int = 0
    first_attempt_at: str | None = None
    last_attempt_at: str | None = None
    next_retry_at: str | None = None
    backoff_ms: int = 0
    max_retry_deadline: str | None = None
    total_retry_duration_ms: int | None = None
    should_retry: bool = False
    blocked_reason: str = ""
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalDurationAggregation:
    aggregation_id: str = ""
    total_agent_run_time_ms: int = 0
    model_duration_ms: int = 0
    tool_duration_ms: int = 0
    command_duration_ms: int = 0
    qa_duration_ms: int = 0
    idle_time_ms: int = 0
    user_gap_time_ms: int = 0
    assistant_gap_time_ms: int = 0
    longest_blocked_state_ms: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalEvidenceRecord:
    evidence_id: str = ""
    produced_at: str | None = None
    observed_at: str | None = None
    ingested_at: str | None = None
    source_updated_at: str | None = None
    validation_at: str | None = None
    expires_at: str | None = None
    freshness_status: str = "unknown"
    evidence_stale: bool = False
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalMigrationBackfillPlan:
    plan_id: str = ""
    target_id: str = ""
    inferred_created_at: str | None = None
    timestamp_status: str = "unknown"
    migration_source: str = "unknown"
    confidence: float = 0.0
    stable_order_key: str = ""
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



def _dedupe_text(values: Any) -> list[str]:
    items = values if isinstance(values, list) else [values]
    output: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in output:
            output.append(text)
    return output


def _add_ms(target: dict[str, int], key: str, value: Any) -> None:
    parsed = _int(value)
    if parsed is not None:
        target[key] = target.get(key, 0) + parsed


def _format_with_policy(timestamp: str | datetime | None, policy: TemporalTimezonePolicy | dict[str, Any] | None = None) -> str:
    data = _dump(policy)
    tz_name = data.get("timezone") or DEFAULT_TIMEZONE
    hour_cycle = data.get("hour_cycle") or "24h"
    normalized = normalize_temporal_timestamp(timestamp, fallback_now=True)
    parsed = _parse_datetime(normalized)
    zone_name, zone = _zoneinfo(tz_name)
    if not parsed:
        return ""
    fmt = "%Y-%m-%d %H:%M:%S" if hour_cycle != "12h" else "%Y-%m-%d %I:%M:%S %p"
    label = f"{parsed.astimezone(zone).strftime(fmt)} {zone_name}"
    if data.get("utc_debug_mode"):
        label = f"{label} / {normalized} UTC"
    return label


def build_temporal_log_policy(**kwargs: Any) -> TemporalLogPolicy:
    retention = _int(kwargs.get("retention_count"))
    max_size = _int(kwargs.get("max_log_size_bytes"))
    warnings: list[str] = []
    if retention is None or retention <= 0:
        retention = 10
        warnings.append("retention_count_normalized")
    if max_size is None or max_size <= 0:
        max_size = 5_000_000
        warnings.append("max_log_size_normalized")
    include_cot = bool(kwargs.get("include_chain_of_thought"))
    if include_cot:
        warnings.append("chain_of_thought_excluded")
    return TemporalLogPolicy(
        policy_id=str(kwargs.get("policy_id") or uuid4().hex),
        timestamp_format=str(kwargs.get("timestamp_format") or "%Y%m%dT%H%M%SZ"),
        retention_count=retention,
        max_log_size_bytes=max_size,
        local_path_label=str(kwargs.get("local_path_label") or "runtime/logs"),
        redaction_enabled=bool(kwargs.get("redaction_enabled", True)),
        extract_evidence=bool(kwargs.get("extract_evidence", False)),
        include_chain_of_thought=False,
        warnings=list(dict.fromkeys(warnings + list(kwargs.get("warnings") or []))),
        required_actions=list(kwargs.get("required_actions") or []),
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )


def build_temporal_log_file_candidate(*, timestamp: str | datetime | None = None, policy: TemporalLogPolicy | dict[str, Any] | None = None, current_size_bytes: int | None = None, metadata: dict[str, Any] | None = None) -> TemporalLogFileCandidate:
    policy_data = _dump(policy) or _dump(build_temporal_log_policy())
    ts = normalize_temporal_timestamp(timestamp, fallback_now=True)
    parsed = _parse_datetime(ts)
    fmt = policy_data.get("timestamp_format") or "%Y%m%dT%H%M%SZ"
    stamp = parsed.strftime(fmt) if parsed else "unknown"
    filename = f"openswarm-runtime-{stamp}.log"
    max_size = _int(policy_data.get("max_log_size_bytes")) or 5_000_000
    size = _int(current_size_bytes) or 0
    should_rotate = size >= max_size
    return TemporalLogFileCandidate(
        candidate_id=str((metadata or {}).get("candidate_id") or uuid4().hex),
        filename=filename,
        timestamp=ts,
        local_path_label=policy_data.get("local_path_label") or "runtime/logs",
        should_rotate=should_rotate,
        rotation_reason="max_size" if should_rotate else "none",
        retention_count=_int(policy_data.get("retention_count")) or 10,
        max_log_size_bytes=max_size,
        metadata=sanitize_temporal_metadata(metadata or {}),
    )


def build_timeline_ordering_decision(**kwargs: Any) -> TemporalTimelineOrderingDecision:
    last_message = normalize_temporal_timestamp(kwargs.get("last_message_at"))
    last_activity = normalize_temporal_timestamp(kwargs.get("last_activity_at"))
    metadata_updated = normalize_temporal_timestamp(kwargs.get("metadata_updated_at"))
    created = normalize_temporal_timestamp(kwargs.get("created_at"), fallback_now=True)
    scope = str(kwargs.get("scope") or kwargs.get("timeline_kind") or "conversation").strip().lower()
    if scope == "execution" and last_activity:
        key, ts, reason = "last_activity_at", last_activity, "execution_last_activity"
    elif last_message:
        key, ts, reason = "last_message_at", last_message, "conversation_last_message"
    elif scope == "metadata" and metadata_updated:
        key, ts, reason = "metadata_updated_at", metadata_updated, "metadata_update_only"
    else:
        key, ts, reason = "created_at", created, "created_at_fallback"
    return TemporalTimelineOrderingDecision(
        decision_id=str(kwargs.get("decision_id") or uuid4().hex),
        order_key=key,
        order_timestamp=ts,
        reason=reason,
        last_message_at=last_message,
        last_activity_at=last_activity,
        metadata_updated_at=metadata_updated,
        created_at=created,
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )


def build_timezone_format_policy(**kwargs: Any) -> TemporalTimezonePolicy:
    tz_name, _ = _zoneinfo(kwargs.get("timezone"))
    hour_cycle = str(kwargs.get("hour_cycle") or "24h").lower()
    if hour_cycle not in {"12h", "24h"}:
        hour_cycle = "24h"
    timestamp = kwargs.get("timestamp") or kwargs.get("now")
    policy = TemporalTimezonePolicy(
        policy_id=str(kwargs.get("policy_id") or uuid4().hex),
        timezone=tz_name,
        locale=str(kwargs.get("locale") or "en-US"),
        hour_cycle=hour_cycle,
        utc_debug_mode=bool(kwargs.get("utc_debug_mode", False)),
        storage_timezone="UTC",
        local_time_label="",
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )
    return TemporalTimezonePolicy(**{**asdict(policy), "local_time_label": _format_with_policy(timestamp, policy)})


def build_session_title_timestamp_fallback(**kwargs: Any) -> TemporalTitleFallback:
    policy = kwargs.get("timezone_policy")
    timestamp = normalize_temporal_timestamp(kwargs.get("timestamp") or kwargs.get("created_at"), fallback_now=True)
    label = _format_with_policy(timestamp, policy if isinstance(policy, (TemporalTimezonePolicy, dict)) else build_timezone_format_policy(timezone=kwargs.get("timezone"), timestamp=timestamp))
    title = str(kwargs.get("title") or f"Session {label}").strip()
    return TemporalTitleFallback(
        title=title,
        title_status="fallback",
        reason=str(kwargs.get("reason") or "title_generation_failed"),
        allow_regenerate=bool(kwargs.get("allow_regenerate", True)),
        timestamp=timestamp,
        timezone=(_dump(policy).get("timezone") if isinstance(policy, (TemporalTimezonePolicy, dict)) else _zoneinfo(kwargs.get("timezone"))[0]),
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )


def _add_ms_to_timestamp(timestamp: str | None, ms: int) -> str | None:
    parsed = _parse_datetime(timestamp)
    if not parsed:
        return None
    return (parsed.timestamp() * 1000 + ms)


def _iso_from_epoch_ms(epoch_ms: float | int | None) -> str | None:
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(float(epoch_ms) / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def build_retry_backoff_state(**kwargs: Any) -> TemporalRetryBackoffState:
    attempt = _int(kwargs.get("attempt_count")) or 0
    max_attempts = _int(kwargs.get("max_attempts")) or 3
    base = _int(kwargs.get("base_backoff_ms")) or 500
    cap = _int(kwargs.get("max_backoff_ms")) or 30_000
    first = normalize_temporal_timestamp(kwargs.get("first_attempt_at"), fallback_now=True)
    last = normalize_temporal_timestamp(kwargs.get("last_attempt_at")) or first
    deadline = normalize_temporal_timestamp(kwargs.get("max_retry_deadline"))
    now = normalize_temporal_timestamp(kwargs.get("now")) or last
    backoff = min(cap, base * (2 ** max(0, attempt - 1))) if attempt else base
    next_epoch = _add_ms_to_timestamp(last, backoff)
    next_retry = _iso_from_epoch_ms(next_epoch)
    total = temporal_duration_ms(first, last)
    warnings: list[str] = []
    required: list[str] = []
    blocked = ""
    should_retry = attempt < max_attempts
    if deadline and next_retry and _parse_datetime(next_retry) and _parse_datetime(deadline) and _parse_datetime(next_retry) > _parse_datetime(deadline):
        should_retry = False
        blocked = "deadline_exceeded"
    if attempt >= max_attempts:
        should_retry = False
        blocked = blocked or "max_attempts_exceeded"
    if not should_retry:
        warnings.append(blocked or "retry_blocked")
        required.append("stop_retry_or_request_review")
    return TemporalRetryBackoffState(
        retry_id=str(kwargs.get("retry_id") or uuid4().hex),
        attempt_count=attempt,
        first_attempt_at=first,
        last_attempt_at=last,
        next_retry_at=next_retry if should_retry else None,
        backoff_ms=backoff,
        max_retry_deadline=deadline,
        total_retry_duration_ms=total,
        should_retry=should_retry,
        blocked_reason=blocked,
        warnings=warnings,
        required_actions=required,
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )


def build_duration_aggregation(records: list[dict[str, Any]] | None = None, **kwargs: Any) -> TemporalDurationAggregation:
    buckets = {
        "total_agent_run_time_ms": 0,
        "model_duration_ms": 0,
        "tool_duration_ms": 0,
        "command_duration_ms": 0,
        "qa_duration_ms": 0,
        "idle_time_ms": _int(kwargs.get("idle_time_ms")) or 0,
        "user_gap_time_ms": _int(kwargs.get("user_gap_time_ms")) or 0,
        "assistant_gap_time_ms": _int(kwargs.get("assistant_gap_time_ms")) or 0,
        "longest_blocked_state_ms": _int(kwargs.get("longest_blocked_state_ms")) or 0,
    }
    evidence_refs: list[str] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        duration = _int(record.get("duration_ms")) or temporal_duration_ms(record.get("started_at"), record.get("completed_at") or record.get("finished_at")) or 0
        kind = str(record.get("execution_kind") or record.get("scope") or record.get("kind") or "").lower()
        _add_ms(buckets, "total_agent_run_time_ms", duration)
        if kind in {"model", "model_call"}:
            _add_ms(buckets, "model_duration_ms", duration)
        elif kind in {"tool", "tool_call"}:
            _add_ms(buckets, "tool_duration_ms", duration)
        elif kind in {"command", "script"}:
            _add_ms(buckets, "command_duration_ms", duration)
        elif kind in {"qa", "validation"}:
            _add_ms(buckets, "qa_duration_ms", duration)
        if record.get("status") in {"blocked", "waiting_approval"}:
            buckets["longest_blocked_state_ms"] = max(buckets["longest_blocked_state_ms"], duration)
        for ref in record.get("evidence_refs") or []:
            if str(ref) not in evidence_refs:
                evidence_refs.append(str(ref))
    warnings = [] if evidence_refs else ["duration_metrics_without_evidence_refs"]
    return TemporalDurationAggregation(
        aggregation_id=str(kwargs.get("aggregation_id") or uuid4().hex),
        evidence_refs=evidence_refs,
        warnings=warnings,
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
        **buckets,
    )


def build_temporal_evidence_record(**kwargs: Any) -> TemporalEvidenceRecord:
    now = normalize_temporal_timestamp(kwargs.get("now"), fallback_now=True)
    expires = normalize_temporal_timestamp(kwargs.get("expires_at"))
    source_updated = normalize_temporal_timestamp(kwargs.get("source_updated_at"))
    validation = normalize_temporal_timestamp(kwargs.get("validation_at"))
    freshness = build_temporal_freshness_state(
        created_at=kwargs.get("ingested_at") or kwargs.get("observed_at") or kwargs.get("produced_at"),
        stale_after=expires,
        last_verified_at=validation,
        now=now,
        ttl_seconds=kwargs.get("ttl_seconds"),
    )
    stale = freshness.status == "stale"
    warnings = list(freshness.warnings)
    required = list(freshness.required_actions)
    if source_updated and validation and _parse_datetime(source_updated) and _parse_datetime(validation) and _parse_datetime(source_updated) > _parse_datetime(validation):
        stale = True
        warnings.append("source_updated_after_validation")
        required.append("revalidate_temporal_evidence")
    return TemporalEvidenceRecord(
        evidence_id=str(kwargs.get("evidence_id") or uuid4().hex),
        produced_at=normalize_temporal_timestamp(kwargs.get("produced_at")),
        observed_at=normalize_temporal_timestamp(kwargs.get("observed_at")),
        ingested_at=normalize_temporal_timestamp(kwargs.get("ingested_at"), fallback_now=True),
        source_updated_at=source_updated,
        validation_at=validation,
        expires_at=expires,
        freshness_status="stale" if stale else freshness.status,
        evidence_stale=stale,
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(required)),
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )


def build_temporal_migration_backfill_plan(**kwargs: Any) -> TemporalMigrationBackfillPlan:
    source = str(kwargs.get("migration_source") or "unknown")
    target_id = str(kwargs.get("target_id") or kwargs.get("id") or "")
    candidates = [kwargs.get("created_at"), kwargs.get("timestamp"), kwargs.get("started_at"), kwargs.get("updated_at")]
    inferred = next((normalize_temporal_timestamp(value) for value in candidates if normalize_temporal_timestamp(value)), None)
    warnings: list[str] = []
    required: list[str] = []
    if inferred:
        status = "inferred"
        confidence = float(kwargs.get("confidence") if kwargs.get("confidence") is not None else 0.75)
    else:
        status = "unknown"
        confidence = 0.0
        warnings.append("created_at_source_missing")
        required.append("manual_timestamp_review")
    stable_order_key = str(kwargs.get("stable_order_key") or f"{inferred or 'unknown'}:{target_id or uuid4().hex}")
    return TemporalMigrationBackfillPlan(
        plan_id=str(kwargs.get("plan_id") or uuid4().hex),
        target_id=target_id,
        inferred_created_at=inferred,
        timestamp_status=status,
        migration_source=source if source else "unknown",
        confidence=max(0.0, min(1.0, confidence)),
        stable_order_key=stable_order_key,
        warnings=warnings,
        required_actions=required,
        metadata=sanitize_temporal_metadata(kwargs.get("metadata") or {}),
    )


def build_temporal_runtime_trace_source(*, log_policy: TemporalLogPolicy | dict[str, Any] | None = None, log_file: TemporalLogFileCandidate | dict[str, Any] | None = None, ordering: TemporalTimelineOrderingDecision | dict[str, Any] | None = None, timezone_policy: TemporalTimezonePolicy | dict[str, Any] | None = None, title_fallback: TemporalTitleFallback | dict[str, Any] | None = None, retry_backoff: TemporalRetryBackoffState | dict[str, Any] | None = None, duration_aggregation: TemporalDurationAggregation | dict[str, Any] | None = None, temporal_evidence: TemporalEvidenceRecord | dict[str, Any] | None = None, migration_backfill: TemporalMigrationBackfillPlan | dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    source = build_temporal_trace_source(**kwargs)
    extensions = {
        "log_policy": _dump(log_policy),
        "log_file": _dump(log_file),
        "ordering": _dump(ordering),
        "timezone_policy": _dump(timezone_policy),
        "title_fallback": _dump(title_fallback),
        "retry_backoff": _dump(retry_backoff),
        "duration_aggregation": _dump(duration_aggregation),
        "temporal_evidence": _dump(temporal_evidence),
        "migration_backfill": _dump(migration_backfill),
    }
    warnings = list(source.get("warnings") or [])
    required = list(source.get("required_actions") or [])
    for item in extensions.values():
        warnings.extend(item.get("warnings") or [])
        required.extend(item.get("required_actions") or [])
    source.update({key: value for key, value in extensions.items() if value})
    source["warnings"] = list(dict.fromkeys(warnings))
    source["required_actions"] = list(dict.fromkeys(required))
    return sanitize_temporal_metadata(source)


def dump_temporal_log_policy(value: TemporalLogPolicy | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_temporal_log_file_candidate(value: TemporalLogFileCandidate | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_timeline_ordering_decision(value: TemporalTimelineOrderingDecision | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_timezone_format_policy(value: TemporalTimezonePolicy | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_session_title_timestamp_fallback(value: TemporalTitleFallback | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_retry_backoff_state(value: TemporalRetryBackoffState | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_duration_aggregation(value: TemporalDurationAggregation | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_temporal_evidence_record(value: TemporalEvidenceRecord | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)


def dump_temporal_migration_backfill_plan(value: TemporalMigrationBackfillPlan | dict[str, Any]) -> dict[str, Any]:
    return _dump(value)

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
