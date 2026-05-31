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
from backend.apps.swarms.miniagent_skill_adaptive import build_adaptive_skill_trace_items


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
    if data.get("adaptive_kind") in {
        "miniagent_skill_gap",
        "miniagent_adaptive_state",
        "swarm_skill_resolution_decision",
        "adaptive_research_request",
        "adaptive_skill_candidate_contract",
        "miniagent_resume_contract",
        "adaptive_skill_metrics",
    }:
        return "miniagent_skill_adaptive"
    if data.get("audit_kind") == "swarm_final_audit":
        return "swarm_final_audit"
    if data.get("report_kind") == "skill_import_preview_report" or data.get("source_kind") in {"skill_import_preview", "skill_import_candidate"}:
        return "skill_import_preview"
    if (
        data.get("harness_kind") == "skill_harness_full_report"
        or data.get("source_kind") == "skill_harness"
        or data.get("contract_kind") == "skill_test_case_contract"
        or data.get("report_kind") in {"skill_dry_run_report", "skill_runtime_validation_report", "skill_evidence_quality_report"}
        or data.get("suite_kind") == "skill_regression_suite"
        or data.get("gate_kind") == "skill_promotion_gate"
    ):
        return "skill_harness"
    if data.get("snapshot_kind") == "skill_version_snapshot":
        return "skill_version_snapshot"
    if data.get("plan_kind") == "skill_rollback_plan":
        return "skill_rollback_plan"
    if data.get("summary_kind") == "skill_effectiveness_summary" or data.get("record_kind") == "skill_effectiveness_metric_record" or data.get("source_kind") == "skill_effectiveness_metrics":
        return "skill_effectiveness_metrics"
    if data.get("metric_kind") == "miniagent_task_runtime_metric":
        return "miniagent_task_runtime_metric"
    if data.get("runtime_kind") == "model_runtime_resolution" or data.get("source_kind") == "model_runtime":
        return "model_runtime"
    if data.get("metric_kind") == "ollama_runtime_metrics":
        return "runtime_timer"
    explicit_source = str(data.get("source_kind") or data.get("trace_source_kind") or data.get("producer_kind") or "").strip().lower()
    if explicit_source == "model_runtime":
        return "model_runtime"
    if explicit_source in {"tool_trace", "tool_call", "tool_result", "tool_error"}:
        return "tool_trace"
    if explicit_source in {"action_trace", "pending_action", "approval", "action_result"}:
        return "action_trace"
    if explicit_source in {"validation_trace", "structured_output_validation"}:
        return "validation_trace"
    if explicit_source in {"skill_trace", "skill_use", "skill_result"}:
        return "skill_trace"
    if explicit_source in {"file_trace", "diff_trace", "workspace_trace", "workspace_file_trace"}:
        return "file_workspace_trace"
    if explicit_source in {"output_trace", "artifact_trace"}:
        return "file_workspace_trace"
    if explicit_source in {"miniagent_trace", "miniagent_task"}:
        return "miniagent_trace"
    if explicit_source in {"handoff_trace", "miniagent_handoff_trace"}:
        return "handoff_trace"
    if data.get("tool_call_id") or data.get("tool_name") or data.get("function_name") or data.get("kind") == "tool":
        return "tool_trace"
    if data.get("pending_action_id") or data.get("action_name") or data.get("approval_status") or data.get("kind") == "action":
        return "action_trace"
    if data.get("skill_trace_kind") or (data.get("skill_id") and (data.get("usage_reason") or data.get("input_context") or data.get("risk"))):
        return "skill_trace"
    if any(
        data.get(key)
        for key in (
            "file_trace_kind",
            "workspace_trace_kind",
            "read_files",
            "created_files",
            "modified_files",
            "deleted_files",
            "affected_paths",
            "workspace_path",
            "diff_summary",
            "file_operation_kind",
            "candidate_id",
            "stable_output_id",
            "output_id",
        )
    ):
        return "file_workspace_trace"
    if data.get("miniagent_trace_kind") or (data.get("miniagent_id") and data.get("task_id")):
        return "miniagent_trace"
    if data.get("handoff_trace_kind") or (data.get("source_agent_id") and data.get("target_agent_id")):
        return "handoff_trace"
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


