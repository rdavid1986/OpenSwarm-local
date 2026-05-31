"""Side-effect-free adaptive skill gap contracts for MiniAgents.

These helpers only derive/redact dictionaries from provided runtime state. They do
not run research, create/update/install skills, activate MCP/tools, mutate DAGs,
or persist approvals.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.apps.swarms.process_trace_item import _safe, build_process_trace_item

GAP_TYPES = {
    "missing_skill",
    "stale_skill",
    "insufficient_skill_depth",
    "wrong_domain_skill",
    "missing_current_docs",
    "better_existing_skill_available",
    "unknown",
}
SEVERITIES = {"info", "warning", "blocked"}
RESOLUTIONS = {
    "use_existing_skill",
    "switch_skill",
    "update_skill",
    "create_skill_candidate",
    "request_research",
    "reject_request",
    "unknown",
}
ADAPTIVE_STATES = {
    "skill_gap_detected",
    "waiting_swarm_decision",
    "waiting_skill_acquisition",
    "skill_acquired",
    "resumed",
    "rejected",
    "blocked",
}
DECISIONS = {
    "use_existing_skill",
    "switch_skill",
    "update_skill",
    "create_skill_candidate",
    "request_research",
    "reject_request",
    "defer",
}
RESEARCH_STATES = {
    "research_approval_required",
    "research_prepared",
    "research_approved",
    "research_blocked",
}
CANDIDATE_ACTIONS = {"create", "update", "none", "blocked"}
RESUME_STATES = {"resume_prepared", "resume_blocked", "resumed"}
APPROVAL_REQUIRED_RESOLUTIONS = {"update_skill", "create_skill_candidate", "request_research"}
APPROVAL_REQUIRED_DECISIONS = {"update_skill", "create_skill_candidate", "request_research", "switch_skill"}
APPROVED_STATES = {"approved", "allowed", "granted", "true", "complete", "completed", "accepted"}


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


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


def _as_dict(value: Any) -> dict[str, Any]:
    return deepcopy(_safe(value)) if isinstance(value, dict) else {}


def _normalize(value: Any, allowed: set[str], default: str) -> str:
    normalized = _text(value).lower().replace("-", "_").replace(" ", "_")
    return normalized if normalized in allowed else default


def _joined_text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
        elif isinstance(value, (list, tuple, set)):
            parts.extend(str(v) for v in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


def _status_text(value: Any) -> str:
    if isinstance(value, dict):
        return _text(value.get("status") or value.get("state") or value.get("result"))
    return _text(value)


def _is_approved(value: Any) -> bool:
    return _text(value).lower() in APPROVED_STATES


def _evidence_refs(*sources: Any) -> list[Any]:
    refs: list[Any] = []
    keys = ("evidence_refs", "evidenceRefs", "evidence_ref", "evidence_id")
    for source in sources:
        data = _as_dict(source)
        for key in keys:
            for ref in _list(data.get(key)):
                if ref not in refs:
                    refs.append(ref)
    return refs


def _skill_text(skill: dict[str, Any]) -> str:
    return _joined_text(
        skill.get("skill_id"),
        skill.get("id"),
        skill.get("skill_name"),
        skill.get("name"),
        skill.get("description"),
        skill.get("tags"),
        skill.get("domains"),
        skill.get("capabilities"),
        skill.get("requirements"),
    )


def _task_text(task: dict[str, Any], context_packet: dict[str, Any]) -> str:
    return _joined_text(
        task.get("title"),
        task.get("goal"),
        task.get("objective"),
        task.get("description"),
        task.get("domain"),
        task.get("mode"),
        task.get("requirements"),
        context_packet.get("summary"),
        context_packet.get("requirements"),
        context_packet.get("domain"),
    )


def _has_overlap(left: str, right: str) -> bool:
    tokens = {token for token in left.replace("_", " ").split() if len(token) >= 4}
    return any(token in right for token in tokens)


def detect_miniagent_skill_gap(
    *,
    assigned_skill_id: Any = None,
    assigned_skill_name: Any = None,
    task: dict[str, Any] | None = None,
    domain: Any = None,
    mode: Any = None,
    context_packet: dict[str, Any] | None = None,
    errors: list[Any] | None = None,
    blockers: list[Any] | None = None,
    validation_result: Any = None,
    tool_requirements: list[Any] | None = None,
    research_requirements: list[Any] | None = None,
    skill_metadata: dict[str, Any] | None = None,
    source: Any = None,
) -> dict[str, Any]:
    """Detect a MiniAgent skill gap from reported task/runtime state only."""

    task = _as_dict(task)
    context_packet = _as_dict(context_packet)
    skill_metadata = _as_dict(skill_metadata)
    assigned_id = _text(assigned_skill_id or task.get("assigned_skill_id") or skill_metadata.get("skill_id") or skill_metadata.get("id"))
    assigned_name = _text(assigned_skill_name or task.get("assigned_skill") or task.get("skill_name") or skill_metadata.get("skill_name") or skill_metadata.get("name"))
    combined = _joined_text(task, context_packet, skill_metadata, errors or [], blockers or [], validation_result, tool_requirements or [], research_requirements or [], domain, mode)

    explicit_gap = _normalize(
        task.get("skill_gap") or task.get("gap_type") or context_packet.get("skill_gap") or skill_metadata.get("gap_type"),
        GAP_TYPES,
        "",
    )
    gap_type = explicit_gap or "unknown"
    has_gap = bool(explicit_gap)
    source_value = _normalize(source or task.get("skill_gap_source") or context_packet.get("source"), {"inferred_from_task_state", "reported_by_runtime", "unknown"}, "unknown")
    confidence = "unknown"

    if not assigned_id and not assigned_name:
        has_gap = True
        gap_type = "missing_skill"
        source_value = "inferred_from_task_state" if source_value == "unknown" else source_value
        confidence = "medium"
    elif any(marker in combined for marker in ("missing_skill", "missing skill", "no matching skill", "skill not available")):
        has_gap = True
        gap_type = "missing_skill"
        source_value = "reported_by_runtime"
        confidence = "high"
    elif any(marker in combined for marker in ("stale_skill", "outdated skill", "skill stale", "deprecated api")):
        has_gap = True
        gap_type = "stale_skill"
        source_value = "reported_by_runtime"
        confidence = "medium"
    elif any(marker in combined for marker in ("insufficient_skill_depth", "not enough expertise", "insufficient skill", "needs deeper skill")):
        has_gap = True
        gap_type = "insufficient_skill_depth"
        source_value = "reported_by_runtime"
        confidence = "medium"
    elif any(marker in combined for marker in ("wrong_domain_skill", "wrong domain", "domain mismatch")):
        has_gap = True
        gap_type = "wrong_domain_skill"
        source_value = "reported_by_runtime"
        confidence = "medium"
    elif any(marker in combined for marker in ("missing_current_docs", "current docs", "latest docs", "up-to-date docs", "fresh docs")):
        has_gap = True
        gap_type = "missing_current_docs"
        source_value = "reported_by_runtime"
        confidence = "medium"
    elif _text(domain or task.get("domain") or context_packet.get("domain")) and assigned_name:
        task_domain = _text(domain or task.get("domain") or context_packet.get("domain")).lower()
        skill_blob = _skill_text({**skill_metadata, "skill_name": assigned_name, "skill_id": assigned_id})
        if task_domain and skill_blob and not _has_overlap(task_domain, skill_blob):
            has_gap = True
            gap_type = "wrong_domain_skill"
            source_value = "inferred_from_task_state"
            confidence = "low"

    validation_status = _status_text(validation_result).lower()
    if validation_status in {"failed", "error", "invalid"} and gap_type == "unknown":
        has_gap = True
        gap_type = "unknown"
        source_value = "inferred_from_task_state" if source_value == "unknown" else source_value
        confidence = "low"

    severity = "info"
    if has_gap:
        severity = "blocked" if gap_type in {"missing_skill", "wrong_domain_skill"} or blockers else "warning"
    if validation_status in {"failed", "error", "invalid"}:
        severity = "blocked"

    recommended_resolution = "unknown"
    if has_gap:
        if gap_type == "missing_current_docs":
            recommended_resolution = "request_research"
        elif gap_type == "missing_skill":
            recommended_resolution = "create_skill_candidate"
        elif gap_type == "wrong_domain_skill":
            recommended_resolution = "switch_skill"
        elif gap_type in {"stale_skill", "insufficient_skill_depth"}:
            recommended_resolution = "update_skill"

    summary = "No MiniAgent skill gap reported."
    if has_gap:
        skill_label = assigned_name or assigned_id or "unassigned skill"
        summary = f"MiniAgent skill gap detected: {gap_type} for {skill_label}."

    required_approval = recommended_resolution in APPROVAL_REQUIRED_RESOLUTIONS or severity == "blocked"
    return _safe({
        "adaptive_kind": "miniagent_skill_gap",
        "has_gap": bool(has_gap),
        "gap_type": _normalize(gap_type, GAP_TYPES, "unknown"),
        "severity": _normalize(severity, SEVERITIES, "info"),
        "summary": summary,
        "recommended_resolution": _normalize(recommended_resolution, RESOLUTIONS, "unknown"),
        "required_approval": bool(required_approval),
        "evidence_refs": _evidence_refs(task, context_packet, validation_result),
        "source": source_value,
        "confidence": _normalize(confidence, {"unknown", "low", "medium", "high"}, "unknown"),
        "assigned_skill_id": assigned_id,
        "assigned_skill_name": assigned_name,
        "task_id": _text(task.get("task_id") or task.get("id")),
        "miniagent_id": _text(task.get("miniagent_id") or task.get("mini_agent_id") or task.get("agent_id")),
        "details": {
            "domain": _text(domain or task.get("domain") or context_packet.get("domain")),
            "mode": _text(mode or task.get("mode") or context_packet.get("mode")),
            "error_count": len(errors or []),
            "blocker_count": len(blockers or []),
            "validation_status": validation_status or "unknown",
            "tool_requirement_count": len(tool_requirements or []),
            "research_requirement_count": len(research_requirements or []),
            "skill_metadata_available": bool(skill_metadata),
        },
    })


def build_miniagent_adaptive_skill_state(
    *,
    miniagent_id: Any = None,
    task_id: Any = None,
    skill_gap: dict[str, Any] | None = None,
    adaptive_state: Any = None,
    requested_resolution: Any = None,
    approval_required: Any = None,
    resume_allowed: Any = None,
    reason: Any = None,
    trace_refs: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: Any = None,
) -> dict[str, Any]:
    gap = _as_dict(skill_gap)
    state = _normalize(adaptive_state or ("skill_gap_detected" if gap.get("has_gap") else "resumed"), ADAPTIVE_STATES, "blocked")
    resolution = _normalize(requested_resolution or gap.get("recommended_resolution"), RESOLUTIONS, "unknown")
    approval = bool(gap.get("required_approval")) if approval_required is None else bool(approval_required)
    if resume_allowed is None:
        resume = state in {"skill_acquired", "resumed"} and not approval
    else:
        resume = bool(resume_allowed)
    payload = {
        "adaptive_kind": "miniagent_adaptive_state",
        "adaptive_state": state,
        "miniagent_id": _text(miniagent_id or gap.get("miniagent_id")),
        "task_id": _text(task_id or gap.get("task_id")),
        "gap_type": _normalize(gap.get("gap_type"), GAP_TYPES, "unknown"),
        "requested_resolution": resolution,
        "approval_required": approval,
        "resume_allowed": resume,
        "reason": _text(reason or gap.get("summary"), "Adaptive skill state prepared from reported MiniAgent state."),
        "trace_refs": _list(trace_refs),
        "metadata": _safe(dict(metadata or {})),
    }
    if created_at:
        payload["created_at"] = _text(created_at)
    return _safe(payload)


def resolve_swarm_skill_gap_decision(
    *,
    skill_gap: dict[str, Any] | None = None,
    available_skills: list[dict[str, Any]] | None = None,
    policy_context: dict[str, Any] | None = None,
    user_approval_state: Any = None,
    task_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gap = _as_dict(skill_gap)
    policy = _as_dict(policy_context)
    task = _as_dict(task_context)
    skills = [_as_dict(skill) for skill in (available_skills or []) if isinstance(skill, dict)]
    has_gap = bool(gap.get("has_gap"))
    requested = _normalize(gap.get("recommended_resolution"), RESOLUTIONS, "unknown")
    approved = _text(user_approval_state).lower() in {"approved", "allowed", "granted", "true"}
    approval_status = _text(user_approval_state, "missing")

    decision = "defer"
    reason = "Insufficient reported data to resolve MiniAgent skill gap."
    blocked_reason = ""
    selected_skill: dict[str, Any] | None = None

    if not has_gap:
        decision = "defer"
        reason = "No MiniAgent skill gap is reported."
    elif requested in {"switch_skill", "use_existing_skill"} and skills:
        task_blob = _task_text(task, _as_dict(task.get("context_packet"))) or _text(gap.get("summary"))
        for skill in skills:
            if _has_overlap(task_blob, _skill_text(skill)):
                selected_skill = skill
                break
        decision = "switch_skill" if requested == "switch_skill" else "use_existing_skill"
        if not selected_skill:
            decision = "defer"
            blocked_reason = "No available skill metadata matched the task context."
        else:
            reason = "Existing available skill can be proposed; no install or research is executed."
    elif requested in {"update_skill", "create_skill_candidate", "request_research"}:
        decision = requested
        reason = "Requested resolution is policy-gated and prepared only."
    elif requested == "reject_request":
        decision = "reject_request"
        reason = "Runtime requested rejection of the skill adaptation request."
    else:
        decision = "defer"

    requires_browser_research = decision == "request_research"
    requires_skill_builder = decision in {"update_skill", "create_skill_candidate"}
    requires_registry_validation = decision in {"switch_skill", "use_existing_skill", "update_skill", "create_skill_candidate"}
    requires_user_approval = decision in APPROVAL_REQUIRED_DECISIONS or requires_browser_research or requires_skill_builder or bool(policy.get("requires_user_approval"))
    if requires_user_approval and not approved:
        blocked_reason = blocked_reason or f"User approval required before {decision}."

    safe_to_resume = decision in {"use_existing_skill", "switch_skill"} and not blocked_reason and bool(selected_skill or decision == "use_existing_skill")
    next_state = "resumed" if safe_to_resume else "waiting_skill_acquisition" if decision in {"update_skill", "create_skill_candidate", "request_research"} else "waiting_swarm_decision"
    if decision in {"reject_request", "defer"} and blocked_reason:
        next_state = "blocked"
    if decision == "reject_request":
        next_state = "rejected"

    return _safe({
        "adaptive_kind": "swarm_skill_resolution_decision",
        "decision": _normalize(decision, DECISIONS, "defer"),
        "requires_user_approval": bool(requires_user_approval),
        "requires_browser_research": bool(requires_browser_research),
        "requires_skill_builder": bool(requires_skill_builder),
        "requires_registry_validation": bool(requires_registry_validation),
        "reason": reason,
        "blocked_reason": blocked_reason,
        "safe_to_resume": bool(safe_to_resume),
        "next_state": _normalize(next_state, ADAPTIVE_STATES, "blocked"),
        "approval_state": approval_status,
        "selected_skill_id": _text((selected_skill or {}).get("skill_id") or (selected_skill or {}).get("id")),
        "selected_skill_name": _text((selected_skill or {}).get("skill_name") or (selected_skill or {}).get("name")),
        "gap_type": _normalize(gap.get("gap_type"), GAP_TYPES, "unknown"),
        "task_id": _text(gap.get("task_id") or task.get("task_id") or task.get("id")),
        "miniagent_id": _text(gap.get("miniagent_id") or task.get("miniagent_id") or task.get("mini_agent_id")),
        "safety_gate": {
            "browser_research_requires_approval": True,
            "create_skill_candidate_requires_approval": True,
            "update_skill_requires_approval": True,
            "install_skill_requires_approval": True,
            "activate_tool_or_mcp_requires_approval": True,
            "resume_with_new_permissions_requires_approval": True,
            "actions_executed": [],
        },
    })


def build_adaptive_research_request(
    *,
    skill_gap: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    research_scope: Any = None,
    browser_context: dict[str, Any] | None = None,
    approval_state: Any = None,
    evidence_refs: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare a browser research request contract without launching research."""

    gap = _as_dict(skill_gap)
    decision_data = _as_dict(decision)
    browser = _as_dict(browser_context)
    approved = _is_approved(approval_state or decision_data.get("approval_state"))
    wants_research = (
        decision_data.get("decision") == "request_research"
        or gap.get("recommended_resolution") == "request_research"
        or bool(research_scope)
    )
    blocked_reason = ""
    if not wants_research:
        blocked_reason = "No browser research request was reported by MiniAgent/Swarm."
        status = "research_blocked"
    elif approved:
        status = "research_prepared"
    else:
        status = "research_approval_required"
        blocked_reason = "User approval required before browser research."

    return _safe({
        "adaptive_kind": "adaptive_research_request",
        "research_status": _normalize(status, RESEARCH_STATES, "research_blocked"),
        "miniagent_id": _text(gap.get("miniagent_id") or decision_data.get("miniagent_id")),
        "task_id": _text(gap.get("task_id") or decision_data.get("task_id")),
        "gap_type": _normalize(gap.get("gap_type") or decision_data.get("gap_type"), GAP_TYPES, "unknown"),
        "requested_research_scope": _text(research_scope or browser.get("research_scope") or gap.get("summary"), "Skill-gap research scope not provided."),
        "requires_approval": bool(wants_research and not approved),
        "approval_state": _text(approval_state or decision_data.get("approval_state"), "missing"),
        "blocked_reason": blocked_reason,
        "browser_metadata": {
            "browser_id": _text(browser.get("browser_id") or browser.get("id")),
            "selected_browser_ids": _list(browser.get("selected_browser_ids") or browser.get("browser_ids")),
            "url": _text(browser.get("url")),
            "approved_or_prepared_only": True,
            "research_launched": False,
        },
        "evidence_refs": _list(evidence_refs),
        "metadata": _safe(dict(metadata or {})),
        "safety_gate": {
            "browser_research_requires_approval": True,
            "actions_executed": [],
            "tools_or_mcp_activated": [],
        },
    })


