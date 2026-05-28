from backend.apps.skills.candidate_approval import (
    apply_skill_candidate_install_approval,
    evaluate_skill_candidate_install_approval,
)
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


def _ready_candidate() -> SkillSpecCandidate:
    return SkillSpecCandidate(
        skill_spec=SkillSpec(name="CSS Validator", content="# CSS Validator\n"),
        source="skill_builder",
        status="validated",
        evidence_refs=["evidence-1"],
        policy_refs=["policy-1"],
    )


def test_install_approval_requires_explicit_approval_even_when_gate_passes():
    candidate = _ready_candidate()

    result = evaluate_skill_candidate_install_approval(candidate, approved=False)

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["install_approved"] is False
    assert result["next_status"] == "validated"
    assert result["reasons"][0]["code"] == "approval_missing"


def test_install_approval_blocks_when_gate_fails():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="CSS Validator", content="# CSS Validator\n"),
        source="skill_builder",
        status="validated",
    )

    result = evaluate_skill_candidate_install_approval(candidate, approved=True)

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["install_approved"] is False
    assert result["next_status"] == "validated"
    assert result["reasons"][0]["code"] == "gate_blocked"


def test_apply_install_approval_marks_candidate_approved_without_installing():
    candidate = _ready_candidate()

    approved = apply_skill_candidate_install_approval(candidate, approved=True)

    assert candidate.install_approved is False
    assert approved.install_approved is True
    assert approved.status == "approved_for_install"


def test_apply_install_approval_attaches_warning_when_blocked():
    candidate = _ready_candidate()

    blocked = apply_skill_candidate_install_approval(candidate, approved=False)

    assert blocked.install_approved is False
    assert blocked.status == "validated"
    assert blocked.warnings[-1]["code"] == "skill_candidate_install_approval"
    assert blocked.warnings[-1]["status"] == "blocked"
