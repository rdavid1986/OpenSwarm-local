import pytest

from backend.apps.skills.candidate_install import install_approved_skill_candidate, slugify_skill_name
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


def test_slugify_skill_name_uses_safe_slug():
    assert slugify_skill_name("CSS Validator!") == "css-validator"
    assert slugify_skill_name("") == "untitled-skill"


def test_install_approved_skill_candidate_writes_legacy_skill_with_audit(tmp_path):
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(
            name="CSS Validator",
            description="Validate CSS.",
            command="css-check",
            content="# CSS Validator\n",
        ),
        source="skill_builder",
        source_ref="workspace-1",
        status="approved_for_install",
        install_approved=True,
        evidence_refs=["evidence-1"],
        policy_refs=["policy-1"],
    )

    skill, installed_candidate, index, audit = install_approved_skill_candidate(
        candidate,
        skills_dir=tmp_path / "skills",
        index={},
    )

    assert skill.id == "css-check"
    assert skill.command == "css-check"
    assert skill.file_path.endswith("css-check.md")
    assert (tmp_path / "skills" / "css-check.md").read_text(encoding="utf-8") == "# CSS Validator\n"
    assert installed_candidate.status == "installed"
    assert installed_candidate.install_approved is True
    assert index["css-check"]["source_candidate_id"] == candidate.candidate_id
    assert index["css-check"]["install_audit"]["candidate_id"] == candidate.candidate_id
    assert audit["event"] == "skill_candidate_installed"


def test_install_skill_candidate_requires_approval(tmp_path):
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="CSS Validator", content="# CSS Validator\n"),
        source="skill_builder",
        status="validated",
        install_approved=False,
    )

    with pytest.raises(ValueError, match="skill_candidate_not_approved_for_install"):
        install_approved_skill_candidate(candidate, skills_dir=tmp_path / "skills", index={})
