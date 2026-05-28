from backend.apps.skills.candidate_validation import apply_skill_candidate_validation, validate_skill_candidate
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


def test_validate_skill_candidate_passes_minimal_candidate_without_approval():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="CSS Validator", content="# CSS Validator\n"),
        source="skill_builder",
    )

    result = validate_skill_candidate(candidate)

    assert result["ok"] is True
    assert result["status"] == "passed"
    assert result["reasons"] == []
    assert result["install_approved"] is False


def test_validate_skill_candidate_reports_missing_required_fields():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="", content=""),
        source="skill_builder",
    )

    result = validate_skill_candidate(candidate)

    assert result["ok"] is False
    assert result["status"] == "failed"
    codes = {reason["code"] for reason in result["reasons"]}
    assert codes == {"name_missing", "content_missing"}


def test_apply_skill_candidate_validation_updates_status_without_installing():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="Router Helper", content="# Router Helper\n"),
        source="skill_builder",
        install_approved=True,
    )

    validated = apply_skill_candidate_validation(candidate)

    assert candidate.install_approved is True
    assert validated.install_approved is False
    assert validated.status == "needs_validation"
    assert validated.validation_errors[0]["code"] == "install_approval_not_allowed"
