from copy import deepcopy

from backend.apps.skills.import_contract import build_empty_skill_import_contract, summarize_skill_import_contract


def test_import_contract_defaults_are_safe():
    contract = build_empty_skill_import_contract()

    assert contract["contract_kind"] == "skill_import_contract"
    assert contract["contract_version"] == "openswarm.skill_import.v1"
    assert contract["source_format"] == "unknown"
    assert contract["source_trust_level"] == "untrusted"
    assert contract["safe_to_install"] is False
    assert contract["can_create_candidate"] is False
    assert contract["can_execute_source"] is False
    assert contract["can_activate_tools"] is False
    assert contract["can_activate_mcp"] is False


def test_import_contract_does_not_install_execute_or_activate():
    contract = build_empty_skill_import_contract(
        source_format="anthropic_skill",
        required_tools=["Read"],
        required_mcp_servers=["filesystem"],
    )

    assert contract["required_tools"] == ["Read"]
    assert contract["required_mcp_servers"] == ["filesystem"]
    assert contract["safe_to_install"] is False
    assert contract["can_execute_source"] is False
    assert contract["can_activate_tools"] is False
    assert contract["can_activate_mcp"] is False
    assert contract["can_create_candidate"] is False


def test_summary_does_not_mutate_contract():
    contract = build_empty_skill_import_contract(
        source_format="cursor_rule",
        conversion_warnings=["warning"],
        unsupported_features=["unsupported"],
        risks=["risk"],
    )
    before = deepcopy(contract)

    summary = summarize_skill_import_contract(contract)

    assert summary["contract_kind"] == "skill_import_contract_summary"
    assert summary["warning_count"] == 1
    assert summary["unsupported_feature_count"] == 1
    assert summary["risk_count"] == 1
    assert summary["safe_to_install"] is False
    assert summary["can_create_candidate"] is False
    assert contract == before
