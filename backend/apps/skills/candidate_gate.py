"""Side-effect-free policy/evidence gate for SkillSpecCandidate records."""

from __future__ import annotations

from typing import Any

from backend.apps.skills.models import SkillSpecCandidate


def _reason(code: str, message: str, *, severity: str = "medium") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def evaluate_skill_candidate_gate(candidate: SkillSpecCandidate) -> dict[str, Any]:
    """Evaluate whether a skill candidate is eligible for future install approval.

    This gate does not install, approve, mutate, call models, or request HITL.
    It only reports whether the candidate has enough validation/policy/evidence
    state to be considered by a later approval flow.
    """

    reasons: list[dict[str, str]] = []

    if candidate.status != "validated":
        reasons.append(_reason(
            "candidate_not_validated",
            "Skill candidate must be validated before install approval can be considered.",
            severity="high",
        ))

    if candidate.validation_errors:
        reasons.append(_reason(
            "validation_errors_present",
            "Skill candidate still has validation errors.",
            severity="high",
        ))

    if not candidate.evidence_refs:
        reasons.append(_reason(
            "evidence_refs_missing",
            "Skill candidate is missing evidence references.",
            severity="medium",
        ))

    if not candidate.policy_refs:
        reasons.append(_reason(
            "policy_refs_missing",
            "Skill candidate is missing policy references.",
            severity="medium",
        ))

    if candidate.install_approved:
        reasons.append(_reason(
            "preapproved_install_not_allowed",
            "Skill candidate gate cannot accept pre-approved installation.",
            severity="critical",
        ))

    status = "passed" if not reasons else "blocked"
    return {
        "status": status,
        "ok": status == "passed",
        "reason_count": len(reasons),
        "reasons": reasons,
        "candidate_id": candidate.candidate_id,
        "install_approval_allowed": status == "passed",
        "install_approved": False,
    }


def apply_skill_candidate_gate(candidate: SkillSpecCandidate) -> SkillSpecCandidate:
    """Attach gate outcome as warnings without approving or installing."""

    gate = evaluate_skill_candidate_gate(candidate)
    warnings = [
        *candidate.warnings,
        {
            "code": "skill_candidate_gate",
            "status": gate["status"],
            "reasons": gate["reasons"],
        },
    ]
    return candidate.model_copy(
        update={
            "warnings": warnings,
            "install_approved": False,
        }
    )
