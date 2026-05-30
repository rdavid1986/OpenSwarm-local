"""Privacy-safe chat response runtime metrics.

This module stores technical timing metadata for SwarmCard/AgentCard chat
responses. It must never store private chain-of-thought or full user/assistant
message content by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from backend.apps.runtime_timing import (
    RuntimeTimerRecord,
    dump_runtime_timer,
    fail_runtime_timer,
    finish_runtime_timer,
    runtime_timer_duration_ms,
    start_runtime_timer,
)

ChatCardType = Literal["swarm", "agent", "unknown"]
ChatMetricStatus = Literal["running", "completed", "failed", "cancelled"]

METRIC_KIND = "chat_response_metric"
METRIC_VERSION = "openswarm.chat_response_metric.v1"

SENSITIVE_METADATA_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "bearer",
    "body",
    "content",
    "cookie",
    "credential",
    "credentials",
    "message",
    "messages",
    "password",
    "private_key",
    "prompt",
    "raw",
    "request",
    "response",
    "secret",
    "set-cookie",
    "text",
    "token",
}

_ALLOWED_CARD_TYPES = {"swarm", "agent"}
_ALLOWED_STATUSES = {"running", "completed", "failed", "cancelled"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_card_type(value: Any) -> ChatCardType:
    normalized = str(value or "").strip().lower()
    if normalized in _ALLOWED_CARD_TYPES:
        return normalized  # type: ignore[return-value]
    return "unknown"


def _normalize_status(value: Any) -> ChatMetricStatus:
    normalized = str(value or "").strip().lower()
    if normalized in _ALLOWED_STATUSES:
        return normalized  # type: ignore[return-value]
    return "running"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in SENSITIVE_METADATA_KEYS or any(marker in normalized for marker in ("password", "secret", "token", "api_key", "private_key"))


def sanitize_chat_metric_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Return JSON-safe metadata without private text or secret-like values."""

    safe: dict[str, Any] = {}
    for key, value in dict(metadata or {}).items():
        if _is_sensitive_key(key):
            safe[str(key)] = "[redacted]"
            continue
        if isinstance(value, dict):
            safe[str(key)] = sanitize_chat_metric_metadata(value)
            continue
        if isinstance(value, list):
            safe[str(key)] = [
                sanitize_chat_metric_metadata(item) if isinstance(item, dict) else _json_safe(item)
                for item in value
            ]
            continue
        safe[str(key)] = _json_safe(value)
    return safe


@dataclass(frozen=True)
class ChatResponseMetric:
    metric_kind: str
    metric_version: str
    response_metric_id: str
    conversation_id: str | None
    message_id: str | None
    parent_message_id: str | None
    card_id: str | None
    card_type: ChatCardType
    mode: str | None
    route: str | None
    flow: str | None
    model: str | None
    provider: str | None
    started_at: str
    first_token_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    queue_ms: int | None = None
    context_build_ms: int | None = None
    memory_retrieval_ms: int | None = None
    model_ms: int | None = None
    tool_ms: int | None = None
    action_ms: int | None = None
    validation_ms: int | None = None
    persistence_ms: int | None = None
    status: ChatMetricStatus = "running"
    error_type: str | None = None
    project_type: str | None = None
    task_type: str | None = None
    created_output: bool = False
    used_skills: list[str] = field(default_factory=list)
    used_modes: list[str] = field(default_factory=list)
    used_actions: list[str] = field(default_factory=list)
    used_tools: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_timer: RuntimeTimerRecord | None = None


