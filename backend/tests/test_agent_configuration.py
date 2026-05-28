import pytest
from pydantic import ValidationError

from backend.apps.agents.orchestration.models import AgentContract
from backend.apps.configuration.models import AgentConfig


def test_agent_config_requires_agent_id():
    with pytest.raises(ValidationError):
        AgentConfig()


def test_agent_contract_legacy_without_configuration_loads_defaults():
    contract = AgentContract(
        role="CoordinatorAgent",
        objective="Coordinate work",
    )

    dumped = contract.model_dump(mode="json")
    dumped.pop("configuration")
    dumped.pop("effective_configuration")
    dumped.pop("configuration_sources")
    dumped.pop("configuration_conflicts")

    loaded = AgentContract(**dumped)

    assert loaded.configuration == {}
    assert loaded.effective_configuration == {}
    assert loaded.configuration_sources == {}
    assert loaded.configuration_conflicts == []


def test_agent_config_sanitizes_secrets_and_mcp_activation():
    from backend.apps.configuration.models import sanitize_agent_config_payload

    sanitized = sanitize_agent_config_payload(
        {
            "api_key": "sk-test",
            "token": "t",
            "password": "p",
            "credential": "c",
            "private_key": "k",
            "mcp_policy": {"active_mcps": ["gmail"], "activate_from_config_load": True},
            "tool_policy": {"auth_token": "nested", "never_assume_permissions": True},
        },
        agent_id="agent-1",
    )

    assert sanitized["agent_id"] == "agent-1"
    assert "api_key" not in sanitized
    assert "token" not in sanitized
    assert "password" not in sanitized
    assert "credential" not in sanitized
    assert "private_key" not in sanitized
    assert "auth_token" not in sanitized["tool_policy"]
    assert "active_mcps" not in sanitized["mcp_policy"]
    assert "activate_from_config_load" not in sanitized["mcp_policy"]


def test_agent_config_can_feed_resolver():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    config = AgentConfig(agent_id="agent-1", model="qwen2.5-coder:32b")
    result = resolve_effective_config(agent_config=config.to_agent_config())

    assert result.effective_config.values["model"] == "qwen2.5-coder:32b"
    assert result.source_map["model"] == ConfigSource.AGENT_CONFIG


def test_agent_override_wins_over_swarm_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        swarm_config={"model": "qwen2.5-coder:14b"},
        agent_config=AgentConfig(agent_id="agent-1", model="qwen2.5-coder:32b").to_agent_config(),
    )

    assert result.effective_config.values["model"] == "qwen2.5-coder:32b"
    assert result.source_map["model"] == ConfigSource.AGENT_CONFIG


def test_agent_defaults_do_not_override_swarm_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        swarm_config={
            "model": "qwen2.5-coder:14b",
            "tool_policy": {"require_approval_for_privileged_tools": False},
        },
        agent_config=AgentConfig(agent_id="agent-1").to_agent_config(),
    )

    assert result.effective_config.values["model"] == "qwen2.5-coder:14b"
    assert result.source_map["model"] == ConfigSource.SWARM_CONFIG
    assert result.effective_config.values["tool_policy"] == {"require_approval_for_privileged_tools": False}
    assert result.source_map["tool_policy"] == ConfigSource.SWARM_CONFIG


def test_effective_hash_changes_when_agent_config_changes():
    from backend.apps.configuration.resolver import resolve_effective_config

    first = resolve_effective_config(agent_config=AgentConfig(agent_id="agent-1").to_agent_config())
    second = resolve_effective_config(
        agent_config=AgentConfig(agent_id="agent-1", model="qwen2.5-coder:32b").to_agent_config()
    )

    assert first.effective_config_hash != second.effective_config_hash


def test_agent_role_metadata_does_not_become_explicit_agent_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    agent_config = AgentConfig(
        agent_id="agent-1",
        swarm_id="swarm-1",
        agent_role="CoordinatorAgent",
    ).to_agent_config()

    result = resolve_effective_config(
        swarm_config={"agent_role": "swarm_default_role"},
        agent_config=agent_config,
    )

    assert agent_config == {}
    assert result.effective_config.values["agent_role"] == "swarm_default_role"
    assert result.source_map["agent_role"] == ConfigSource.SWARM_CONFIG
