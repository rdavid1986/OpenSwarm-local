from backend.apps.configuration import ConfigScope, build_configuration_scope_matrix


REQUIRED_SCOPES = {
    "global",
    "project",
    "dashboard",
    "swarm",
    "agent",
    "miniagent",
    "mode",
    "tool",
    "mcp",
    "runtime_session",
    "message_turn",
}


def test_configuration_scope_matrix_contains_all_required_scopes():
    matrix = build_configuration_scope_matrix()

    assert set(matrix.as_dict()) == REQUIRED_SCOPES


def test_configuration_scope_matrix_rules_declare_required_fields():
    matrix = build_configuration_scope_matrix()

    for scope_name in REQUIRED_SCOPES:
        rule = matrix.get_rule(ConfigScope(scope_name))
        assert rule.configurable_keys
        assert rule.persistence_behavior
        assert rule.inheritance_behavior
        assert rule.override_behavior
        assert rule.approval_requirement
        assert rule.security_notes
        assert isinstance(rule.can_affect_tools, bool)
        assert isinstance(rule.can_affect_mcp, bool)
        assert isinstance(rule.can_affect_models, bool)
        assert isinstance(rule.can_affect_memory, bool)


def test_configuration_scope_matrix_mcp_scope_cannot_activate_by_load():
    rule = build_configuration_scope_matrix().get_rule("mcp")

    assert rule.can_affect_mcp is True
    assert any("cannot activate" in note for note in rule.security_notes)
