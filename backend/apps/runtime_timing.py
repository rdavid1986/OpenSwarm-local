"""Side-effect-free runtime timer contract.

RTM.1 intentionally defines only an in-memory record plus pure-ish helpers.
It does not persist timers, emit events, call providers, or update UI state.
Future phases can store/emits these records from lifecycle integration points.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


RuntimeTimerScope = Literal[
    "swarm",
    "agent",
    "mini_agent",
    "planner",
    "refinement",
    "model_call",
    "tool_call",
    "validation",
    "benchmark",
    "benchmark_test",
    "model_load",
]

RuntimeTimerState = Literal[
    "thinking",
    "planning",
    "working",
    "executing",
    "validating",
    "loading_model",
    "completed",
    "failed",
    "cancelled",
]

RuntimeTimerStatus = Literal["running", "completed", "failed", "cancelled"]


VALID_RUNTIME_TIMER_SCOPES: set[str] = {
    "swarm",
    "agent",
    "mini_agent",
    "planner",
    "refinement",
    "model_call",
    "tool_call",
    "validation",
    "benchmark",
    "benchmark_test",
    "model_load",
}

VALID_RUNTIME_TIMER_STATES: set[str] = {
    "thinking",
    "planning",
    "working",
    "executing",
    "validating",
    "loading_model",
    "completed",
    "failed",
    "cancelled",
}

VALID_RUNTIME_TIMER_STATUSES: set[str] = {"running", "completed", "failed", "cancelled"}

DEFAULT_RUNTIME_TIMER_SCOPE: RuntimeTimerScope = "model_call"
DEFAULT_RUNTIME_TIMER_STATE: RuntimeTimerState = "working"
DEFAULT_RUNTIME_TIMER_STATUS: RuntimeTimerStatus = "running"


@dataclass(frozen=True)
class RuntimeTimerRecord:
    timer_id: str
    scope: RuntimeTimerScope
    label: str
    state: RuntimeTimerState
    started_at: str
    finished_at: str | None = None
    duration_ms: int | None = None
    status: RuntimeTimerStatus = "running"
    swarm_id: str | None = None
    agent_id: str | None = None
    mini_agent_id: str | None = None
    task_id: str | None = None
    model: str | None = None
    route: str | None = None
    flow: str | None = None
    output_id: str | None = None
    candidate_iteration_id: str | None = None
    evidence_refs: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normalize_choice(value: Any, *, valid: set[str], default: str, field_name: str, strict: bool) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in valid:
        return normalized
    if strict:
        raise ValueError(f"Unknown runtime timer {field_name}: {value!r}")
    return default


def normalize_runtime_timer_scope(
    value: Any,
    *,
    default: RuntimeTimerScope = DEFAULT_RUNTIME_TIMER_SCOPE,
    strict: bool = False,
) -> RuntimeTimerScope:
    return _normalize_choice(
        value,
        valid=VALID_RUNTIME_TIMER_SCOPES,
        default=default,
        field_name="scope",
        strict=strict,
    )  # type: ignore[return-value]


def normalize_runtime_timer_state(
    value: Any,
    *,
    default: RuntimeTimerState = DEFAULT_RUNTIME_TIMER_STATE,
    strict: bool = False,
) -> RuntimeTimerState:
    return _normalize_choice(
        value,
        valid=VALID_RUNTIME_TIMER_STATES,
        default=default,
        field_name="state",
        strict=strict,
    )  # type: ignore[return-value]


def normalize_runtime_timer_status(
    value: Any,
    *,
    default: RuntimeTimerStatus = DEFAULT_RUNTIME_TIMER_STATUS,
    strict: bool = False,
) -> RuntimeTimerStatus:
    return _normalize_choice(
        value,
        valid=VALID_RUNTIME_TIMER_STATUSES,
        default=default,
        field_name="status",
        strict=strict,
    )  # type: ignore[return-value]


def runtime_timer_duration_ms(
    timer_or_started_at: RuntimeTimerRecord | dict[str, Any] | str | datetime | None,
    finished_at: str | datetime | None = None,
    *,
    now: str | datetime | None = None,
) -> int | None:
    if isinstance(timer_or_started_at, RuntimeTimerRecord):
        started_at = timer_or_started_at.started_at
        finished_at = finished_at or timer_or_started_at.finished_at
    elif isinstance(timer_or_started_at, dict):
        started_at = timer_or_started_at.get("started_at")
        finished_at = finished_at or timer_or_started_at.get("finished_at")
    else:
        started_at = timer_or_started_at

    start = _parse_datetime(started_at)
    finish = _parse_datetime(finished_at) or _parse_datetime(now) or _parse_datetime(_now_iso())
    if start is None or finish is None:
        return None
    return max(0, int((finish - start).total_seconds() * 1000))


def start_runtime_timer(
    *,
    scope: Any,
    label: str,
    state: Any = DEFAULT_RUNTIME_TIMER_STATE,
    started_at: str | datetime | None = None,
    timer_id: str | None = None,
    swarm_id: str | None = None,
    agent_id: str | None = None,
    mini_agent_id: str | None = None,
    task_id: str | None = None,
    model: str | None = None,
    route: str | None = None,
    flow: str | None = None,
    output_id: str | None = None,
    candidate_iteration_id: str | None = None,
    evidence_refs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeTimerRecord:
    started = started_at.isoformat() if isinstance(started_at, datetime) else (started_at or _now_iso())
    return RuntimeTimerRecord(
        timer_id=timer_id or uuid4().hex,
        scope=normalize_runtime_timer_scope(scope),
        label=str(label or "").strip() or "Runtime timer",
        state=normalize_runtime_timer_state(state),
        started_at=started,
        finished_at=None,
        duration_ms=None,
        status="running",
        swarm_id=swarm_id,
        agent_id=agent_id,
        mini_agent_id=mini_agent_id,
        task_id=task_id,
        model=model,
        route=route,
        flow=flow,
        output_id=output_id,
        candidate_iteration_id=candidate_iteration_id,
        evidence_refs=list(evidence_refs or []),
        error=None,
        metadata=dict(metadata or {}),
    )


def finish_runtime_timer(
    timer: RuntimeTimerRecord,
    *,
    finished_at: str | datetime | None = None,
    state: Any = "completed",
    metadata: dict[str, Any] | None = None,
) -> RuntimeTimerRecord:
    finished = finished_at.isoformat() if isinstance(finished_at, datetime) else (finished_at or _now_iso())
    merged_metadata = {**timer.metadata, **(metadata or {})}
    return replace(
        timer,
        state=normalize_runtime_timer_state(state, default="completed"),
        finished_at=finished,
        duration_ms=runtime_timer_duration_ms(timer.started_at, finished),
        status="completed",
        metadata=merged_metadata,
    )


def fail_runtime_timer(
    timer: RuntimeTimerRecord,
    *,
    error: Any,
    finished_at: str | datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeTimerRecord:
    finished = finished_at.isoformat() if isinstance(finished_at, datetime) else (finished_at or _now_iso())
    merged_metadata = {**timer.metadata, **(metadata or {})}
    return replace(
        timer,
        state="failed",
        finished_at=finished,
        duration_ms=runtime_timer_duration_ms(timer.started_at, finished),
        status="failed",
        error=str(error) if error is not None else None,
        metadata=merged_metadata,
    )


def cancel_runtime_timer(
    timer: RuntimeTimerRecord,
    *,
    error: Any = None,
    finished_at: str | datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeTimerRecord:
    finished = finished_at.isoformat() if isinstance(finished_at, datetime) else (finished_at or _now_iso())
    merged_metadata = {**timer.metadata, **(metadata or {})}
    return replace(
        timer,
        state="cancelled",
        finished_at=finished,
        duration_ms=runtime_timer_duration_ms(timer.started_at, finished),
        status="cancelled",
        error=str(error) if error is not None else timer.error,
        metadata=merged_metadata,
    )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def dump_runtime_timer(timer: RuntimeTimerRecord | dict[str, Any]) -> dict[str, Any]:
    data = asdict(timer) if isinstance(timer, RuntimeTimerRecord) else dict(timer)
    return _json_safe(data)
