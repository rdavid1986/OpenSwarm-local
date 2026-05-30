
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

AUDIT_VERSION = "openswarm.swarm_final_audit.v1"


def _critical_blockers(items: list[Any]) -> bool:
    for item in items:
        if isinstance(item, dict) and str(item.get("severity", "")).lower() in {"critical", "error", "high"}:
            return True
        if isinstance(item, str) and item:
            return True
    return False


def build_swarm_final_audit(*, swarm_id: str = "", timeline: dict[str, Any] | None = None, worklogs: list[dict[str, Any]] | None = None, handoffs: list[dict[str, Any]] | None = None, validation_summary: str = "") -> dict[str, Any]:
    worklogs = [deepcopy(_safe(w)) for w in (worklogs or [])]
    handoffs = [deepcopy(_safe(h)) for h in (handoffs or [])]
    timeline_events = _list((timeline or {}).get("events"))
    completed = [w for w in worklogs if w.get("status") == "completed"]
    blocked = [w for w in worklogs if w.get("status") == "blocked"]
    failed = [w for w in worklogs if w.get("status") == "failed"]
    blockers = [b for w in worklogs for b in _list(w.get("blockers"))]
    evidence_count = sum(len(_list(w.get("evidence_refs"))) for w in worklogs) + sum(len(_list(e.get("evidence_refs"))) for e in timeline_events)
    artifact_count = sum(len(_list(w.get("artifacts_created"))) for w in worklogs) + sum(len(_list(e.get("artifact_refs"))) for e in timeline_events)
    risks = [risk for h in handoffs for risk in _list(h.get("risks"))]
    gaps = []
    if evidence_count == 0:
        gaps.append("missing_evidence")
    if worklogs and len(handoffs) == 0:
        gaps.append("missing_handoff")
    critical = bool(failed or _critical_blockers(blockers))
    if critical:
        final_status = "failed" if failed else "blocked"
    elif gaps:
        final_status = "completed_with_warnings"
    else:
        final_status = "completed"
    can_complete = final_status in {"completed", "completed_with_warnings"} and not critical
    return _safe({
        "audit_kind": "swarm_final_audit",
        "audit_version": AUDIT_VERSION,
        "swarm_id": swarm_id,
        "completed_tasks": [w.get("task_id", "") for w in completed],
        "blocked_tasks": [w.get("task_id", "") for w in blocked],
        "failed_tasks": [w.get("task_id", "") for w in failed],
        "evidence_count": evidence_count,
        "artifact_count": artifact_count,
        "handoff_count": len(handoffs),
        "validation_summary": validation_summary or "No validation summary provided.",
        "gaps": gaps,
        "risks": risks,
        "recommended_followups": ["Attach evidence before relying on final output."] if "missing_evidence" in gaps else [],
        "final_status": final_status,
        "can_mark_swarm_complete": can_complete,
        "created_at": _now(),
    })


def summarize_swarm_final_audit(audit: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(audit or {}))
    return {
        "summary_kind": "swarm_final_audit_summary",
        "swarm_id": snapshot.get("swarm_id", ""),
        "final_status": snapshot.get("final_status", "completed_with_warnings"),
        "can_mark_swarm_complete": bool(snapshot.get("can_mark_swarm_complete", False)),
        "completed_count": len(_list(snapshot.get("completed_tasks"))),
        "blocked_count": len(_list(snapshot.get("blocked_tasks"))),
        "failed_count": len(_list(snapshot.get("failed_tasks"))),
        "evidence_count": snapshot.get("evidence_count", 0),
        "handoff_count": snapshot.get("handoff_count", 0),
        "gap_count": len(_list(snapshot.get("gaps"))),
    }
