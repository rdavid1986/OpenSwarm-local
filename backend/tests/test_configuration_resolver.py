from backend.apps.configuration import ConfigSource, resolve_effective_config


def test_project_override_wins_over_global():
    result = resolve_effective_config(user_global={"model": "global"}, project_config={"model": "project"})

    assert result.effective_config.values["model"] == "project"
    assert result.source_map["model"] == ConfigSource.PROJECT_CONFIG
    assert result.overrides


def test_swarm_override_wins_over_project():
    result = resolve_effective_config(project_config={"model": "project"}, swarm_config={"model": "swarm"})

    assert result.effective_config.values["model"] == "swarm"
    assert result.source_map["model"] == ConfigSource.SWARM_CONFIG


def test_agent_override_wins_over_swarm():
    result = resolve_effective_config(swarm_config={"model": "swarm"}, agent_config={"model": "agent"})

    assert result.effective_config.values["model"] == "agent"
    assert result.source_map["model"] == ConfigSource.AGENT_CONFIG


def test_miniagent_override_wins_over_agent():
    result = resolve_effective_config(agent_config={"model": "agent"}, miniagent_config={"model": "mini"})

    assert result.effective_config.values["model"] == "mini"
    assert result.source_map["model"] == ConfigSource.MINIAGENT_CONFIG


def test_runtime_override_wins_unless_blocked_by_safety():
    result = resolve_effective_config(
        agent_config={"model": "agent", "sandbox_override": False},
        runtime_override={"model": "runtime", "sandbox_override": True},
    )

    assert result.effective_config.values["model"] == "runtime"
    assert result.source_map["model"] == ConfigSource.RUNTIME_OVERRIDE
    assert result.effective_config.values["sandbox_override"] is False
    assert any(entry["key"] == "sandbox_override" for entry in result.blocked_entries)


def test_turn_instruction_wins_unless_blocked_by_safety():
    result = resolve_effective_config(
        runtime_override={"output_format": "json", "active_mcps": []},
        turn_instruction={"output_format": "markdown", "active_mcps": ["gmail"]},
    )

    assert result.effective_config.values["output_format"] == "markdown"
    assert result.source_map["output_format"] == ConfigSource.TURN_INSTRUCTION
    assert result.effective_config.values["active_mcps"] == []
    assert any(entry["key"] == "active_mcps" for entry in result.blocked_entries)


def test_secrets_do_not_appear_in_effective_config():
    result = resolve_effective_config(user_global={"api_key": "sk-secret", "model": "sonnet"})

    assert "api_key" not in result.effective_config.values
    assert result.effective_config.values["model"] == "sonnet"
    assert any(action.code == "remove_secret_from_config" for action in result.required_user_actions)


def test_mcp_cannot_be_activated_by_configuration():
    result = resolve_effective_config(project_config={"active_mcps": ["gmail"], "mcp_catalog_visible": True})

    assert "active_mcps" not in result.effective_config.values
    assert result.effective_config.values["mcp_catalog_visible"] is True
    assert any(action.code == "explicit_mcp_activation_required" for action in result.required_user_actions)


def test_estimated_values_cannot_be_marked_as_measured():
    result = resolve_effective_config(
        system_default={"context_window_source": "estimated"},
        runtime_override={"context_window_measurement": "measured"},
    )

    assert "context_window_measurement" not in result.effective_config.values
    assert result.effective_config.values["context_window_source"] == "estimated"
    assert any(action.code == "provide_measured_evidence" for action in result.required_user_actions)


def test_source_map_preserves_source_for_each_effective_value():
    result = resolve_effective_config(
        system_default={"theme": "dark"},
        project_config={"model": "project"},
        agent_config={"temperature": 0.2},
    )

    assert result.source_map == {
        "theme": ConfigSource.SYSTEM_DEFAULT,
        "model": ConfigSource.PROJECT_CONFIG,
        "temperature": ConfigSource.AGENT_CONFIG,
    }


def test_conflicts_blocked_and_required_actions_are_reported():
    result = resolve_effective_config(
        user_global={"model": "global"},
        project_config={"model": "project"},
        runtime_override={"grant_permission": True},
    )

    assert any(conflict.key == "model" and conflict.blocked is False for conflict in result.conflicts)
    assert any(conflict.key == "grant_permission" and conflict.blocked is True for conflict in result.conflicts)
    assert any(entry["key"] == "grant_permission" for entry in result.blocked_entries)
    assert any(action.code == "explicit_permission_approval_required" for action in result.required_user_actions)


def test_effective_config_hash_changes_when_effective_configuration_changes():
    first = resolve_effective_config(project_config={"model": "sonnet"})
    second = resolve_effective_config(project_config={"model": "opus"})

    assert first.effective_config_hash != second.effective_config_hash
    assert first.effective_config.effective_config_hash == first.effective_config_hash
