"""Unified side-effect-free state context helpers for Swarm prompts.

RI-X.3 centralizes how model-assisted flows describe the real state they have
available. These helpers never query storage, call providers, execute tools, or
mutate SwarmState; they only normalize caller-provided values.
"""

from __future__ import annotations

import json
from typing import Any

from backend.apps.swarms.code_action import normalize_code_action_contract, summarize_code_action_contract
from backend.apps.swarms.project_memory import (
    build_project_memory_manifest,
    extract_project_memory_refs,
    summarize_project_memory_manifest,
)


MISSING = "missing"
UNKNOWN = "unknown"
EMPTY = "empty"
MAX_TEXT = 600
MAX_LIST_ITEMS = 12
MAX_DICT_ITEMS = 64


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_state_context_value(value: Any) -> Any:
    """Return a JSON-safe, bounded representation without inventing values."""

    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text[:MAX_TEXT]
    if isinstance(value, (list, tuple, set)):
        return [normalize_state_context_value(item) for item in list(value)[:MAX_LIST_ITEMS]]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for index, key in enumerate(sorted(value.keys(), key=lambda item: str(item))):
            if index >= MAX_DICT_ITEMS:
                normalized["__truncated__"] = True
                break
            normalized[str(key)[:120]] = normalize_state_context_value(value.get(key))
        return normalized
    return _as_text(value)[:MAX_TEXT]


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _as_text(value)
        if text:
            return text
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _count_or_zero(value: Any) -> int:
    try:
        number = int(value)
        return number if number >= 0 else 0
    except Exception:
        return 0


def _evidence_status(*, evidence_status: str | None, available_context: dict[str, Any], artifact_count: int) -> str:
    explicit = _as_text(evidence_status)
    if explicit:
        return explicit
    if available_context.get("evidence") or available_context.get("final_evidence"):
        return "present"
    if artifact_count > 0:
        return "artifacts_present"
    return MISSING


def _available_context_summary(available_context: dict[str, Any]) -> dict[str, Any]:
    if not available_context:
        return {"status": MISSING, "keys": [], "values": {}}
    keys = sorted(str(key) for key in available_context.keys())[:MAX_LIST_ITEMS]
    return {
        "status": "present",
        "keys": keys,
        "values": normalize_state_context_value({key: available_context.get(key) for key in keys}),
    }


def _project_memory_payload(
    *,
    project_memory_manifest: dict[str, Any] | None,
    project_memory_summary: str | None,
    project_memory_refs: dict[str, Any] | None,
    available_context: dict[str, Any],
) -> dict[str, Any]:
    raw_manifest = (
        project_memory_manifest
        if isinstance(project_memory_manifest, dict)
        else available_context.get("project_memory_manifest")
        if isinstance(available_context.get("project_memory_manifest"), dict)
        else available_context.get("project_memory")
        if isinstance(available_context.get("project_memory"), dict)
        else None
    )
    raw_summary = _first_text(project_memory_summary, available_context.get("project_memory_summary"))
    raw_refs = (
        project_memory_refs
        if isinstance(project_memory_refs, dict)
        else available_context.get("project_memory_refs")
        if isinstance(available_context.get("project_memory_refs"), dict)
        else None
    )

    if not raw_manifest:
        return {
            "status": EMPTY,
            "summary": "Project Memory: empty",
            "refs": normalize_state_context_value(raw_refs or {}),
            "manifest": None,
        }

    manifest = build_project_memory_manifest(
        project_id=raw_manifest.get("project_id"),
        swarm_id=raw_manifest.get("swarm_id"),
        workspace_id=raw_manifest.get("workspace_id"),
        current_goal=raw_manifest.get("current_goal"),
        decisions=raw_manifest.get("decisions"),
        outputs=raw_manifest.get("outputs"),
        accepted_iterations=raw_manifest.get("accepted_iterations"),
        candidate_iterations=raw_manifest.get("candidate_iterations"),
        artifacts=raw_manifest.get("artifacts"),
        evidence=raw_manifest.get("evidence"),
        constraints=raw_manifest.get("constraints"),
        open_questions=raw_manifest.get("open_questions"),
        last_updated_source=raw_manifest.get("last_updated_source"),
    )
    return {
        "status": "present",
        "summary": raw_summary or summarize_project_memory_manifest(manifest),
        "refs": normalize_state_context_value(raw_refs or extract_project_memory_refs(manifest)),
        "manifest": normalize_state_context_value(manifest),
    }


