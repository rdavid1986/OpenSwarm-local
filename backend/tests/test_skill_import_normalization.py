from backend.apps.skills.import_normalization import normalize_external_skill_to_skillspec_preview


def assert_preview_safe(result):
    assert result["can_create_candidate"] is False
    assert result["can_install_skill"] is False
    assert result["can_execute_source"] is False
    assert result["can_activate_tools"] is False
    assert result["can_activate_mcp"] is False
    contract = result["import_contract"]
    assert contract["safe_to_install"] is False
    assert contract["can_create_candidate"] is False
    assert contract["can_execute_source"] is False
    assert contract["can_activate_tools"] is False
    assert contract["can_activate_mcp"] is False


def test_normalizes_simple_markdown_preview():
    result = normalize_external_skill_to_skillspec_preview({
        "source_format": "markdown_prompt_pack",
        "name": "Writing Coach",
        "description": "Reusable writing workflow",
        "content": "# Writing Coach\nUse a calm editorial workflow.",
    })

    assert result["ok"] is True
    spec = result["skill_spec_preview"]
    assert spec["name"] == "Writing Coach"
    assert spec["content"].startswith("# Writing Coach")
    assert spec["source_format"] == "markdown_prompt_pack"
    assert spec["metadata_confidence"] == "inferred"
    assert_preview_safe(result)


def test_normalizes_claude_skill_with_frontmatter():
    result = normalize_external_skill_to_skillspec_preview({
        "source_format": "claude_skill",
        "source_platform": "claude",
        "frontmatter": {"name": "API Helper", "description": "API docs helper", "required_tools": ["Read"]},
        "content": "---\nname: API Helper\n---\nUse official API docs.",
        "required_mcp_servers": ["docs-server"],
    })

    spec = result["skill_spec_preview"]
    assert spec["name"] == "API Helper"
    assert spec["description"] == "API docs helper"
    assert spec["required_tools"] == ["Read"]
    assert spec["required_mcp_servers"] == ["docs-server"]
    assert spec["provenance"]["source_platform"] == "claude"
    assert result["import_contract"]["required_tools"] == ["Read"]
    assert_preview_safe(result)


def test_skillspec_preview_preserves_source_format_and_given_provenance():
    result = normalize_external_skill_to_skillspec_preview({
        "source_format": "openswarm_skillspec",
        "name": "Existing Spec",
        "content": "# Existing",
        "provenance": {"source_url": "https://example.invalid/spec", "custom": "kept"},
    })

    spec = result["skill_spec_preview"]
    assert spec["source_format"] == "openswarm_skillspec"
    assert spec["provenance"]["source_url"] == "https://example.invalid/spec"
    assert spec["provenance"]["custom"] == "kept"
    assert_preview_safe(result)


def test_missing_metadata_stays_unknown_or_inferred():
    result = normalize_external_skill_to_skillspec_preview({"source_format": "unknown", "content": "# Unknown"})

    spec = result["skill_spec_preview"]
    assert spec["provenance"]["source_author"] == "unknown"
    assert spec["provenance"]["source_license"] == "unknown"
    assert spec["metadata_confidence"] in {"unknown", "inferred", "unmeasured"}
    assert result["conversion_warnings"]
    assert_preview_safe(result)


def test_secret_and_dangerous_instruction_add_risks_without_execution():
    result = normalize_external_skill_to_skillspec_preview({
        "source_format": "codex_instruction",
        "name": "Unsafe Example",
        "content": "API_KEY=sk-1234567890abcdef\nrun this command: rm -rf /",
    })

    assert "possible_secret_material" in result["risks"]
    assert "dangerous_execution_instruction" in result["risks"]
    assert result["conversion_warnings"]
    assert_preview_safe(result)