def _first_text(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        text = str(data.get(key) or "").strip()
        if text:
            return text
    return default


def _compact_value(value: Any, fallback: str = "unavailable") -> Any:
    if value in (None, ""):
        return fallback
    safe = _safe(value)
    if isinstance(safe, str):
        text = safe.strip()
        return text[:600] + "..." if len(text) > 600 else text
    if isinstance(safe, (list, tuple)):
        return list(safe)[:20]
    if isinstance(safe, dict):
        return {key: safe[key] for key in list(safe)[:20]}
    return safe


def _duration(data: dict[str, Any]) -> Any:
    return data.get("duration_ms") or data.get("elapsed_ms") or data.get("latency_ms")


def _approval_status(data: dict[str, Any]) -> str:
    return _first_text(data, "approval_status", "approval_state", "permission_status", default="unavailable")


def _status_from_operational_source(data: dict[str, Any]) -> str:
    explicit = _first_text(data, "status", "state")
    if explicit:
        return explicit
    approval = _approval_status(data).lower()
    if approval in {"pending", "required", "requires_approval", "waiting_approval"}:
        return "blocked"
    if data.get("error") or data.get("failure_reason"):
        return "failed"
    if data.get("result") is not None or data.get("output") is not None or data.get("finished_at"):
        return "completed"
    if data.get("started_at"):
        return "running"
    return "planned"


def build_tool_trace_item(data: dict[str, Any]) -> dict[str, Any]:
    """Build a side-effect-free ToolCore trace item from a tool call/result source."""

    tool_name = _first_text(data, "tool_name", "name", "function_name", default="Unknown tool")
    return build_process_trace_item(
        trace_id=data.get("trace_id") or data.get("tool_call_id") or data.get("call_id") or data.get("id"),
        kind="tool",
        subsystem="ToolCore",
        title=f"Tool: {tool_name}",
        summary=_first_text(data, "summary", "result_summary", "output_summary", "error", default=f"Tool {tool_name} recorded."),
        status=_status_from_operational_source(data),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at") or data.get("ended_at"),
        duration_ms=_duration(data),
        evidence_refs=data.get("evidence_refs"),
        artifact_refs=data.get("artifact_refs"),
        related_task_id=data.get("task_id") or data.get("related_task_id"),
        related_agent_id=data.get("agent_id") or data.get("related_agent_id"),
        related_miniagent_id=data.get("miniagent_id") or data.get("related_miniagent_id"),
        related_action_id=data.get("related_action_id") or data.get("action_id"),
        created_at=data.get("created_at"),
        details={
            "tool_name": tool_name,
            "input_summary": _compact_value(data.get("input_summary") or data.get("arguments") or data.get("input")),
            "permission_policy": _first_text(data, "permission_policy", "policy", default="unavailable"),
            "approval_status": _approval_status(data),
            "result_summary": _compact_value(data.get("result_summary") or data.get("result") or data.get("output")),
            "error": data.get("error"),
            "affected_files": _refs(data.get("affected_files")) + _refs(data.get("affected_paths")),
            "source_kind": _first_text(data, "source_kind", default="tool_trace"),
        },
    )


def build_action_trace_item(data: dict[str, Any]) -> dict[str, Any]:
    """Build a side-effect-free ActionCore trace item from action/pending-action data."""

    action_name = _first_text(data, "action_name", "name", "type", default="Unknown action")
    action_id = data.get("action_id") or data.get("pending_action_id") or data.get("related_action_id") or data.get("id")
    return build_process_trace_item(
        trace_id=data.get("trace_id") or action_id,
        kind="action",
        subsystem="ActionCore",
        title=f"Action: {action_name}",
        summary=_first_text(data, "summary", "result_summary", "error", default=f"Action {action_name} recorded."),
        status=_status_from_operational_source(data),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at") or data.get("ended_at"),
        duration_ms=_duration(data),
        evidence_refs=data.get("evidence_refs"),
        artifact_refs=data.get("artifact_refs"),
        related_task_id=data.get("task_id") or data.get("related_task_id"),
        related_agent_id=data.get("agent_id") or data.get("related_agent_id"),
        related_miniagent_id=data.get("miniagent_id") or data.get("related_miniagent_id"),
        related_action_id=action_id,
        created_at=data.get("created_at"),
        details={
            "action_name": action_name,
            "input_summary": _compact_value(data.get("input_summary") or data.get("payload") or data.get("input")),
            "permission_policy": _first_text(data, "permission_policy", "policy", default="unavailable"),
            "approval_status": _approval_status(data),
            "result_summary": _compact_value(data.get("result_summary") or data.get("result") or data.get("output")),
            "error": data.get("error"),
            "affected_files": _refs(data.get("affected_files")) + _refs(data.get("affected_paths")),
            "source_kind": _first_text(data, "source_kind", default="action_trace"),
        },
    )


def build_skill_trace_item(data: dict[str, Any]) -> dict[str, Any]:
    """Build a side-effect-free SkillCore trace item from skill-use data."""

    skill_id = data.get("skill_id") or data.get("id") or data.get("related_skill_id")
    skill_name = _first_text(data, "skill_name", "name", default=str(skill_id or "Unknown skill"))
    return build_process_trace_item(
        trace_id=data.get("trace_id") or skill_id,
        kind="skill",
        subsystem="SkillCore",
        title=f"Skill: {skill_name}",
        summary=_first_text(data, "summary", "reason", "usage_reason", "motivo", default=f"Skill {skill_name} recorded."),
        status=data.get("status") or "completed",
        evidence_refs=data.get("evidence_refs"),
        artifact_refs=data.get("artifact_refs"),
        related_task_id=data.get("task_id") or data.get("related_task_id"),
        related_agent_id=data.get("agent_id") or data.get("related_agent_id"),
        related_miniagent_id=data.get("miniagent_id") or data.get("related_miniagent_id"),
        related_skill_id=skill_id,
        created_at=data.get("created_at"),
        details={
            "skill_id": skill_id,
            "skill_name": skill_name,
            "usage_reason": _first_text(data, "reason", "usage_reason", "assignment_reason", default="unavailable"),
            "scope": data.get("scope") or "unavailable",
            "input_context": _compact_value(data.get("input_context") or data.get("context") or data.get("input")),
            "output_summary": _compact_value(data.get("output_summary") or data.get("output")),
            "risk": data.get("risk") or data.get("risk_level") or "unavailable",
            "installation_status": data.get("installation_status") or data.get("install_status") or "unavailable",
            "approval_status": _approval_status(data),
            "provenance": data.get("provenance") or data.get("source") or "unavailable",
        },
    )


def build_file_workspace_trace_item(data: dict[str, Any]) -> dict[str, Any]:
    """Build a side-effect-free FileCore trace item from file/diff/workspace data."""

    has_output = any(data.get(key) for key in ("candidate_id", "stable_output_id", "output_id", "artifact_id"))
    if has_output and not any(data.get(key) for key in ("read_files", "created_files", "modified_files", "deleted_files", "affected_paths", "diff_summary")):
        kind = "output"
        subsystem = "OutputCore"
        title = _first_text(data, "title", default="Output trace")
    else:
        kind = data.get("kind") or ("diff" if data.get("diff_summary") else "workspace" if data.get("workspace_path") else "file")
        subsystem = "FileCore"
        title = _first_text(data, "title", "file_operation_kind", default="Workspace files")
    affected_paths = (
        _refs(data.get("affected_paths"))
        + _refs(data.get("read_files"))
        + _refs(data.get("created_files"))
        + _refs(data.get("modified_files"))
        + _refs(data.get("deleted_files"))
    )
    return build_process_trace_item(
        trace_id=data.get("trace_id") or data.get("operation_id") or data.get("output_id") or data.get("candidate_id"),
        kind=kind,
        subsystem=subsystem,
        title=title,
        summary=_first_text(data, "summary", "diff_summary", default="Workspace trace recorded."),
        status=data.get("status") or data.get("validation_state") or "completed",
        evidence_refs=data.get("evidence_refs"),
        artifact_refs=_refs(data.get("artifact_refs")) + _refs(data.get("artifact_id")),
        related_task_id=data.get("task_id") or data.get("related_task_id"),
        related_agent_id=data.get("agent_id") or data.get("related_agent_id"),
        created_at=data.get("created_at"),
        details={
            "workspace_path": data.get("workspace_path") or "unavailable",
            "read_files": _refs(data.get("read_files")),
            "created_files": _refs(data.get("created_files")),
            "modified_files": _refs(data.get("modified_files")),
            "deleted_files": _refs(data.get("deleted_files")),
            "diff_summary": data.get("diff_summary") or "unavailable",
            "candidate_id": data.get("candidate_id"),
            "stable_output_id": data.get("stable_output_id"),
            "output_id": data.get("output_id"),
            "validation_state": data.get("validation_state") or "unavailable",
            "affected_paths": affected_paths,
            "file_operation_kind": data.get("file_operation_kind") or "unavailable",
        },
    )


def build_miniagent_trace_item(data: dict[str, Any]) -> dict[str, Any]:
    """Build a side-effect-free MiniAgentCore trace item from MiniAgent task data."""

    miniagent_id = data.get("miniagent_id") or data.get("mini_agent_id") or data.get("id")
    miniagent_name = _first_text(data, "miniagent_name", "name", default=str(miniagent_id or "MiniAgent"))
    return build_process_trace_item(
        trace_id=data.get("trace_id") or miniagent_id or data.get("task_id"),
        kind="miniagent",
        subsystem="MiniAgentCore",
        title=f"MiniAgent: {miniagent_name}",
        summary=_first_text(data, "summary", "output_summary", "failure_reason", default="MiniAgent task recorded."),
        status=_status_from_operational_source(data),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at") or data.get("ended_at"),
        duration_ms=_duration(data),
        evidence_refs=data.get("evidence_refs") or data.get("evidence"),
        artifact_refs=data.get("artifact_refs") or data.get("artifacts"),
        related_task_id=data.get("task_id") or data.get("related_task_id"),
        related_agent_id=data.get("agent_id") or data.get("related_agent_id"),
        related_miniagent_id=miniagent_id,
        created_at=data.get("created_at"),
        details={
            "miniagent_id": miniagent_id,
            "miniagent_name": miniagent_name,
            "task_id": data.get("task_id") or "unavailable",
            "input_summary": _compact_value(data.get("input_summary") or data.get("input")),
            "output_summary": _compact_value(data.get("output_summary") or data.get("output")),
            "validation": data.get("validation") or data.get("validation_summary") or "unavailable",
            "failure_reason": data.get("failure_reason") or data.get("error"),
        },
    )


def build_handoff_trace_item(data: dict[str, Any]) -> dict[str, Any]:
    """Build a side-effect-free HandoffCore trace item from handoff data."""

    source = data.get("source_agent_id") or data.get("source") or "unknown"
    target = data.get("target_agent_id") or data.get("target") or "unknown"
    return build_process_trace_item(
        trace_id=data.get("trace_id") or data.get("handoff_id") or f"{source}->{target}",
        kind="handoff",
        subsystem="HandoffCore",
        title="Handoff",
        summary=_first_text(data, "summary", "completed_work_summary", "output_summary", "failure_reason", default="Handoff recorded."),
        status=_status_from_operational_source(data),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at") or data.get("ended_at"),
        duration_ms=_duration(data),
        evidence_refs=data.get("evidence_refs") or data.get("evidence"),
        artifact_refs=data.get("artifact_refs") or data.get("artifacts"),
        related_task_id=data.get("target_task_id") or data.get("source_task_id") or data.get("task_id"),
        related_agent_id=data.get("target_agent_id") or data.get("source_agent_id") or data.get("agent_id"),
        related_miniagent_id=data.get("miniagent_id") or data.get("target_miniagent_id"),
        created_at=data.get("created_at"),
        details={
            "source": source,
            "target": target,
            "source_task_id": data.get("source_task_id"),
            "target_task_id": data.get("target_task_id"),
            "input_summary": _compact_value(data.get("input_summary") or data.get("input")),
            "output_summary": _compact_value(data.get("output_summary") or data.get("output") or data.get("completed_work_summary")),
            "validation": data.get("validation") or data.get("validation_summary") or "unavailable",
            "failure_reason": data.get("failure_reason") or data.get("error"),
        },
    )




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


def _adaptive_skill_item(data: dict[str, Any]) -> dict[str, Any]:
    adaptive_kind = data.get("adaptive_kind")
    kwargs: dict[str, Any] = {}
    if adaptive_kind == "miniagent_skill_gap":
        kwargs["skill_gap"] = data
    elif adaptive_kind == "miniagent_adaptive_state":
        kwargs["adaptive_state"] = data
    elif adaptive_kind == "swarm_skill_resolution_decision":
        kwargs["decision"] = data
    elif adaptive_kind == "adaptive_research_request":
        kwargs["research_request"] = data
    elif adaptive_kind == "adaptive_skill_candidate_contract":
        kwargs["candidate_contract"] = data
    elif adaptive_kind == "miniagent_resume_contract":
        kwargs["resume_contract"] = data
    elif adaptive_kind == "adaptive_skill_metrics":
        kwargs["metrics"] = data
    items = build_adaptive_skill_trace_items(**kwargs)
    return items[0] if items else build_process_trace_item(
        kind="skill",
        subsystem="SkillCore",
        title="Adaptive skill state",
        summary="Adaptive MiniAgent skill contract recorded.",
        status="warning",
        details={"adaptive_kind": adaptive_kind},
    )



def build_model_runtime_process_trace_item(source: dict[str, Any]) -> dict[str, Any]:
    data = source or {}
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    required_actions = data.get("required_actions") if isinstance(data.get("required_actions"), list) else []
    fallback = data.get("fallback_policy") if isinstance(data.get("fallback_policy"), dict) else {}
    status = "warning" if warnings or required_actions or fallback.get("requires_user_approval") else "completed"
    return build_process_trace_item(
        trace_id=data.get("model_id") or data.get("local_model_name") or data.get("provider_id"),
        kind="model",
        subsystem="ModelCore",
        title="Model runtime resolution",
        summary="Provider/model runtime resolution metadata recorded without model execution.",
        status=status,
        details={
            "source_kind": "model_runtime",
            "runtime_kind": data.get("runtime_kind") or "model_runtime_resolution",
            "provider_id": data.get("provider_id"),
            "model_id": data.get("model_id"),
            "local_model_name": data.get("local_model_name"),
            "role_profile": data.get("role_profile"),
            "variant": data.get("variant"),
            "thinking_level": data.get("thinking_level"),
            "active_thinking": data.get("active_thinking"),
            "capability_source": data.get("capability_source"),
            "context_limit": data.get("context_limit"),
            "context_limit_source": data.get("context_limit_source"),
            "model_source": data.get("model_source"),
            "source_chain": data.get("source_chain") or [],
            "warning_count": len(warnings),
            "required_actions": required_actions,
            "fallback_requires_user_approval": fallback.get("requires_user_approval", False),
            "auto_switch_performed": fallback.get("auto_switch_performed", False),
            "can_execute_model": False,
            "can_start_ollama": False,
            "can_install_model": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
        metadata={"source_kind": "model_runtime"},
    )

def build_skill_import_process_trace_item(preview_report: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    report = preview_report or {}
    policy_data = policy if isinstance(policy, dict) else {}
    contract = report.get("import_contract") if isinstance(report.get("import_contract"), dict) else {}
    spec = report.get("skill_spec_preview") if isinstance(report.get("skill_spec_preview"), dict) else {}
    provenance = spec.get("provenance") if isinstance(spec.get("provenance"), dict) else {}
    risk_report = report.get("risk_report") if isinstance(report.get("risk_report"), dict) else {}
    compatibility = report.get("compatibility_score") if isinstance(report.get("compatibility_score"), dict) else {}
    migration = report.get("migration_assistant") if isinstance(report.get("migration_assistant"), dict) else {}
    risks = _refs(risk_report.get("risks"))
    decision = _first_text(policy_data, "decision", default=_first_text(contract, "policy_decision", default="preview_only"))
    compatibility_status = compatibility.get("status") or "unmeasured"
    blocked = decision == "blocked" or compatibility_status == "blocked" or bool(risk_report.get("possible_secret_material") or risk_report.get("dangerous_execution_instruction"))
    needs_review = decision == "needs_review" or compatibility_status in {"needs_review", "unmeasured"} or bool(migration.get("requires_manual_review"))
    status = "blocked" if blocked else "warning" if needs_review else "completed"
    source_kind = _first_text(report, "source_kind", default="skill_import_preview")

    return build_process_trace_item(
        trace_id=report.get("preview_id") or report.get("candidate_id"),
        kind="skill",
        subsystem="SkillCore",
        title="Skill import preview",
        summary="Skill import preview recorded without installing, executing source, activating tools, or activating MCP.",
        status=status,
        details={
            "source_kind": source_kind,
            "source_status": "blocked" if blocked else "needs_review" if needs_review else "preview_ready",
            "preview_id": report.get("preview_id"),
            "candidate_id": report.get("candidate_id"),
            "source_format": report.get("source_format") or contract.get("source_format") or spec.get("source_format"),
            "detected_format": (report.get("detection") or {}).get("detected_format") if isinstance(report.get("detection"), dict) else None,
            "import_adapter": report.get("import_adapter") or contract.get("import_adapter") or provenance.get("import_adapter"),
            "policy_decision": decision,
            "compatibility_score": compatibility.get("score", "unmeasured"),
            "compatibility_status": compatibility_status,
            "migration_suggestion_count": migration.get("suggestion_count", 0),
            "risk_count": len(risks),
            "can_create_candidate": bool(report.get("can_create_candidate") or policy_data.get("can_create_candidate")),
            "can_install_skill": False,
            "can_execute_source": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
        metadata={"source_kind": source_kind},
    )


def build_skill_harness_process_trace_item(source: dict[str, Any]) -> dict[str, Any]:
    data = source or {}
    test_contract = data.get("test_contract") if isinstance(data.get("test_contract"), dict) else data if data.get("contract_kind") == "skill_test_case_contract" else {}
    dry_run = data.get("dry_run") if isinstance(data.get("dry_run"), dict) else data if data.get("report_kind") == "skill_dry_run_report" else {}
    validation = data.get("runtime_validation") if isinstance(data.get("runtime_validation"), dict) else data if data.get("report_kind") == "skill_runtime_validation_report" else {}
    regression = data.get("regression_suite") if isinstance(data.get("regression_suite"), dict) else data if data.get("suite_kind") == "skill_regression_suite" else {}
    evidence = data.get("evidence_quality") if isinstance(data.get("evidence_quality"), dict) else data if data.get("report_kind") == "skill_evidence_quality_report" else {}
    promotion = data.get("promotion_gate") if isinstance(data.get("promotion_gate"), dict) else data if data.get("gate_kind") == "skill_promotion_gate" else {}
    validation_status = validation.get("status") or "unmeasured"
    promotion_decision = promotion.get("decision") or "unmeasured"
    blocked = validation_status in {"blocked", "failed"} or promotion_decision == "blocked" or regression.get("status") == "blocked" or evidence.get("status") == "blocked"
    needs_review = promotion_decision in {"needs_review", "unmeasured"} or validation_status in {"needs_review", "unmeasured"} or evidence.get("status") in {"weak", "missing", "unmeasured"}
    status = "blocked" if blocked else "warning" if needs_review else "completed"

    return build_process_trace_item(
        trace_id=data.get("skill_ref") or test_contract.get("skill_ref") or validation.get("skill_ref") or promotion.get("skill_ref"),
        kind="skill",
        subsystem="SkillCore",
        title="Skill harness validation",
        summary="Read-only skill harness validation recorded without execution, install, tools, or MCP activation.",
        status=status,
        details={
            "source_kind": "skill_harness",
            "test_contract_status": test_contract.get("status"),
            "test_case_count": test_contract.get("test_case_count"),
            "validation_status": validation_status,
            "evidence_status": evidence.get("status"),
            "promotion_decision": promotion_decision,
            "regression_status": regression.get("status"),
            "dry_run_mode": dry_run.get("dry_run_mode"),
            "dry_run_executed": dry_run.get("executed", False),
            "can_request_install_approval": promotion.get("can_request_install_approval", False),
            "can_install_skill": False,
            "can_execute_source": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
        metadata={"source_kind": "skill_harness"},
    )


def build_skill_version_process_trace_item(source: dict[str, Any]) -> dict[str, Any]:
    data = source or {}
    return build_process_trace_item(
        trace_id=data.get("snapshot_id") or data.get("skill_ref"),
        kind="skill",
        subsystem="SkillCore",
        title="Skill version snapshot",
        summary="Skill version snapshot metadata recorded without raw content or restore execution.",
        status="completed" if data.get("snapshot_id") else "warning",
        details={
            "source_kind": "skill_version_snapshot",
            "snapshot_id": data.get("snapshot_id"),
            "skill_ref": data.get("skill_ref"),
            "skill_name": data.get("skill_name"),
            "source": data.get("source"),
            "content_hash": data.get("content_hash"),
            "spec_hash": data.get("spec_hash"),
            "metadata_hash": data.get("metadata_hash"),
            "rollback_supported": data.get("rollback_supported"),
            "can_restore": data.get("can_restore"),
            "can_install_skill": False,
            "can_execute_source": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
        metadata={"source_kind": "skill_version_snapshot"},
    )


def build_skill_rollback_process_trace_item(source: dict[str, Any]) -> dict[str, Any]:
    data = source or {}
    decision = data.get("decision") or "unmeasured"
    return build_process_trace_item(
        trace_id=data.get("target_snapshot_id") or data.get("current_snapshot_id"),
        kind="review",
        subsystem="ReviewCore",
        title="Skill rollback plan",
        summary="Rollback plan prepared read-only; restore was not performed.",
        status="completed" if decision == "restore_ready" else "blocked" if decision == "blocked" else "warning",
        details={
            "source_kind": "skill_rollback_plan",
            "rollback_decision": decision,
            "current_snapshot_id": data.get("current_snapshot_id"),
            "target_snapshot_id": data.get("target_snapshot_id"),
            "changed_fields_count": len(data.get("changed_fields") or []),
            "can_restore": data.get("can_restore"),
            "restore_performed": data.get("restore_performed", False),
            "can_install_skill": False,
            "can_execute_source": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
        metadata={"source_kind": "skill_rollback_plan"},
    )


def build_skill_effectiveness_process_trace_item(source: dict[str, Any]) -> dict[str, Any]:
    data = source or {}
    status = data.get("status") or "unmeasured"
    return build_process_trace_item(
        trace_id=data.get("skill_ref"),
        kind="metric",
        subsystem="MetricCore",
        title="Skill effectiveness metrics",
        summary="Effectiveness metrics summary from explicit records only.",
        status="completed" if status == "effective" else "blocked" if status == "failing" else "warning",
        details={
            "source_kind": "skill_effectiveness_metrics",
            "skill_ref": data.get("skill_ref"),
            "record_count": data.get("record_count", 0),
            "measured_count": data.get("measured_count", 0),
            "status": status,
            "average_score": data.get("average_score"),
            "can_install_skill": False,
            "can_execute_source": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
        metadata={"source_kind": "skill_effectiveness_metrics"},
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
    elif source_kind == "miniagent_skill_adaptive":
        item = _adaptive_skill_item(data)
    elif source_kind == "swarm_final_audit":
        item = _audit_item(data)
    elif source_kind == "skill_import_preview":
        item = build_skill_import_process_trace_item(data, policy=data.get("policy") if isinstance(data.get("policy"), dict) else None)
    elif source_kind == "skill_harness":
        item = build_skill_harness_process_trace_item(data)
    elif source_kind == "skill_version_snapshot":
        item = build_skill_version_process_trace_item(data)
    elif source_kind == "skill_rollback_plan":
        item = build_skill_rollback_process_trace_item(data)
    elif source_kind == "skill_effectiveness_metrics":
        item = build_skill_effectiveness_process_trace_item(data)
    elif source_kind == "model_runtime":
        item = build_model_runtime_process_trace_item(data)
    elif source_kind == "miniagent_task_runtime_metric":
        item = process_trace_item_from_runtime_metric(data)
    elif source_kind == "tool_trace":
        item = build_tool_trace_item(data)
    elif source_kind == "action_trace":
        item = build_action_trace_item(data)
    elif source_kind == "validation_trace":
        item = build_process_trace_item(
            trace_id=data.get("trace_id") or data.get("id"),
            kind=data.get("kind") or "validation",
            subsystem="ValidationCore",
            title=data.get("title") or "Validation",
            summary=data.get("summary") or "Validation metadata recorded.",
            status=data.get("status") or "completed",
            details=data.get("details") if isinstance(data.get("details"), dict) else data,
        )
    elif source_kind == "skill_trace":
        item = build_skill_trace_item(data)
    elif source_kind == "file_workspace_trace":
        item = build_file_workspace_trace_item(data)
    elif source_kind == "miniagent_trace":
        item = build_miniagent_trace_item(data)
    elif source_kind == "handoff_trace":
        item = build_handoff_trace_item(data)
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
