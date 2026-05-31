"""Side-effect-free skill effectiveness metrics contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

SAFE_FLAGS = {
    "can_install_skill": False,
    "can_execute_source": False,
    "can_activate_tools": False,
    "can_activate_mcp": False,
}
OUTCOMES = {"success", "failure", "partial", "unknown", "not_recorded"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def build_skill_effectiveness_metric_record(
    *,
    skill_ref: str = "",
    candidate_id: str = "",
    source: str = "unknown",
    outcome: str = "unknown",
    score: float | None = None,
    evidence_refs: list | None = None,
    trace_refs: list | None = None,
    notes: str | list[str] = "",
    measured: bool | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_outcome = outcome if outcome in OUTCOMES else "unknown"
    bounded_score = None if score is None else max(0.0, min(1.0, float(score)))
    metric_time = created_at or _now()
    base = f"{skill_ref}|{candidate_id}|{source}|{normalized_outcome}|{bounded_score}|{metric_time}"
    return {
        "record_kind": "skill_effectiveness_metric_record",
        "record_id": f"skill-metric-{sha256(base.encode('utf-8')).hexdigest()[:16]}",
        "skill_ref": _text(skill_ref, "unknown"),
        "candidate_id": _text(candidate_id),
        "source": source if source in {"harness", "install_audit", "user_feedback", "runtime_trace", "unknown"} else "unknown",
        "outcome": normalized_outcome,
        "score": bounded_score,
        "evidence_refs": [str(item) for item in _list(evidence_refs)],
        "trace_refs": [str(item) for item in _list(trace_refs)],
        "created_at": metric_time,
        "notes": [str(item) for item in _list(notes) if str(item or "").strip()],
        "measured": bool(measured) if measured is not None else bounded_score is not None and normalized_outcome != "not_recorded",
        **SAFE_FLAGS,
    }


def build_skill_effectiveness_summary(records: list[dict], *, skill_ref: str = "") -> dict[str, Any]:
    safe = [record for record in records if isinstance(record, dict)]
    selected = [record for record in safe if not skill_ref or record.get("skill_ref") == skill_ref]
    measured = [record for record in selected if record.get("measured")]
    scores = [float(record["score"]) for record in measured if record.get("score") is not None]
    success = sum(1 for record in selected if record.get("outcome") == "success")
    failure = sum(1 for record in selected if record.get("outcome") == "failure")
    partial = sum(1 for record in selected if record.get("outcome") == "partial")
    unknown = sum(1 for record in selected if record.get("outcome") in {"unknown", "not_recorded", None})
    avg = round(sum(scores) / len(scores), 3) if scores else None
    if not selected:
        status = "unmeasured"
    elif not measured:
        status = "insufficient_data"
    elif failure > success and failure >= partial:
        status = "failing"
    elif avg is not None and avg >= 0.75 and success >= failure:
        status = "effective"
    else:
        status = "needs_review"
    evidence_refs: list[str] = []
    for record in selected:
        for ref in _list(record.get("evidence_refs")):
            text = str(ref)
            if text and text not in evidence_refs:
                evidence_refs.append(text)
    return {
        "summary_kind": "skill_effectiveness_summary",
        "skill_ref": _text(skill_ref or (selected[0].get("skill_ref") if selected else ""), "unknown"),
        "record_count": len(selected),
        "measured_count": len(measured),
        "success_count": success,
        "failure_count": failure,
        "partial_count": partial,
        "unknown_count": unknown,
        "average_score": avg,
        "status": status,
        "limitations": ["No effectiveness records were provided; metrics were not invented."] if not selected else ["Only explicit records are counted."],
        "evidence_refs": evidence_refs,
        "can_promote_candidate": status == "effective",
        **SAFE_FLAGS,
    }


def build_skill_effectiveness_gate(summary: dict) -> dict[str, Any]:
    status = str((summary or {}).get("status") or "unmeasured")
    decision = "effective" if status == "effective" else "blocked" if status == "failing" else "needs_review" if status in {"needs_review", "insufficient_data"} else "unmeasured"
    return {
        "gate_kind": "skill_effectiveness_gate",
        "decision": decision,
        "status": status,
        "can_promote_candidate": decision == "effective",
        "reasons": [] if decision == "effective" else [{"code": f"effectiveness_{status}", "message": "Effectiveness is not established by explicit records."}],
        **SAFE_FLAGS,
    }
