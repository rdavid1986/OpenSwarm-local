
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

SENSITIVE_KEYS = {"chain_of_thought", "cot", "private_reasoning", "hidden_reasoning"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if str(k) not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    return value


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return _safe(value)
    return [_safe(value)]


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join(str(candidate.get(k, "")) for k in ("skill_id", "id", "skill_name", "name", "description", "tags", "required_tools", "required_mcp_servers")).lower()


def build_skill_assignment_trace(**kwargs: Any) -> dict[str, Any]:
    return _safe({
        "assignment_kind": "skill_assignment_trace",
        "task_id": _text(kwargs.get("task_id")),
        "agent_id": _text(kwargs.get("agent_id")),
        "miniagent_id": _text(kwargs.get("miniagent_id")),
        "skill_id": _text(kwargs.get("skill_id")),
        "skill_name": _text(kwargs.get("skill_name"), "No skill assigned"),
        "skill_source": _text(kwargs.get("skill_source"), "unknown"),
        "matched_requirements": _list(kwargs.get("matched_requirements")),
        "missing_requirements": _list(kwargs.get("missing_requirements")),
        "match_confidence": max(0.0, min(1.0, float(kwargs.get("match_confidence", 0.0) or 0.0))),
        "assignment_reason": _text(kwargs.get("assignment_reason"), "No matching skill was available."),
        "alternatives_considered": _list(kwargs.get("alternatives_considered")),
        "risks": _list(kwargs.get("risks")),
        "fallback_used": bool(kwargs.get("fallback_used", False)),
        "created_at": _text(kwargs.get("created_at"), _now()),
        "visible_to_user": bool(kwargs.get("visible_to_user", True)),
        "can_install_skill": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    })


def summarize_skill_assignment_trace(trace: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(trace or {}))
    return {
        "summary_kind": "skill_assignment_trace_summary",
        "task_id": snapshot.get("task_id", ""),
        "skill_id": snapshot.get("skill_id", ""),
        "skill_name": snapshot.get("skill_name", "No skill assigned"),
        "match_confidence": snapshot.get("match_confidence", 0.0),
        "fallback_used": bool(snapshot.get("fallback_used", False)),
        "assignment_reason": snapshot.get("assignment_reason", ""),
    }


def build_skill_assignment_from_candidates(*, task: dict[str, Any] | None = None, candidates: list[dict[str, Any]] | None = None, agent_id: str = "", miniagent_id: str = "") -> dict[str, Any]:
    task = task or {}
    candidates = candidates or []
    task_requirements = [str(x).lower() for x in _list(task.get("requirements"))]
    task_text = " ".join([str(task.get("title", "")), str(task.get("description", "")), " ".join(task_requirements)]).lower()
    best = None
    best_matches: list[str] = []
    alternatives = []
    for candidate in candidates:
        c = deepcopy(candidate)
        c_text = _candidate_text(c)
        matches = [req for req in task_requirements if req and req in c_text]
        name = str(c.get("skill_name") or c.get("name") or "").lower()
        if name and name in task_text:
            matches.append(name)
        alternatives.append({"skill_id": c.get("skill_id") or c.get("id", ""), "skill_name": c.get("skill_name") or c.get("name", ""), "matched_requirements": matches})
        if len(matches) > len(best_matches):
            best, best_matches = c, matches
    if not best:
        return build_skill_assignment_trace(
            task_id=task.get("task_id") or task.get("id"), agent_id=agent_id, miniagent_id=miniagent_id,
            fallback_used=True, alternatives_considered=alternatives, risks=["no_matching_skill"],
        )
    missing = [req for req in task_requirements if req not in best_matches]
    confidence = min(1.0, len(best_matches) / max(1, len(task_requirements))) if task_requirements else 0.5
    return build_skill_assignment_trace(
        task_id=task.get("task_id") or task.get("id"), agent_id=agent_id, miniagent_id=miniagent_id,
        skill_id=best.get("skill_id") or best.get("id", ""), skill_name=best.get("skill_name") or best.get("name", ""),
        skill_source=best.get("skill_source") or best.get("source", "candidate"), matched_requirements=best_matches,
        missing_requirements=missing, match_confidence=confidence,
        assignment_reason="Selected by declarative metadata match.", alternatives_considered=alternatives,
        fallback_used=False,
    )
