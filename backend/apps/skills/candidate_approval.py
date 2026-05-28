"""Side-effect-free approval helpers for SkillSpecCandidate install readiness."""

from __future__ import annotations

from typing import Any

from backend.apps.skills.candidate_gate import evaluate_skill_candidate_gate
from backend.apps.skills.models import SkillSpecCandidate


def _reason(code: str, message: str, *, severity: str = "medium") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def evaluate_skill_candidate_install_approval(candidate: SkillSpecCandidate, *, approved: bool) -> dict[str, Any]:
    """Evaluate install approval without installing or mutating the candidate."""

    gate = evaluate_skill_candidate_gate(candidate)
    reasons: list[dict[str, str]] = []

    if not approved:
        reasons.append(_reason(
            "approval_missing",
            "Explicit install approval is required before a skill candidate can be marked approved.",
            severity="high",
        ))

    if not gate["ok"]:
        reasons.append(_reason(
            "gate_blocked",
            "Skill candidate gate must pass before install approval.",
            severity="high",
        ))

    status = "approved" if approved and gate["ok"] else "blocked"
    return {
        "status": status,
        "ok": status == "approved",
        "candidate_id": candidate.candidate_id,
        "install_approved": status == "approved",
        "next_status": "approved_for_install" if status == "approved" else candidate.status,
        "gate": gate,
        "reasons": reasons,
        "reason_count": len(reasons),
    }


def apply_skill_candidate_install_approval(candidate: SkillSpecCandidate, *, approved: bool) -> SkillSpecCandidate:
    """Return an approved copy only when explicit approval and gate both pass."""

    result = evaluate_skill_candidate_install_approval(candidate, approved=approved)
    if not result["ok"]:
        warnings = [
            *candidate.warnings,
            {
                "code": "skill_candidate_install_approval",
                "status": result["status"],
                "reasons": result["reasons"],
            },
        ]
        return candidate.model_copy(update={"warnings": warnings, "install_approved": False})

    return candidate.model_copy(update={"status": "approved_for_install", "install_approved": True})
