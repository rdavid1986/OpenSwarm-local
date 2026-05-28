"""Side-effect-free validation helpers for SkillSpecCandidate records."""

from __future__ import annotations

from typing import Any

from backend.apps.skills.models import SkillSpecCandidate


MAX_SKILL_NAME_CHARS = 120
MAX_SKILL_DESCRIPTION_CHARS = 2000
MAX_SKILL_CONTENT_CHARS = 200_000


def _text(value: Any, *, max_chars: int = 1000) -> str:
    return str(value or "").strip()[:max_chars]


def _reason(code: str, message: str, *, severity: str = "medium") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def validate_skill_candidate(candidate: SkillSpecCandidate) -> dict[str, Any]:
    """Validate a SkillSpecCandidate without installing, mutating, or approving it."""

    spec = candidate.skill_spec
    reasons: list[dict[str, str]] = []

    name = _text(spec.name, max_chars=MAX_SKILL_NAME_CHARS + 1)
    description = _text(spec.description, max_chars=MAX_SKILL_DESCRIPTION_CHARS + 1)
    content = _text(spec.content, max_chars=MAX_SKILL_CONTENT_CHARS + 1)

    if not name:
        reasons.append(_reason("name_missing", "Skill candidate is missing a name.", severity="high"))
    elif len(name) > MAX_SKILL_NAME_CHARS:
        reasons.append(_reason("name_too_long", "Skill candidate name is too long.", severity="medium"))

    if len(description) > MAX_SKILL_DESCRIPTION_CHARS:
        reasons.append(_reason("description_too_long", "Skill candidate description is too long.", severity="medium"))

    if not content:
        reasons.append(_reason("content_missing", "Skill candidate is missing SKILL.md content.", severity="high"))
    elif len(content) > MAX_SKILL_CONTENT_CHARS:
        reasons.append(_reason("content_too_large", "Skill candidate content is too large.", severity="high"))

    if spec.metadata_confidence not in {"unknown", "inferred", "measured", "unmeasured"}:
        reasons.append(_reason("metadata_confidence_invalid", "Skill candidate metadata confidence is invalid.", severity="medium"))

    if candidate.install_approved:
        reasons.append(_reason("install_approval_not_allowed", "Validation cannot approve installation.", severity="critical"))

    status = "passed" if not reasons else "failed"
    return {
        "status": status,
        "ok": status == "passed",
        "reason_count": len(reasons),
        "reasons": reasons,
        "candidate_id": candidate.candidate_id,
        "install_approved": False,
    }


def apply_skill_candidate_validation(candidate: SkillSpecCandidate) -> SkillSpecCandidate:
    """Return a validated copy without mutating or installing the original candidate."""

    result = validate_skill_candidate(candidate)
    next_status = "validated" if result["ok"] else "needs_validation"
    return candidate.model_copy(
        update={
            "status": next_status,
            "validation_errors": result["reasons"],
            "install_approved": False,
        }
    )
