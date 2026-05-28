from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


def test_skill_spec_defaults_do_not_invent_metadata():
    spec = SkillSpec(
        name="CSS Validator",
        description="Validate CSS quality.",
        content="# CSS Validator\n",
    )

    assert spec.spec_version == "openswarm.skill.v1"
    assert spec.source_format == "unknown"
    assert spec.metadata_confidence == "unknown"
    assert spec.provenance == {}
    assert spec.required_tools == []
    assert spec.required_mcp_servers == []
    assert spec.validation_plan == {}
    assert spec.evidence_contract == {}


def test_skill_spec_candidate_is_not_install_approval():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="Router Helper", content="# Router Helper\n"),
        source="skill_builder",
    )

    assert candidate.status == "candidate"
    assert candidate.install_approved is False
    assert candidate.validation_errors == []
    assert candidate.evidence_refs == []
    assert candidate.skill_spec.name == "Router Helper"
