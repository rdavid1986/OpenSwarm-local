from backend.apps.skills.system_audit import build_skill_system_audit


def test_skill_system_audit_is_read_only():
    audit = build_skill_system_audit()

    assert audit["audit_kind"] == "skill_system_audit"
    assert audit["read_only"] is True
    assert audit["can_mutate_candidate"] is False
    assert audit["can_install_skill"] is False
    assert audit["can_approve_install"] is False
    assert audit["can_execute_web"] is False
    assert audit["can_activate_tools"] is False
    assert audit["can_activate_mcp"] is False


def test_skill_system_audit_reports_current_capabilities_and_gaps():
    audit = build_skill_system_audit()
    capabilities = audit["capabilities"]

    assert capabilities["skill_spec_contract"]["status"] == "implemented"
    assert "required_tools" in capabilities["skill_spec_contract"]["fields"]
    assert "required_mcp_servers" in capabilities["skill_spec_contract"]["fields"]

    assert capabilities["research_grounding"]["status"] == "implemented"
    assert "research_evidence persistence" in capabilities["research_grounding"]["features"]

    assert capabilities["registry"]["status"] == "partial"
    assert "no universal import adapter layer yet" in capabilities["registry"]["gaps"]

    assert capabilities["harness"]["status"] == "not_implemented"


def test_skill_system_audit_recommends_next_blocks():
    audit = build_skill_system_audit()
    phases = {item["phase"] for item in audit["next_action_matrix"]}

    assert "SKILL-IMPORT" in phases
    assert "Skill Harness" in phases
    assert "Skill Pack / Skill Collections" in phases
    assert "Cross-surface Skills-Actions-Modes Contract Map" in phases