def build_skill_candidate_from_adaptive_research(
    *,
    skill_gap: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    research_request: dict[str, Any] | None = None,
    research_evidence_refs: list[Any] | None = None,
    source_refs: list[Any] | None = None,
    provenance_refs: list[Any] | None = None,
    existing_skill_id: Any = None,
    existing_skill_name: Any = None,
    candidate_id: Any = None,
    approval_state: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare skill candidate create/update contract from real refs only."""

    gap = _as_dict(skill_gap)
    decision_data = _as_dict(decision)
    request = _as_dict(research_request)
    decision_name = _normalize(decision_data.get("decision") or gap.get("recommended_resolution"), DECISIONS, "defer")
    evidence = _list(research_evidence_refs or request.get("evidence_refs") or gap.get("evidence_refs"))
    sources = _list(source_refs)
    provenance = _list(provenance_refs)
    action = "none"
    blocked_reason = ""

    if decision_name == "create_skill_candidate":
        action = "create"
    elif decision_name == "update_skill":
        action = "update"
    elif decision_name == "request_research":
        action = "none"
        blocked_reason = "Research evidence must be reviewed before preparing a skill candidate."

    if action in {"create", "update"}:
        if not evidence:
            action = "blocked"
            blocked_reason = "Real research evidence refs are required before creating/updating a skill candidate."
        elif not (sources and provenance):
            action = "blocked"
            blocked_reason = "Source refs and provenance refs are required before creating/updating a skill candidate."
        elif action == "update" and not _text(existing_skill_id or decision_data.get("selected_skill_id")):
            action = "blocked"
            blocked_reason = "Existing skill id is required before preparing a skill update candidate."

    return _safe({
        "adaptive_kind": "adaptive_skill_candidate_contract",
        "candidate_action": _normalize(action, CANDIDATE_ACTIONS, "blocked"),
        "candidate_id": _text(candidate_id),
        "miniagent_id": _text(gap.get("miniagent_id") or decision_data.get("miniagent_id")),
        "task_id": _text(gap.get("task_id") or decision_data.get("task_id")),
        "gap_type": _normalize(gap.get("gap_type") or decision_data.get("gap_type"), GAP_TYPES, "unknown"),
        "existing_skill_id": _text(existing_skill_id or decision_data.get("selected_skill_id")),
        "existing_skill_name": _text(existing_skill_name or decision_data.get("selected_skill_name")),
        "research_evidence_refs": evidence,
        "source_refs": sources,
        "provenance_refs": provenance,
        "requires_approval": True,
        "approval_state": _text(approval_state or decision_data.get("approval_state"), "missing"),
        "policy_gate_required": True,
        "blocked_reason": blocked_reason,
        "summary": blocked_reason or f"Skill candidate {action} contract prepared; no skill was created, updated, or installed.",
        "metadata": _safe(dict(metadata or {})),
        "safety_gate": {
            "skill_builder_requires_approval": True,
            "registry_validation_required": True,
            "install_skill_requires_approval": True,
            "actions_executed": [],
        },
    })


def build_miniagent_resume_contract(
    *,
    adaptive_state: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    candidate_contract: dict[str, Any] | None = None,
    approval_state: Any = None,
    context_packet_refs: list[Any] | None = None,
    worklog_refs: list[Any] | None = None,
    acquired_skill_id: Any = None,
    candidate_id: Any = None,
    tool_permission_changes: list[Any] | None = None,
    mcp_permission_changes: list[Any] | None = None,
    blocked_reason: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare a safe MiniAgent resume contract without resuming execution."""

    state = _as_dict(adaptive_state)
    decision_data = _as_dict(decision)
    candidate = _as_dict(candidate_contract)
    approved = _is_approved(approval_state or candidate.get("approval_state") or decision_data.get("approval_state"))
    context_refs = _list(context_packet_refs or state.get("trace_refs"))
    logs = _list(worklog_refs)
    permission_changes = _list(tool_permission_changes) + _list(mcp_permission_changes)
    skill_ref = _text(acquired_skill_id or candidate.get("existing_skill_id") or decision_data.get("selected_skill_id"))
    candidate_ref = _text(candidate_id or candidate.get("candidate_id"))
    reason = _text(blocked_reason)

    if permission_changes and not approved:
        reason = reason or "User approval required before resuming with new tool/MCP permissions."
    if (candidate.get("requires_approval") or decision_data.get("requires_user_approval")) and not approved:
        reason = reason or "User approval required before MiniAgent resume."
    if not (skill_ref or candidate_ref or decision_data.get("safe_to_resume")):
        reason = reason or "Acquired skill, approved candidate, or safe existing skill decision is required before resume."
    if not context_refs:
        reason = reason or "Context packet refs must be preserved before resume."
    if not logs:
        reason = reason or "MiniAgent worklog refs must be preserved before resume."

    resume_allowed = not bool(reason)
    return _safe({
        "adaptive_kind": "miniagent_resume_contract",
        "resume_state": "resume_prepared" if resume_allowed else "resume_blocked",
        "resume_allowed": bool(resume_allowed),
        "miniagent_id": _text(state.get("miniagent_id") or decision_data.get("miniagent_id") or candidate.get("miniagent_id")),
        "task_id": _text(state.get("task_id") or decision_data.get("task_id") or candidate.get("task_id")),
        "acquired_skill_id": skill_ref,
        "candidate_id": candidate_ref,
        "approval_state": _text(approval_state or candidate.get("approval_state") or decision_data.get("approval_state"), "missing"),
        "context_packet_refs": context_refs,
        "worklog_refs": logs,
        "tool_permission_changes": _list(tool_permission_changes),
        "mcp_permission_changes": _list(mcp_permission_changes),
        "blocked_reason": reason,
        "metadata": _safe(dict(metadata or {})),
        "safety_gate": {
            "resume_with_new_permissions_requires_approval": True,
            "dag_rewire_executed": False,
            "actions_executed": [],
        },
    })


def build_adaptive_skill_metrics(*, items: list[Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Summarize adaptive-skill contracts from provided trace/source items only."""

    counts = {
        "skill_gap_count": 0,
        "adaptive_requests_count": 0,
        "research_requests_count": 0,
        "candidate_create_requests_count": 0,
        "candidate_update_requests_count": 0,
        "resume_prepared_count": 0,
        "resume_blocked_count": 0,
        "approval_required_count": 0,
        "approval_missing_count": 0,
    }
    for raw in items or []:
        data = _as_dict(raw)
        metadata_data = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        kind = data.get("adaptive_kind") or metadata_data.get("adaptive_kind")
        if kind:
            counts["adaptive_requests_count"] += 1
        if kind == "miniagent_skill_gap" and data.get("has_gap"):
            counts["skill_gap_count"] += 1
        if kind == "adaptive_research_request":
            counts["research_requests_count"] += 1
        if kind == "adaptive_skill_candidate_contract":
            if data.get("candidate_action") == "create":
                counts["candidate_create_requests_count"] += 1
            if data.get("candidate_action") == "update":
                counts["candidate_update_requests_count"] += 1
        if kind == "miniagent_resume_contract":
            if data.get("resume_state") == "resume_prepared":
                counts["resume_prepared_count"] += 1
            if data.get("resume_state") == "resume_blocked":
                counts["resume_blocked_count"] += 1
        if data.get("requires_approval") or data.get("required_approval") or data.get("approval_required") or data.get("requires_user_approval"):
            counts["approval_required_count"] += 1
            if _text(data.get("approval_state"), "missing").lower() == "missing":
                counts["approval_missing_count"] += 1

    return _safe({
        "adaptive_kind": "adaptive_skill_metrics",
        "metric_kind": "adaptive_skill_metrics",
        "summary": "Adaptive MiniAgent skill metrics derived from reported contracts.",
        "counts": counts,
        "metadata": _safe(dict(metadata or {})),
    })


def build_adaptive_skill_trace_items(
    *,
    skill_gap: dict[str, Any] | None = None,
    adaptive_state: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    research_request: dict[str, Any] | None = None,
    candidate_contract: dict[str, Any] | None = None,
    resume_contract: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build safe trace items for adaptive skill contracts without executing actions."""

    items: list[dict[str, Any]] = []
    gap = _as_dict(skill_gap)
    state = _as_dict(adaptive_state)
    decision_data = _as_dict(decision)
    research = _as_dict(research_request)
    candidate = _as_dict(candidate_contract)
    resume = _as_dict(resume_contract)
    metric_data = _as_dict(metrics)
    if gap:
        status = "blocked" if gap.get("severity") == "blocked" else "warning" if gap.get("has_gap") else "completed"
        items.append(build_process_trace_item(
            trace_id=f"skill-gap-{gap.get('task_id') or gap.get('miniagent_id') or gap.get('gap_type') or 'unknown'}",
            kind="skill",
            subsystem="SkillCore",
            title="Skill gap detected" if gap.get("has_gap") else "Skill gap check",
            summary=gap.get("summary") or "MiniAgent skill gap check recorded.",
            status=status,
            evidence_refs=gap.get("evidence_refs"),
            related_task_id=gap.get("task_id"),
            related_miniagent_id=gap.get("miniagent_id"),
            related_skill_id=gap.get("assigned_skill_id"),
            details={
                "gap_type": gap.get("gap_type"),
                "severity": gap.get("severity"),
                "recommended_resolution": gap.get("recommended_resolution"),
                "required_approval": gap.get("required_approval"),
                "source": gap.get("source"),
                "confidence": gap.get("confidence"),
                "details": gap.get("details") if isinstance(gap.get("details"), dict) else {},
            },
            metadata={"source_kind": "miniagent_skill_adaptive", "adaptive_kind": "miniagent_skill_gap"},
        ))
    if state:
        state_name = _text(state.get("adaptive_state"), "blocked")
        status = "completed" if state_name in {"skill_acquired", "resumed"} else "blocked" if state_name in {"blocked", "waiting_skill_acquisition", "waiting_swarm_decision", "skill_gap_detected"} else "warning"
        items.append(build_process_trace_item(
            trace_id=f"adaptive-state-{state.get('task_id') or state.get('miniagent_id') or state_name}",
            kind="miniagent",
            subsystem="MiniAgentCore",
            title="MiniAgent adaptive skill state",
            summary=state.get("reason") or f"Adaptive state: {state_name}.",
            status=status,
            related_task_id=state.get("task_id"),
            related_miniagent_id=state.get("miniagent_id"),
            details={
                "adaptive_state": state_name,
                "gap_type": state.get("gap_type"),
                "requested_resolution": state.get("requested_resolution"),
                "approval_required": state.get("approval_required"),
                "resume_allowed": state.get("resume_allowed"),
                "trace_refs": state.get("trace_refs") or [],
            },
            metadata={"source_kind": "miniagent_skill_adaptive", "adaptive_kind": "miniagent_adaptive_state"},
        ))
    if decision_data:
        status = "completed" if decision_data.get("safe_to_resume") else "blocked" if decision_data.get("blocked_reason") or decision_data.get("requires_user_approval") else "warning"
        items.append(build_process_trace_item(
            trace_id=f"skill-decision-{decision_data.get('task_id') or decision_data.get('miniagent_id') or decision_data.get('decision') or 'unknown'}",
            kind="review",
            subsystem="ReviewCore",
            title="Swarm skill resolution decision",
            summary=decision_data.get("blocked_reason") or decision_data.get("reason") or "Swarm skill decision prepared.",
            status=status,
            related_task_id=decision_data.get("task_id"),
            related_miniagent_id=decision_data.get("miniagent_id"),
            related_skill_id=decision_data.get("selected_skill_id"),
            details={
                "decision": decision_data.get("decision"),
                "requires_user_approval": decision_data.get("requires_user_approval"),
                "requires_browser_research": decision_data.get("requires_browser_research"),
                "requires_skill_builder": decision_data.get("requires_skill_builder"),
                "requires_registry_validation": decision_data.get("requires_registry_validation"),
                "safe_to_resume": decision_data.get("safe_to_resume"),
                "next_state": decision_data.get("next_state"),
                "approval_state": decision_data.get("approval_state"),
                "safety_gate": decision_data.get("safety_gate"),
            },
            metadata={"source_kind": "miniagent_skill_adaptive", "adaptive_kind": "swarm_skill_resolution_decision"},
        ))
    if research:
        status = "completed" if research.get("research_status") in {"research_prepared", "research_approved"} else "blocked"
        items.append(build_process_trace_item(
            trace_id=f"adaptive-research-{research.get('task_id') or research.get('miniagent_id') or research.get('research_status') or 'unknown'}",
            kind="review",
            subsystem="ReviewCore",
            title="Browser research prepared" if status == "completed" else "Browser research approval required",
            summary=research.get("blocked_reason") or research.get("requested_research_scope") or "Adaptive browser research request recorded.",
            status=status,
            evidence_refs=research.get("evidence_refs"),
            related_task_id=research.get("task_id"),
            related_miniagent_id=research.get("miniagent_id"),
            details={
                "research_status": research.get("research_status"),
                "requested_research_scope": research.get("requested_research_scope"),
                "requires_approval": research.get("requires_approval"),
                "approval_state": research.get("approval_state"),
                "browser_metadata": research.get("browser_metadata"),
                "safety_gate": research.get("safety_gate"),
            },
            metadata={"source_kind": "miniagent_skill_adaptive", "adaptive_kind": "adaptive_research_request"},
        ))
    if candidate:
        action = _text(candidate.get("candidate_action"), "blocked")
        status = "blocked" if action == "blocked" else "warning" if action == "none" else "planned"
        items.append(build_process_trace_item(
            trace_id=f"adaptive-skill-candidate-{candidate.get('task_id') or candidate.get('candidate_id') or action}",
            kind="skill",
            subsystem="SkillCore",
            title="Skill candidate blocked" if action == "blocked" else "Skill candidate contract prepared",
            summary=candidate.get("blocked_reason") or candidate.get("summary") or "Adaptive skill candidate contract recorded.",
            status=status,
            evidence_refs=candidate.get("research_evidence_refs"),
            related_task_id=candidate.get("task_id"),
            related_miniagent_id=candidate.get("miniagent_id"),
            related_skill_id=candidate.get("existing_skill_id"),
            details={
                "candidate_action": action,
                "candidate_id": candidate.get("candidate_id"),
                "source_refs": candidate.get("source_refs") or [],
                "provenance_refs": candidate.get("provenance_refs") or [],
                "requires_approval": candidate.get("requires_approval"),
                "policy_gate_required": candidate.get("policy_gate_required"),
                "approval_state": candidate.get("approval_state"),
                "safety_gate": candidate.get("safety_gate"),
            },
            metadata={"source_kind": "miniagent_skill_adaptive", "adaptive_kind": "adaptive_skill_candidate_contract"},
        ))
    if resume:
        status = "planned" if resume.get("resume_allowed") else "blocked"
        items.append(build_process_trace_item(
            trace_id=f"miniagent-resume-{resume.get('task_id') or resume.get('miniagent_id') or resume.get('resume_state') or 'unknown'}",
            kind="miniagent",
            subsystem="MiniAgentCore",
            title="MiniAgent resume prepared" if resume.get("resume_allowed") else "MiniAgent resume blocked",
            summary=resume.get("blocked_reason") or "MiniAgent resume contract prepared without executing resume.",
            status=status,
            related_task_id=resume.get("task_id"),
            related_miniagent_id=resume.get("miniagent_id"),
            related_skill_id=resume.get("acquired_skill_id"),
            details={
                "resume_state": resume.get("resume_state"),
                "resume_allowed": resume.get("resume_allowed"),
                "candidate_id": resume.get("candidate_id"),
                "approval_state": resume.get("approval_state"),
                "context_packet_refs": resume.get("context_packet_refs") or [],
                "worklog_refs": resume.get("worklog_refs") or [],
                "tool_permission_changes": resume.get("tool_permission_changes") or [],
                "mcp_permission_changes": resume.get("mcp_permission_changes") or [],
                "safety_gate": resume.get("safety_gate"),
            },
            metadata={"source_kind": "miniagent_skill_adaptive", "adaptive_kind": "miniagent_resume_contract"},
        ))
    if metric_data:
        items.append(build_process_trace_item(
            trace_id="adaptive-skill-metrics",
            kind="metric",
            subsystem="MetricCore",
            title="Adaptive skill metrics",
            summary=metric_data.get("summary") or "Adaptive MiniAgent skill metrics recorded.",
            status="completed",
            details={
                "metric_kind": metric_data.get("metric_kind"),
                "counts": metric_data.get("counts") or {},
            },
            metadata={"source_kind": "miniagent_skill_adaptive", "adaptive_kind": "adaptive_skill_metrics"},
        ))
    return items
