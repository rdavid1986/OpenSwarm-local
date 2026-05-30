from backend.apps.skills.import_adapters import get_skill_import_adapter, list_skill_import_adapters, select_skill_import_adapter


def assert_adapter_safe(adapter):
    assert adapter["can_execute_source"] is False
    assert adapter["can_activate_tools"] is False
    assert adapter["can_activate_mcp"] is False
    assert adapter["security_notes"]


def test_adapter_list_is_not_empty_and_safe():
    adapters = list_skill_import_adapters()

    assert adapters
    for adapter in adapters:
        assert adapter["adapter_id"]
        assert adapter["supported_formats"]
        assert 0.0 <= adapter["confidence"] <= 1.0
        assert_adapter_safe(adapter)


def test_get_adapter_by_id_returns_copy():
    adapter = get_skill_import_adapter("codex_instruction_adapter")
    assert adapter is not None
    assert "codex_instruction" in adapter["supported_formats"]
    assert_adapter_safe(adapter)

    adapter["adapter_id"] = "mutated"
    assert get_skill_import_adapter("codex_instruction_adapter")["adapter_id"] == "codex_instruction_adapter"


def test_select_adapter_by_format():
    assert select_skill_import_adapter("anthropic_skill")["adapter_id"] == "anthropic_skill_adapter"
    assert select_skill_import_adapter("cursor_rule")["adapter_id"] == "cursor_rule_adapter"
    assert select_skill_import_adapter("mcp_tool_instruction")["adapter_id"] == "mcp_tool_instruction_adapter"


def test_unknown_uses_fallback_and_is_safe():
    adapter = select_skill_import_adapter("not_real")

    assert adapter["adapter_id"] == "unknown_fallback_adapter"
    assert_adapter_safe(adapter)
