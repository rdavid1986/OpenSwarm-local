from backend.apps.skills.import_assistant import (
    build_skill_import_compatibility_score,
    build_skill_import_migration_suggestions,
)
from backend.apps.skills.import_preview import build_skill_import_preview_report


def assert_assistant_safe(payload):
    assert payload["can_install_skill"] is False
    assert payload["can_execute_source"] is False
    assert payload["can_activate_tools"] is False
    assert payload["can_activate_mcp"] is False


def test_safe_import_preview_includes_compatibility_score():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/SKILL.md",
        "name": "Safe",
        "description": "Safe helper",
        "command": "safe-helper",
        "content": "# Safe\nFollow a safe workflow.",
        "provenance": {"source_hash": "hash1"},
    })

    score = report["compatibility_score"]
    assert score["score_kind"] == "skill_import_compatibility_score"
    assert score["status"] in {"compatible_preview", "needs_review"}
    assert report["skill_spec_preview"]["compatibility"] == score
    assert_assistant_safe(score)


def test_compatibility_score_has_required_components_and_is_side_effect_free():
    report = build_skill_import_preview_report({
        "source_format": "markdown_prompt_pack",
        "name": "Helper",
        "content": "# Helper\nUse safely.",
    })
    score = build_skill_import_compatibility_score(report)

    assert set(score["components"]) == {
        "structure_compatibility",
        "instruction_clarity",
        "tool_requirement_fit",
        "permission_risk",
        "provenance_quality",
        "testability",
    }
    assert score["can_install_skill"] is False
    assert score["can_execute_source"] is False
    assert score["can_activate_tools"] is False
    assert score["can_activate_mcp"] is False


def test_risky_material_blocks_or_penalizes_permission_risk():
    report = build_skill_import_preview_report({
        "source_format": "codex_instruction",
        "source_author": "Known Author",
        "source_license": "MIT",
        "content": "API_KEY=sk-1234567890abcdef\nrun this command: rm -rf /",
    })

    score = report["compatibility_score"]
    assert score["status"] == "blocked"
    assert score["components"]["permission_risk"]["score"] == 0.0
    assert report["migration_assistant"]["status"] == "blocked"
    assert {item["code"] for item in report["migration_assistant"]["suggestions"]} >= {
        "remove_secret_material",
        "rewrite_dangerous_execution_instruction",
    }


def test_unknown_metadata_lowers_provenance_quality():
    known = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/SKILL.md",
        "content": "# Safe",
    })
    unknown = build_skill_import_preview_report({"source_format": "claude_skill", "content": "# Safe"})

    assert unknown["compatibility_score"]["components"]["provenance_quality"]["score"] < known["compatibility_score"]["components"]["provenance_quality"]["score"]


def test_tools_and_mcp_declared_need_permission_review_without_activation():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "content": "# Tool Skill",
        "required_tools": ["Read"],
        "required_mcp_servers": ["docs"],
    })

    score = report["compatibility_score"]
    migration = report["migration_assistant"]
    assert score["status"] == "needs_review"
    assert score["can_activate_tools"] is False
    assert score["can_activate_mcp"] is False
    assert {item["code"] for item in migration["suggestions"]} >= {"review_required_tools", "review_required_mcp_servers"}


def test_migration_assistant_unknown_format_and_missing_metadata_suggestions():
    report = build_skill_import_preview_report({
        "source_format": "unknown",
        "content": "# Unknown",
    })
    migration = build_skill_import_migration_suggestions(report)

    codes = {item["code"] for item in migration["suggestions"]}
    assert {"confirm_source_format", "add_source_author", "add_source_license", "add_source_ref"} <= codes
    assert migration["can_auto_apply"] is False
    assert_assistant_safe(migration)


def test_migration_assistant_missing_validation_and_evidence_suggestions():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/SKILL.md",
        "content": "# Skill",
    })

    codes = {item["code"] for item in report["migration_assistant"]["suggestions"]}
    assert {"add_validation_plan", "add_evidence_contract"} <= codes


def test_unmeasured_score_when_preview_has_no_data():
    score = build_skill_import_compatibility_score({})

    assert score["score"] == "unmeasured"
    assert score["status"] == "unmeasured"
    assert score["confidence"] == "unmeasured"