def _code_action_payload(
    *,
    code_actions: list[Any] | None,
    available_context: dict[str, Any],
) -> dict[str, Any]:
    raw_actions = code_actions if code_actions is not None else available_context.get("code_actions")
    normalized_actions = [
        normalize_code_action_contract(item)
        for item in (raw_actions if isinstance(raw_actions, list) else [])
        if isinstance(item, dict)
    ]

    if not normalized_actions:
        return {
            "status": EMPTY,
            "actions": [],
            "summary": "Code Actions: empty",
            "count": 0,
        }

    return {
        "status": "present",
        "actions": normalize_state_context_value(normalized_actions),
        "summary": "; ".join(summarize_code_action_contract(action) for action in normalized_actions[:MAX_LIST_ITEMS]),
        "count": len(normalized_actions),
    }


def _pending_code_action_payload(
    *,
    pending_code_actions: list[Any] | None,
    available_context: dict[str, Any],
) -> dict[str, Any]:
    raw_actions = (
        pending_code_actions
        if pending_code_actions is not None
        else available_context.get("pending_code_actions")
    )
    normalized_pending: list[dict[str, Any]] = []

    for item in raw_actions if isinstance(raw_actions, list) else []:
        if not isinstance(item, dict):
            continue
        code_action = item.get("code_action") if isinstance(item.get("code_action"), dict) else item
        normalized = dict(item)
        normalized["pending_action_type"] = _first_text(
            item.get("pending_action_type"),
            item.get("type"),
        ) or "code_action"
        normalized["status"] = _first_text(item.get("status")) or MISSING
        normalized["code_action"] = normalize_code_action_contract(code_action)
        normalized["executed"] = False
        normalized["execution_allowed"] = False
        normalized["execution_performed"] = False
        normalized["execution_result"] = None
        normalized_pending.append(normalize_state_context_value(normalized))

    if not normalized_pending:
        return {
            "status": EMPTY,
            "actions": [],
            "summary": "Pending Code Actions: empty",
            "count": 0,
        }

    summaries = []
    for item in normalized_pending[:MAX_LIST_ITEMS]:
        code_action = item.get("code_action") if isinstance(item, dict) else {}
        status = item.get("status") if isinstance(item, dict) else MISSING
        summaries.append(f"pending_status={status}; {summarize_code_action_contract(code_action)}")

    return {
        "status": "present",
        "actions": normalize_state_context_value(normalized_pending),
        "summary": "; ".join(summaries),
        "count": len(normalized_pending),
    }