def start_chat_response_metric(
    *,
    conversation_id: str | None = None,
    message_id: str | None = None,
    parent_message_id: str | None = None,
    card_id: str | None = None,
    card_type: Any = "unknown",
    mode: str | None = None,
    route: str | None = None,
    flow: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    started_at: str | datetime | None = None,
    response_metric_id: str | None = None,
    project_type: str | None = None,
    task_type: str | None = None,
    created_output: bool = False,
    used_skills: list[str] | None = None,
    used_modes: list[str] | None = None,
    used_actions: list[str] | None = None,
    used_tools: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChatResponseMetric:
    metric_id = response_metric_id or uuid4().hex
    started = started_at.isoformat() if isinstance(started_at, datetime) else (started_at or _now_iso())
    timer = start_runtime_timer(
        timer_id=f"chat-{metric_id}",
        scope="model_call",
        label="Chat response",
        state="thinking",
        started_at=started,
        swarm_id=card_id if _normalize_card_type(card_type) == "swarm" else None,
        agent_id=card_id if _normalize_card_type(card_type) == "agent" else None,
        model=model,
        route=route,
        flow=flow,
        evidence_refs=evidence_refs or [],
        metadata={
            "metric_kind": METRIC_KIND,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "parent_message_id": parent_message_id,
            "card_type": _normalize_card_type(card_type),
            "mode": mode,
            "provider": provider,
        },
    )
    return ChatResponseMetric(
        metric_kind=METRIC_KIND,
        metric_version=METRIC_VERSION,
        response_metric_id=metric_id,
        conversation_id=_optional_text(conversation_id),
        message_id=_optional_text(message_id),
        parent_message_id=_optional_text(parent_message_id),
        card_id=_optional_text(card_id),
        card_type=_normalize_card_type(card_type),
        mode=_optional_text(mode),
        route=_optional_text(route),
        flow=_optional_text(flow),
        model=_optional_text(model),
        provider=_optional_text(provider),
        started_at=started,
        status="running",
        project_type=_optional_text(project_type),
        task_type=_optional_text(task_type),
        created_output=bool(created_output),
        used_skills=list(used_skills or []),
        used_modes=list(used_modes or []),
        used_actions=list(used_actions or []),
        used_tools=list(used_tools or []),
        evidence_refs=list(evidence_refs or []),
        metadata=sanitize_chat_metric_metadata(metadata),
        runtime_timer=timer,
    )


def mark_chat_response_first_token(
    metric: ChatResponseMetric,
    *,
    first_token_at: str | datetime | None = None,
) -> ChatResponseMetric:
    first_token = first_token_at.isoformat() if isinstance(first_token_at, datetime) else (first_token_at or _now_iso())
    return replace(
        metric,
        first_token_at=first_token,
        queue_ms=runtime_timer_duration_ms(metric.started_at, first_token),
    )


def finish_chat_response_metric(
    metric: ChatResponseMetric,
    *,
    finished_at: str | datetime | None = None,
    metadata: dict[str, Any] | None = None,
    **timing_overrides: Any,
) -> ChatResponseMetric:
    finished = finished_at.isoformat() if isinstance(finished_at, datetime) else (finished_at or _now_iso())
    runtime_timer = finish_runtime_timer(metric.runtime_timer, finished_at=finished) if metric.runtime_timer else None
    merged_metadata = {**metric.metadata, **sanitize_chat_metric_metadata(metadata)}
    return replace(
        metric,
        finished_at=finished,
        duration_ms=runtime_timer_duration_ms(metric.started_at, finished),
        status="completed",
        runtime_timer=runtime_timer,
        metadata=merged_metadata,
        context_build_ms=timing_overrides.get("context_build_ms", metric.context_build_ms),
        memory_retrieval_ms=timing_overrides.get("memory_retrieval_ms", metric.memory_retrieval_ms),
        model_ms=timing_overrides.get("model_ms", metric.model_ms),
        tool_ms=timing_overrides.get("tool_ms", metric.tool_ms),
        action_ms=timing_overrides.get("action_ms", metric.action_ms),
        validation_ms=timing_overrides.get("validation_ms", metric.validation_ms),
        persistence_ms=timing_overrides.get("persistence_ms", metric.persistence_ms),
    )


def fail_chat_response_metric(
    metric: ChatResponseMetric,
    *,
    error_type: str,
    finished_at: str | datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChatResponseMetric:
    finished = finished_at.isoformat() if isinstance(finished_at, datetime) else (finished_at or _now_iso())
    runtime_timer = fail_runtime_timer(metric.runtime_timer, error=error_type, finished_at=finished) if metric.runtime_timer else None
    merged_metadata = {**metric.metadata, **sanitize_chat_metric_metadata(metadata)}
    return replace(
        metric,
        finished_at=finished,
        duration_ms=runtime_timer_duration_ms(metric.started_at, finished),
        status="failed",
        error_type=_text(error_type, "unknown_error"),
        runtime_timer=runtime_timer,
        metadata=merged_metadata,
    )


def dump_chat_response_metric(metric: ChatResponseMetric | dict[str, Any]) -> dict[str, Any]:
    if isinstance(metric, dict):
        dumped = dict(metric)
        dumped["metadata"] = sanitize_chat_metric_metadata(dumped.get("metadata") if isinstance(dumped.get("metadata"), dict) else {})
        return _json_safe(dumped)

    dumped = {
        "metric_kind": metric.metric_kind,
        "metric_version": metric.metric_version,
        "response_metric_id": metric.response_metric_id,
        "conversation_id": metric.conversation_id,
        "message_id": metric.message_id,
        "parent_message_id": metric.parent_message_id,
        "card_id": metric.card_id,
        "card_type": metric.card_type,
        "mode": metric.mode,
        "route": metric.route,
        "flow": metric.flow,
        "model": metric.model,
        "provider": metric.provider,
        "started_at": metric.started_at,
        "first_token_at": metric.first_token_at,
        "finished_at": metric.finished_at,
        "duration_ms": metric.duration_ms,
        "queue_ms": metric.queue_ms,
        "context_build_ms": metric.context_build_ms,
        "memory_retrieval_ms": metric.memory_retrieval_ms,
        "model_ms": metric.model_ms,
        "tool_ms": metric.tool_ms,
        "action_ms": metric.action_ms,
        "validation_ms": metric.validation_ms,
        "persistence_ms": metric.persistence_ms,
        "status": metric.status,
        "error_type": metric.error_type,
        "project_type": metric.project_type,
        "task_type": metric.task_type,
        "created_output": metric.created_output,
        "used_skills": list(metric.used_skills),
        "used_modes": list(metric.used_modes),
        "used_actions": list(metric.used_actions),
        "used_tools": list(metric.used_tools),
        "evidence_refs": list(metric.evidence_refs),
        "metadata": sanitize_chat_metric_metadata(metric.metadata),
        "runtime_timer": dump_runtime_timer(metric.runtime_timer) if metric.runtime_timer else None,
    }
    return _json_safe(dumped)


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(needle in haystack for needle in needles)


def _safe_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def classify_chat_metric_safe_metadata(input: dict[str, Any] | None) -> dict[str, Any]:
    """Classify a chat metric using only safe routing/runtime metadata.

    This helper must not inspect prompt, response, message, body, text or raw
    content fields. It is intentionally coarse, deterministic and privacy-safe.
    """

    data = dict(input or {})
    mode = str(data.get("mode") or "").strip().lower()
    route = str(data.get("route") or "").strip().lower()
    flow = str(data.get("flow") or "").strip().lower()
    artifact_kind = str(data.get("artifact_kind") or "").strip().lower()
    card_type = _normalize_card_type(data.get("card_type"))
    used_tools = _safe_list(data.get("used_tools"))
    used_actions = _safe_list(data.get("used_actions"))
    used_skills = _safe_list(data.get("used_skills"))

    task_type = "unknown"
    project_type = "unknown"
    intent_type = "chat"
    complexity_level = "low"
    warnings: list[str] = []

    haystack = " ".join([
        mode,
        route,
        flow,
        artifact_kind,
        " ".join(used_tools),
        " ".join(used_actions),
        " ".join(used_skills),
    ])

    if _contains_any(haystack, ("skill_import", "import_skill", "skill import")):
        task_type = "skill_import"
        project_type = "skill"
        intent_type = "skill_import"
        complexity_level = "medium"
    elif _contains_any(haystack, ("skill_review", "reviewer", "improvement_proposal", "proposal_diff")):
        task_type = "skill_review"
        project_type = "skill"
        intent_type = "review"
        complexity_level = "medium"
    elif _contains_any(haystack, ("skill_builder", "skill-builder", "skill builder")) or mode == "skill_builder":
        task_type = "skill_builder"
        project_type = "skill"
        intent_type = "skill_creation"
        complexity_level = "medium"
    elif _contains_any(haystack, ("refine", "refinement", "candidate_iteration", "preview_refinement")):
        task_type = "refinement"
        project_type = "application" if artifact_kind or data.get("created_output") else "unknown"
        intent_type = "refine"
        complexity_level = "medium"
    elif _contains_any(haystack, ("debug", "fix_error", "bug", "diagnostic")):
        task_type = "debug"
        intent_type = "debug"
        complexity_level = "medium"
    elif _contains_any(haystack, ("browser", "research", "web_grounding", "web_search")):
        task_type = "research"
        project_type = "research"
        intent_type = "research"
        complexity_level = "medium"
    elif _contains_any(haystack, ("mcp", "tool", "action", "safeshell")) or used_tools or used_actions:
        task_type = "tool_action"
        intent_type = "execute"
        complexity_level = "medium"
    elif _contains_any(haystack, ("game", "unity", "blender", "3d", "g3d")):
        task_type = "game_3d"
        project_type = "game_3d"
        intent_type = "build"
        complexity_level = "high"
    elif _contains_any(haystack, ("desktop", "windows_app", "macos", "linux_app")):
        task_type = "desktop_app"
        project_type = "desktop_app"
        intent_type = "build"
        complexity_level = "high"
    elif _contains_any(haystack, ("mobile", "android", "ios")):
        task_type = "mobile_app"
        project_type = "mobile_app"
        intent_type = "build"
        complexity_level = "high"
    elif _contains_any(haystack, ("static_app", "landing", "website", "web_app", "app_builder", "implementation")):
        task_type = "app_builder"
        project_type = "application"
        intent_type = "build"
        complexity_level = "high"
    elif _contains_any(haystack, ("plan", "planner", "dag")):
        task_type = "planning"
        intent_type = "plan"
        complexity_level = "medium"
    elif _contains_any(haystack, ("config", "configuration", "settings")):
        task_type = "configuration"
        intent_type = "configure"
        complexity_level = "low"
    elif mode == "ask" or card_type in {"swarm", "agent"}:
        task_type = "ask"

    if bool(data.get("created_output")) and project_type == "unknown":
        project_type = "application"
    if bool(data.get("requires_research")) and task_type not in {"research", "skill_import", "skill_review"}:
        warnings.append("requires_research_without_research_task_type")

    return {
        "project_type": project_type,
        "task_type": task_type,
        "intent_type": intent_type,
        "complexity_level": complexity_level,
        "requires_tools": bool(used_tools or used_actions or data.get("used_tools") or data.get("used_actions")),
        "requires_research": bool(data.get("requires_research") or task_type == "research"),
        "requires_swarm": card_type == "swarm",
        "creates_output": bool(data.get("created_output")),
        "confidence": "low" if task_type == "unknown" else "medium",
        "warnings": warnings,
    }
