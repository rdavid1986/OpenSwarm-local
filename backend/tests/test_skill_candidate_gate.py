from backend.apps.skills.candidate_gate import apply_skill_candidate_gate, evaluate_skill_candidate_gate
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


def test_skill_candidate_gate_blocks_without_validation_policy_and_evidence():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="CSS Validator", content="# CSS Validator\n"),
        source="skill_builder",
    )

    result = evaluate_skill_candidate_gate(candidate)

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["install_approval_allowed"] is False
    assert result["install_approved"] is False
    codes = {reason["code"] for reason in result["reasons"]}
    assert codes == {"candidate_not_validated", "evidence_refs_missing", "policy_refs_missing"}


def test_skill_candidate_gate_passes_validated_candidate_with_policy_and_evidence_refs():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="Router Helper", content="# Router Helper\n"),
        source="skill_builder",
        status="validated",
        evidence_refs=["evidence-1"],
        policy_refs=["policy-1"],
    )

    result = evaluate_skill_candidate_gate(candidate)

    assert result["ok"] is True
    assert result["status"] == "passed"
    assert result["install_approval_allowed"] is True
    assert result["install_approved"] is False
    assert result["reasons"] == []


def test_apply_skill_candidate_gate_attaches_warning_without_approval():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="Unsafe Preapproval", content="# Unsafe\n"),
        source="skill_builder",
        status="validated",
        evidence_refs=["evidence-1"],
        policy_refs=["policy-1"],
        install_approved=True,
    )

    gated = apply_skill_candidate_gate(candidate)

    assert candidate.install_approved is True
    assert gated.install_approved is False
    assert gated.warnings[-1]["code"] == "skill_candidate_gate"
    assert gated.warnings[-1]["status"] == "blocked"
    assert gated.warnings[-1]["reasons"][0]["code"] == "preapproved_install_not_allowed"
