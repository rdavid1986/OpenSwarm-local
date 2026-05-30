from backend.apps.skills.import_detection import detect_skill_import_source_format


def assert_safe(result):
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["safe_to_continue_preview"] is True
    assert result["can_create_candidate"] is False
    assert result["can_execute_source"] is False
    assert result["can_activate_tools"] is False
    assert result["can_activate_mcp"] is False


def test_detect_anthropic_or_claude_skill_from_skill_md_frontmatter():
    result = detect_skill_import_source_format({"files": [{"name": "SKILL.md", "content": "---\nname: Test\n---\nBody"}]})
    assert result["detected_format"] == "claude_skill"
    assert_safe(result)


def test_detect_openswarm_skillspec():
    result = detect_skill_import_source_format({"raw_text": '{"spec_version":"openswarm.skill.v1","name":"X"}'})
    assert result["detected_format"] == "openswarm_skillspec"
    assert result["confidence"] > 0.9
    assert_safe(result)


def test_detect_cursor_windsurf_copilot_codex():
    cases = [
        ({"files": [{"path": ".cursor/rules/ui.md"}]}, "cursor_rule"),
        ({"files": [{"path": ".windsurf/rules/main.md"}]}, "windsurf_rule"),
        ({"files": [{"name": "copilot-instructions.md"}]}, "copilot_instruction"),
        ({"files": [{"name": "AGENTS.md", "content": "Codex instructions"}]}, "codex_instruction"),
    ]
    for payload, expected in cases:
        result = detect_skill_import_source_format(payload)
        assert result["detected_format"] == expected
        assert_safe(result)


def test_detect_other_key_formats():
    cases = [
        ({"raw_text": "Gemini CLI config"}, "gemini_cli_config"),
        ({"raw_text": "Qwen Code config"}, "qwen_code_config"),
        ({"raw_text": "Kiro spec workflow"}, "kiro_spec"),
        ({"raw_text": "MCP tool server instructions"}, "mcp_tool_instruction"),
        ({"files": [{"name": "README.md", "content": "prompt pack"}]}, "markdown_prompt_pack"),
        ({"files": [{"name": "manifest.json", "content": '{"kind":"skill_pack"}'}]}, "skill_pack"),
    ]
    for payload, expected in cases:
        result = detect_skill_import_source_format(payload)
        assert result["detected_format"] == expected
        assert_safe(result)


def test_unknown_fallback_is_safe():
    result = detect_skill_import_source_format({"raw_text": "plain text"})

    assert result["detected_format"] == "unknown"
    assert result["confidence"] == 0.0
    assert result["warnings"]
    assert_safe(result)