def build_state_context_payload(
    *,
    mode: str | None = None,
    route: str | None = None,
    user_message: str | None = None,
    creation_type: str | None = None,
    project_intake_status: str | None = None,
    pending_action_type: str | None = None,
    output_id: str | None = None,
    candidate_iteration_id: str | None = None,
    evidence_status: str | None = None,
    artifact_count: int | None = None,
    provider_health: dict[str, Any] | None = None,
    model_name: str | None = None,
    guard_status: str | None = None,
    project_memory_manifest: dict[str, Any] | None = None,
    project_memory_summary: str | None = None,
    project_memory_refs: dict[str, Any] | None = None,
    agent_id: str | None = None,
    mini_agent_id: str | None = None,
    task_id: str | None = None,
    context_budget_used: int | None = None,
    context_budget_total: int | None = None,
    context_budget_source: str | None = None,
    context_sections: list[Any] | None = None,
    allowed_files: list[Any] | None = None,
    relevant_files: list[Any] | None = None,
    forbidden_files: list[Any] | None = None,
    dependency_outputs: list[Any] | None = None,
    tools_allowed: list[Any] | None = None,
    memory_scope: str | None = None,
    freshness_refs: dict[str, Any] | None = None,
    code_actions: list[Any] | None = None,
    pending_code_actions: list[Any] | None = None,
    available_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized snapshot from caller-provided state only."""

    context = _as_dict(available_context)
    provider = _as_dict(provider_health or context.get("provider_health"))
    resolved_artifact_count = _count_or_zero(
        artifact_count if artifact_count is not None else context.get("artifact_count") or context.get("artifacts_count")
    )
    resolved_pending_action = _first_text(pending_action_type, context.get("pending_action_type"), context.get("pending_action"))
    resolved_output_id = _first_text(output_id, context.get("output_id"), context.get("preview_output_id"), context.get("active_output"))
    resolved_candidate_iteration_id = _first_text(
        candidate_iteration_id,
        context.get("candidate_iteration_id"),
        context.get("iteration_id"),
    )
    resolved_project_memory = _project_memory_payload(
        project_memory_manifest=project_memory_manifest,
        project_memory_summary=project_memory_summary,
        project_memory_refs=project_memory_refs,
        available_context=context,
    )
    resolved_code_actions = _code_action_payload(
        code_actions=code_actions,
        available_context=context,
    )
    resolved_pending_code_actions = _pending_code_action_payload(
        pending_code_actions=pending_code_actions,
        available_context=context,
    )

    payload = {
        "mode": _first_text(mode, context.get("mode")) or MISSING,
        "route": _first_text(route, context.get("route")) or MISSING,
        "user_message": _as_text(user_message) or MISSING,
        "creation_type": _first_text(creation_type, context.get("creation_type")) or UNKNOWN,
        "project_intake_status": _first_text(project_intake_status, context.get("project_intake_status")) or MISSING,
        "pending_action_type": resolved_pending_action,
        "has_pending_action": bool(resolved_pending_action),
        "output_id": resolved_output_id,
        "candidate_iteration_id": resolved_candidate_iteration_id,
        "has_candidate_iteration": bool(resolved_candidate_iteration_id),
        "evidence_status": _evidence_status(
            evidence_status=evidence_status,
            available_context=context,
            artifact_count=resolved_artifact_count,
        ),
        "artifact_count": resolved_artifact_count,
        "provider_health_status": _first_text(provider.get("status"), context.get("provider_health_status")) or MISSING,
        "model_name": _first_text(model_name, provider.get("model"), context.get("model_name")) or MISSING,
        "guard_status": _first_text(guard_status, context.get("guard_status"), context.get("claim_guard_status")) or MISSING,
        "agent_id": _first_text(agent_id, context.get("agent_id")),
        "mini_agent_id": _first_text(mini_agent_id, context.get("mini_agent_id")),
        "task_id": _first_text(task_id, context.get("task_id")),
        "context_budget_used": _count_or_zero(context_budget_used if context_budget_used is not None else context.get("context_budget_used")),
        "context_budget_total": _count_or_zero(context_budget_total if context_budget_total is not None else context.get("context_budget_total")),
        "context_budget_source": _first_text(context_budget_source, context.get("context_budget_source")) or MISSING,
        "context_sections": normalize_state_context_value(context_sections if context_sections is not None else context.get("context_sections") or []),
        "allowed_files": normalize_state_context_value(allowed_files if allowed_files is not None else context.get("allowed_files") or []),
        "relevant_files": normalize_state_context_value(relevant_files if relevant_files is not None else context.get("relevant_files") or []),
        "forbidden_files": normalize_state_context_value(forbidden_files if forbidden_files is not None else context.get("forbidden_files") or []),
        "dependency_outputs": normalize_state_context_value(dependency_outputs if dependency_outputs is not None else context.get("dependency_outputs") or []),
        "tools_allowed": normalize_state_context_value(tools_allowed if tools_allowed is not None else context.get("tools_allowed") or []),
        "memory_scope": _first_text(memory_scope, context.get("memory_scope")) or MISSING,
        "freshness_refs": normalize_state_context_value(freshness_refs if freshness_refs is not None else context.get("freshness_refs") or {}),
        "project_memory_status": resolved_project_memory["status"],
        "project_memory_summary": resolved_project_memory["summary"],
        "project_memory_refs": resolved_project_memory["refs"],
        "project_memory_manifest": resolved_project_memory["manifest"],
        "code_action_status": resolved_code_actions["status"],
        "code_action_summary": resolved_code_actions["summary"],
        "code_action_count": resolved_code_actions["count"],
        "code_actions": resolved_code_actions["actions"],
        "pending_code_action_status": resolved_pending_code_actions["status"],
        "pending_code_action_summary": resolved_pending_code_actions["summary"],
        "pending_code_action_count": resolved_pending_code_actions["count"],
        "pending_code_actions": resolved_pending_code_actions["actions"],
        "available_context_summary": _available_context_summary(context),
    }
    return normalize_state_context_value(payload)


def build_state_context_prompt(context: dict[str, Any]) -> str:
    """Render state context with explicit missing/unknown semantics."""

    normalized = normalize_state_context_value(context)
    return "\n".join(
        [
            "OpenSwarm real state context:",
            "- Treat missing/null/empty fields as unavailable state, not permission to invent values.",
            "- Treat unknown fields as unknown until the system provides evidence.",
            "- The model may reason over this context, but guards authorize or block actions.",
            "MiniAgent Context:",
            f"- agent_id: {_as_dict(normalized).get('agent_id') or EMPTY}",
            f"- mini_agent_id: {_as_dict(normalized).get('mini_agent_id') or EMPTY}",
            f"- task_id: {_as_dict(normalized).get('task_id') or EMPTY}",
            f"- memory_scope: {_as_dict(normalized).get('memory_scope') or EMPTY}",
            "Context Budget:",
            f"- used: {_as_dict(normalized).get('context_budget_used', 0)}",
            f"- total: {_as_dict(normalized).get('context_budget_total', 0)}",
            f"- source: {_as_dict(normalized).get('context_budget_source') or MISSING}",
            "- sections: " + json.dumps(_as_dict(normalized).get("context_sections") or [], ensure_ascii=False, sort_keys=True),
            "MiniAgent Files / Tools:",
            "- allowed_files: " + json.dumps(_as_dict(normalized).get("allowed_files") or [], ensure_ascii=False, sort_keys=True),
            "- relevant_files: " + json.dumps(_as_dict(normalized).get("relevant_files") or [], ensure_ascii=False, sort_keys=True),
            "- forbidden_files: " + json.dumps(_as_dict(normalized).get("forbidden_files") or [], ensure_ascii=False, sort_keys=True),
            "- dependency_outputs: " + json.dumps(_as_dict(normalized).get("dependency_outputs") or [], ensure_ascii=False, sort_keys=True),
            "- tools_allowed: " + json.dumps(_as_dict(normalized).get("tools_allowed") or [], ensure_ascii=False, sort_keys=True),
            "- freshness_refs: " + json.dumps(_as_dict(normalized).get("freshness_refs") or {}, ensure_ascii=False, sort_keys=True),
            "Code Actions:",
            f"- status: {_as_dict(normalized).get('code_action_status') or EMPTY}",
            f"- count: {_as_dict(normalized).get('code_action_count') or 0}",
            f"- summary: {_as_dict(normalized).get('code_action_summary') or 'Code Actions: empty'}",
            "- actions: " + json.dumps(_as_dict(normalized).get("code_actions") or [], ensure_ascii=False, sort_keys=True),
            "Pending Code Actions:",
            f"- status: {_as_dict(normalized).get('pending_code_action_status') or EMPTY}",
            f"- count: {_as_dict(normalized).get('pending_code_action_count') or 0}",
            f"- summary: {_as_dict(normalized).get('pending_code_action_summary') or 'Pending Code Actions: empty'}",
            "- actions: " + json.dumps(_as_dict(normalized).get("pending_code_actions") or [], ensure_ascii=False, sort_keys=True),
            "Project Memory:",
            f"- status: {_as_dict(normalized).get('project_memory_status') or EMPTY}",
            f"- summary: {_as_dict(normalized).get('project_memory_summary') or 'Project Memory: empty'}",
            "- refs: " + json.dumps(_as_dict(normalized).get("project_memory_refs") or {}, ensure_ascii=False, sort_keys=True),
            json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True),
        ]
    )
