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


def test_normalizes_prepared_openswarm_legacy_skill_metadata():
    result = normalize_external_skill_to_skillspec_preview({
        "source_format": "openswarm_legacy_skill",
        "meta_json": {
            "name": "Legacy Helper",
            "description": "Migrated helper",
            "command": "legacy-helper",
            "author": "Legacy Author",
            "license": "MIT",
        },
        "files": [{"name": "SKILL.md", "content": "# Legacy Helper\nUse this migrated workflow."}],
    })

    spec = result["skill_spec_preview"]
    assert spec["name"] == "Legacy Helper"
    assert spec["description"] == "Migrated helper"
    assert spec["command"] == "legacy-helper"
    assert spec["content"].startswith("# Legacy Helper")
    assert spec["source_format"] == "openswarm_legacy_skill"
    assert spec["provenance"]["source_platform"] == "openswarm"
    assert spec["provenance"]["legacy_metadata_present"] is True
    assert result["import_contract"]["source_format"] == "openswarm_legacy_skill"
    assert_preview_safe(result)


def test_normalizes_prepared_openswarm_skillspec_preview_without_candidate_creation():
    result = normalize_external_skill_to_skillspec_preview({
        "source_format": "openswarm_skillspec",
        "metadata": {
            "name": "Portable Skill",
            "description": "Existing SkillSpec-like data",
            "command": "portable-skill",
        },
        "content": "# Portable Skill\nAlready portable.",
        "provenance": {"source_url": "file://export/skill.json"},
    })

    spec = result["skill_spec_preview"]
    assert spec["name"] == "Portable Skill"
    assert spec["command"] == "portable-skill"
    assert spec["source_format"] == "openswarm_skillspec"
    assert spec["provenance"]["source_url"] == "file://export/skill.json"
    assert result["can_create_candidate"] is False
    assert_preview_safe(result)


def test_normalizes_prepared_anthropic_skill_frontmatter_from_skill_md():
    result = normalize_external_skill_to_skillspec_preview({
        "source_format": "anthropic_skill",
        "content": "---\nname: Brand Writer\ndescription: Writes in brand voice\n---\n# Brand Writer\nFollow the brand system.",
    })

    spec = result["skill_spec_preview"]
    assert spec["name"] == "Brand Writer"
    assert spec["description"] == "Writes in brand voice"
    assert spec["content"].startswith("---")
    assert spec["source_format"] == "anthropic_skill"
    assert spec["provenance"]["frontmatter_present"] is True
    assert spec["provenance"]["source_platform"] == "claude"
    assert result["import_contract"]["import_adapter"] == "anthropic_skill_adapter"
    assert_preview_safe(result)


def test_claude_skill_supplied_frontmatter_overrides_parsed_preview_metadata():
    result = normalize_external_skill_to_skillspec_preview({
        "source_format": "claude_skill",
        "frontmatter": {"name": "Supplied Name", "description": "Supplied description"},
        "content": "---\nname: Parsed Name\ndescription: Parsed description\n---\nBody",
    })

    spec = result["skill_spec_preview"]
    assert spec["name"] == "Supplied Name"
    assert spec["description"] == "Supplied description"
    assert spec["source_format"] == "claude_skill"
    assert result["import_contract"]["import_adapter"] == "claude_skill_adapter"
    assert_preview_safe(result)
