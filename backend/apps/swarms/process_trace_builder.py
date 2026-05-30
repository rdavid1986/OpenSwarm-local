"""Build ProcessTraceItem objects from existing runtime contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.apps.runtime_timing import RuntimeTimerRecord, dump_runtime_timer
from backend.apps.swarms.process_trace_item import (
    _safe,
    build_process_trace_item,
    build_process_trace_panel,
    build_process_trace_turn_container,
    build_humanized_reasoning_trace_item,
    process_trace_item_from_runtime_metric,
    process_trace_item_from_timeline_event,
)
from backend.apps.swarms.process_trace_subsystems import apply_subsystem_identity_to_trace_item


def redact_process_trace_source(source: Any) -> Any:
    if isinstance(source, RuntimeTimerRecord):
        return _safe(dump_runtime_timer(source))
    return _safe(deepcopy(source))


def normalize_process_trace_source_kind(source: Any) -> str:
    data = redact_process_trace_source(source)
    if isinstance(source, RuntimeTimerRecord):
        return "runtime_timer"
    if not isinstance(data, dict):
        return "unknown"
    if data.get("event_id") or data.get("event_type"):
        return "timeline_event"
    if (
        data.get("reasoning_summary_kind") == "humanized_reasoning_summary"
        or data.get("trace_kind") == "humanized_reasoning_summary"
        or (data.get("summary_source") and (data.get("reasoning_summary") or data.get("summary")))
    ):
        return "humanized_reasoning_summary"
    if data.get("worklog_kind") == "agent_worklog_entry":
        return "agent_worklog"
    if data.get("display_kind") == "context_retrieval_display_item" or data.get("panel_kind") == "context_retrieval_panel":
        return "context_retrieval"
    if data.get("assignment_kind") == "skill_assignment_trace":
        return "skill_assignment_trace"
    if data.get("handoff_kind") == "miniagent_handoff":
        return "miniagent_handoff"
    if data.get("audit_kind") == "swarm_final_audit":
        return "swarm_final_audit"
    if data.get("metric_kind") == "miniagent_task_runtime_metric":
        return "miniagent_task_runtime_metric"
    if data.get("timer_id") and data.get("scope"):
        return "runtime_timer"
    if data.get("evidence_id") or data.get("evidence_ref") or data.get("artifact_id") or data.get("artifact_ref"):
        return "evidence"
    return "unknown"


def _refs(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return list(value)
    text = str(value or "").strip()
    return [text] if text else []




def _reasoning_summary_item(data: dict[str, Any]) -> dict[str, Any]:
    return build_humanized_reasoning_trace_item(
        trace_id=data.get("reasoning_trace_id") or data.get("trace_id"),
        summary=data.get("reasoning_summary") or data.get("summary"),
        source=data.get("summary_source") or data.get("reasoning_summary_source"),
        status=data.get("status") or "completed",
        requested_level=data.get("requested_reasoning_level") or data.get("requested_level") or data.get("thinking_level"),
        applied_level=data.get("applied_reasoning_level") or data.get("applied_level") or data.get("effective_thinking_level"),
        provider=data.get("provider"),
        model=data.get("model"),
        capability_supported=data.get("capability_supported"),
        duration_ms=data.get("duration_ms"),
        related_agent_id=data.get("agent_id") or data.get("related_agent_id"),
        related_task_id=data.get("task_id") or data.get("related_task_id"),
        output_message_id=data.get("output_message_id"),
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )


def _context_item(data: dict[str, Any]) -> dict[str, Any]:
    return build_process_trace_item(
        trace_id=data.get("retrieval_id"),
        kind="context",
        title=data.get("title") or "Retrieved context",
        summary=data.get("summary") or data.get("relevance_reason") or "Context retrieved.",
        status="completed",
        related_task_id=data.get("used_by_task_id"),
        related_agent_id=data.get("used_by_agent_id"),
        evidence_refs=_refs(data.get("evidence_ref")),
        visible_to_user=data.get("visible_to_user", True),
        details={
            "source_type": data.get("source_type"),
            "freshness": data.get("freshness"),
            "confidence": data.get("confidence"),
            "redaction_applied": data.get("redaction_applied"),
        },
    )


def _worklog_item(data: dict[str, Any]) -> dict[str, Any]:
    return build_process_trace_item(
        trace_id=data.get("task_id") or data.get("agent_id"),
        kind="worklog",
        title=data.get("task_title") or "Agent worklog",
        summary=data.get("handoff_summary") or data.get("assigned_skill_reason") or "Agent worklog recorded.",
        status=data.get("status"),
        related_task_id=data.get("task_id"),
        related_agent_id=data.get("agent_id"),
        related_miniagent_id=data.get("miniagent_id"),
        related_skill_id=data.get("assigned_skill_id"),
        evidence_refs=data.get("evidence_refs"),
        artifact_refs=data.get("artifacts_created"),
        created_at=data.get("created_at"),
        details={
            "context_count": len(_refs(data.get("context_used"))) + len(_refs(data.get("memory_context_used"))),
            "action_count": len(_refs(data.get("actions_executed"))),
            "command_count": len(_refs(data.get("commands_executed"))),
            "blocker_count": len(_refs(data.get("blockers"))),
            "validation_count": len(_refs(data.get("validation_results"))),
        },
    )


def _skill_item(data: dict[str, Any]) -> dict[str, Any]:
    return build_process_trace_item(
        trace_id=data.get("skill_id") or data.get("task_id"),
        kind="skill",
        title=data.get("skill_name") or "Skill assignment",
        summary=data.get("assignment_reason") or "Skill assignment recorded.",
        status="completed" if data.get("skill_id") else "warning",
        related_task_id=data.get("task_id"),
        related_agent_id=data.get("agent_id"),
        related_miniagent_id=data.get("miniagent_id"),
        related_skill_id=data.get("skill_id"),
        created_at=data.get("created_at"),
        visible_to_user=data.get("visible_to_user", True),
        details={
            "skill_source": data.get("skill_source"),
            "match_confidence": data.get("match_confidence"),
            "fallback_used": data.get("fallback_used"),
            "matched_count": len(_refs(data.get("matched_requirements"))),
            "missing_count": len(_refs(data.get("missing_requirements"))),
        },
    )


def _handoff_item(data: dict[str, Any]) -> dict[str, Any]:
    return build_process_trace_item(
        trace_id=f"{data.get('source_task_id', '')}->{data.get('target_task_id', '')}",
        kind="handoff",
        title="MiniAgent handoff",
        summary=data.get("completed_work_summary") or "MiniAgent handoff recorded.",
        status="completed",
        related_task_id=data.get("target_task_id") or data.get("source_task_id"),
        related_agent_id=data.get("target_agent_id") or data.get("source_agent_id"),
        evidence_refs=data.get("evidence_refs"),
        artifact_refs=data.get("artifacts"),
        created_at=data.get("created_at"),
        details={
            "source_agent_id": data.get("source_agent_id"),
            "target_agent_id": data.get("target_agent_id"),
            "source_task_id": data.get("source_task_id"),
            "target_task_id": data.get("target_task_id"),
            "blocker_count": len(_refs(data.get("blockers"))),
            "risk_count": len(_refs(data.get("risks"))),
            "validation_summary": data.get("validation_summary"),
        },
    )


def _audit_item(data: dict[str, Any]) -> dict[str, Any]:
    final_status = str(data.get("final_status") or "completed_with_warnings")
    status = "completed" if final_status == "completed" else "warning"
    if "failed" in final_status:
        status = "failed"
    if "blocked" in final_status:
        status = "blocked"
    return build_process_trace_item(
        trace_id=data.get("swarm_id"),
        kind="review",
        title="Swarm final audit",
        summary=data.get("validation_summary") or f"Final status: {final_status}.",
        status=status,
        evidence_refs=data.get("evidence_refs"),
        artifact_refs=data.get("artifact_refs"),
        created_at=data.get("created_at"),
        details={
            "swarm_id": data.get("swarm_id"),
            "final_status": final_status,
            "completed_count": len(_refs(data.get("completed_tasks"))),
            "blocked_count": len(_refs(data.get("blocked_tasks"))),
            "failed_count": len(_refs(data.get("failed_tasks"))),
            "evidence_count": data.get("evidence_count"),
            "artifact_count": data.get("artifact_count"),
            "handoff_count": data.get("handoff_count"),
            "can_mark_swarm_complete": data.get("can_mark_swarm_complete"),
        },
    )


def _evidence_item(data: dict[str, Any]) -> dict[str, Any]:
    evidence_ref = data.get("evidence_ref") or data.get("evidence_id")
    artifact_ref = data.get("artifact_ref") or data.get("artifact_id")
    return build_process_trace_item(
        trace_id=evidence_ref or artifact_ref,
        kind="evidence",
        title=data.get("title") or "Evidence",
        summary=data.get("summary") or "Evidence or artifact reference recorded.",
        status=data.get("status") or "completed",
        evidence_refs=_refs(evidence_ref) + _refs(data.get("evidence_refs")),
        artifact_refs=_refs(artifact_ref) + _refs(data.get("artifact_refs")),
        related_task_id=data.get("task_id"),
        related_agent_id=data.get("agent_id"),
        created_at=data.get("created_at"),
        details={"source_type": data.get("source_type"), "kind": data.get("kind")},
    )


def build_process_trace_item_from_source(source: Any) -> dict[str, Any]:
    source_kind = normalize_process_trace_source_kind(source)
    data = redact_process_trace_source(source)
    if source_kind == "runtime_timer":
        item = process_trace_item_from_runtime_metric(source if isinstance(source, RuntimeTimerRecord) else data)
    elif source_kind == "timeline_event":
        item = process_trace_item_from_timeline_event(data)
    elif source_kind == "humanized_reasoning_summary":
        item = _reasoning_summary_item(data)
    elif source_kind == "agent_worklog":
        item = _worklog_item(data)
    elif source_kind == "context_retrieval":
        if data.get("panel_kind") == "context_retrieval_panel":
            item = build_process_trace_item(
                trace_id=data.get("title"),
                kind="context",
                title=data.get("title") or "Context retrieval panel",
                summary=f"{len(data.get('items') or [])} context item(s) retrieved.",
                status="completed",
                details={"item_count": len(data.get("items") or []), "source_types": data.get("source_types", [])},
                visible_to_user=data.get("visible_to_user", True),
            )
        else:
            item = _context_item(data)
    elif source_kind == "skill_assignment_trace":
        item = _skill_item(data)
    elif source_kind == "miniagent_handoff":
        item = _handoff_item(data)
    elif source_kind == "swarm_final_audit":
        item = _audit_item(data)
    elif source_kind == "miniagent_task_runtime_metric":
        item = process_trace_item_from_runtime_metric(data)
    elif source_kind == "evidence":
        item = _evidence_item(data)
    else:
        item = build_process_trace_item(
            kind="unknown",
            title=data.get("title") if isinstance(data, dict) else "Unknown trace source",
            summary=data.get("summary") if isinstance(data, dict) else "Unknown trace source.",
            details={"source_kind": source_kind},
        )
    item = apply_subsystem_identity_to_trace_item(item)
    item["metadata"] = {**dict(item.get("metadata") or {}), "source_kind": source_kind}
    return item


def build_process_trace_items_from_sources(sources: list[Any] | None) -> list[dict[str, Any]]:
    return [build_process_trace_item_from_source(source) for source in (sources or [])]




def _unique_refs_from_items(items: list[dict[str, Any]], key: str) -> list[Any]:
    refs: list[Any] = []
    for item in items:
        for ref in _refs(item.get(key)):
            if ref not in refs:
                refs.append(ref)
    return refs


def _unique_related_from_items(items: list[dict[str, Any]], key: str) -> list[Any]:
    refs: list[Any] = []
    for item in items:
        value = item.get(key)
        if value not in (None, "") and value not in refs:
            refs.append(value)
    return refs


def _status_from_trace_items(items: list[dict[str, Any]]) -> str:
    statuses = [str(item.get("status") or "").strip().lower() for item in items]
    if not statuses:
        return "planned"
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if "running" in statuses:
        return "running"
    if "warning" in statuses:
        return "warning"
    if all(status == "completed" for status in statuses):
        return "completed"
    return "planned"


def build_process_trace_turn_container_from_sources(
    sources: list[Any] | None,
    *,
    turn_trace_id: Any = None,
    title: Any = "Thought",
    status: Any = None,
    turn_id: Any = None,
    message_id: Any = None,
    action_id: Any = None,
    started_at: Any = None,
    finished_at: Any = None,
    duration_ms: Any = None,
    output_message_id: Any = None,
    default_collapsed_after_finish: bool = True,
    default_expanded_while_running: bool = False,
    visible_to_user: bool = True,
    internal_only: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a privacy-safe turn container from existing traceable sources."""

    source_list = sources or []
    items = build_process_trace_items_from_sources(source_list)
    source_kinds = [normalize_process_trace_source_kind(source) for source in source_list]
    effective_status = status or _status_from_trace_items(items)
    merged_metadata = {
        "source_kind": "process_trace_turn_sources",
        "source_count": len(source_list),
        "source_kinds": source_kinds,
        **dict(metadata or {}),
    }

    return build_process_trace_turn_container(
        items=items,
        turn_trace_id=turn_trace_id,
        title=title,
        status=effective_status,
        turn_id=turn_id,
        message_id=message_id,
        action_id=action_id,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        output_message_id=output_message_id,
        related_task_ids=_unique_related_from_items(items, "related_task_id"),
        related_agent_ids=_unique_related_from_items(items, "related_agent_id"),
        related_miniagent_ids=_unique_related_from_items(items, "related_miniagent_id"),
        evidence_refs=_unique_refs_from_items(items, "evidence_refs"),
        artifact_refs=_unique_refs_from_items(items, "artifact_refs"),
        default_collapsed_after_finish=default_collapsed_after_finish,
        default_expanded_while_running=default_expanded_while_running,
        visible_to_user=visible_to_user,
        internal_only=internal_only,
        metadata=merged_metadata,
    )


def build_process_trace_panel_from_sources(sources: list[Any] | None, panel_title: str = "Process Trace") -> dict[str, Any]:
    return build_process_trace_panel(build_process_trace_items_from_sources(sources), panel_title=panel_title)
