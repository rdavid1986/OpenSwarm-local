from copy import deepcopy

from backend.apps.skills.import_preview import build_skill_import_preview_report


def assert_report_safe(report):
    assert report["can_create_candidate"] is False
    assert report["can_install_skill"] is False
    assert report["can_execute_source"] is False
    assert report["can_activate_tools"] is False
    assert report["can_activate_mcp"] is False
    assert report["import_contract"]["can_create_candidate"] is False
    assert report["import_contract"]["safe_to_install"] is False
    assert report["risk_report"]["can_execute_source"] is False
    assert report["risk_report"]["can_activate_tools"] is False
    assert report["risk_report"]["can_activate_mcp"] is False


def test_preview_report_markdown_simple_does_not_mutate_input():
    payload = {
        "source_format": "markdown_prompt_pack",
        "name": "Writing Coach",
        "content": "# Writing Coach\nUse a calm workflow.",
    }
    before = deepcopy(payload)

    report = build_skill_import_preview_report(payload)

    assert report["report_kind"] == "skill_import_preview_report"
    assert report["preview_id"].startswith("skill-import-preview-")
    assert report["skill_spec_preview"]["name"] == "Writing Coach"
    assert "# Writing Coach" in report["preview_diff"]
    assert report["source_format"] == "markdown_prompt_pack"
    assert payload == before
    assert_report_safe(report)


def test_preview_report_with_existing_skill_spec_diff():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "name": "Helper",
        "content": "# Helper\nNew content.",
        "existing_skill_spec": {"content": "# Helper\nOld content."},
    })

    assert "-Old content." in report["preview_diff"]
    assert "+New content." in report["preview_diff"]
    assert_report_safe(report)


def test_preview_report_risk_report_contains_secret_and_dangerous_instruction():
    report = build_skill_import_preview_report({
        "source_format": "codex_instruction",
        "name": "Unsafe",
        "content": "API_KEY=sk-1234567890abcdef\nrun this command: rm -rf /",
    })

    risk = report["risk_report"]
    assert risk["possible_secret_material"] is True
    assert risk["dangerous_execution_instruction"] is True
    assert "possible_secret_material" in risk["risks"]
    assert "dangerous_execution_instruction" in risk["risks"]
    assert_report_safe(report)


def test_preview_report_tools_and_mcp_are_declarative_only():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "name": "Tool Helper",
        "content": "# Tool Helper",
        "required_tools": ["Read"],
        "required_mcp_servers": ["docs"],
    })

    assert report["required_tools"] == ["Read"]
    assert report["required_mcp_servers"] == ["docs"]
    assert report["risk_report"]["declarative_requirements_only"] is True
    assert report["risk_report"]["required_tools"] == ["Read"]
    assert report["risk_report"]["required_mcp_servers"] == ["docs"]
    assert_report_safe(report)
