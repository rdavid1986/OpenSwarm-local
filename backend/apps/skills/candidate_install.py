"""Controlled installation helpers for approved SkillSpecCandidate records."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.apps.skills.models import Skill, SkillSpecCandidate


def slugify_skill_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(name or "").strip().lower()).strip("-")
    return slug or "untitled-skill"


def build_skill_candidate_install_audit(candidate: SkillSpecCandidate, *, skill_id: str, file_path: str) -> dict[str, Any]:
    return {
        "event": "skill_candidate_installed",
        "candidate_id": candidate.candidate_id,
        "skill_id": skill_id,
        "file_path": file_path,
        "source": candidate.source,
        "source_ref": candidate.source_ref,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "validation_errors": candidate.validation_errors,
        "evidence_refs": candidate.evidence_refs,
        "policy_refs": candidate.policy_refs,
    }


def install_approved_skill_candidate(
    candidate: SkillSpecCandidate,
    *,
    skills_dir: Path | str,
    index: dict[str, dict[str, Any]],
) -> tuple[Skill, SkillSpecCandidate, dict[str, dict[str, Any]], dict[str, Any]]:
    """Install an approved candidate into the legacy skill registry.

    This helper writes only through the caller-provided skills_dir/index context.
    It refuses candidates that are not explicitly approved_for_install.
    """

    if candidate.status != "approved_for_install" or not candidate.install_approved:
        raise ValueError("skill_candidate_not_approved_for_install")

    spec = candidate.skill_spec
    skill_id = slugify_skill_name(spec.command or spec.name)
    target_dir = Path(skills_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{skill_id}.md"
    file_path.write_text(spec.content, encoding="utf-8")

    audit = build_skill_candidate_install_audit(candidate, skill_id=skill_id, file_path=str(file_path))
    next_index = dict(index)
    next_index[skill_id] = {
        "name": spec.name,
        "description": spec.description,
        "command": spec.command or skill_id,
        "source_candidate_id": candidate.candidate_id,
        "install_audit": audit,
    }

    installed_skill = Skill(
        id=skill_id,
        name=spec.name,
        description=spec.description,
        content=spec.content,
        file_path=str(file_path),
        command=spec.command or skill_id,
    )
    installed_candidate = candidate.model_copy(update={"status": "installed", "install_approved": True})
    return installed_skill, installed_candidate, next_index, audit
