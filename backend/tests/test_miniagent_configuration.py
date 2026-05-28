import pytest
from pydantic import ValidationError

from backend.apps.agents.orchestration.models import SwarmState
from backend.apps.configuration.models import MiniAgentConfig


def test_miniagent_config_requires_miniagent_id():
    with pytest.raises(ValidationError):
        MiniAgentConfig()


def test_swarm_state_legacy_without_miniagent_profiles_loads_defaults():
    swarm = SwarmState(
        id="swarm-legacy",
        title="Legacy",
        user_prompt="Do work",
    )

    dumped = swarm.model_dump(mode="json")
    dumped.pop("miniagent_profiles")

    loaded = SwarmState(**dumped)

    assert loaded.miniagent_profiles == {}


def test_miniagent_config_sanitizes_secrets_and_mcp_activation():
    from backend.apps.configuration.models import sanitize_miniagent_config_payload

    sanitized = sanitize_miniagent_config_payload(
        {
            "api_key": "sk-test",
            "token": "t",
            "password": "p",
            "credential": "c",
            "private_key": "k",
            "mcp_policy": {"active_mcps": ["gmail"], "activate_from_config_load": True},
            "tool_policy": {"auth_token": "nested", "never_assume_permissions": True},
        },
        miniagent_id="mini-1",
    )

    assert sanitized["miniagent_id"] == "mini-1"
    assert "api_key" not in sanitized
    assert "token" not in sanitized
    assert "password" not in sanitized
    assert "credential" not in sanitized
    assert "private_key" not in sanitized
    assert "auth_token" not in sanitized["tool_policy"]
    assert "active_mcps" not in sanitized["mcp_policy"]
    assert "activate_from_config_load" not in sanitized["mcp_policy"]


def test_miniagent_config_can_feed_resolver():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    config = MiniAgentConfig(miniagent_id="mini-1", specialization="css_patch")
    result = resolve_effective_config(miniagent_config=config.to_miniagent_config())

    assert result.effective_config.values["specialization"] == "css_patch"
    assert result.source_map["specialization"] == ConfigSource.MINIAGENT_CONFIG


def test_miniagent_override_wins_over_agent_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        agent_config={"model": "qwen2.5-coder:14b"},
        miniagent_config=MiniAgentConfig(miniagent_id="mini-1", model="qwen2.5-coder:32b").to_miniagent_config(),
    )

    assert result.effective_config.values["model"] == "qwen2.5-coder:32b"
    assert result.source_map["model"] == ConfigSource.MINIAGENT_CONFIG


def test_miniagent_defaults_do_not_override_agent_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        agent_config={
            "model": "qwen2.5-coder:14b",
            "context_policy": {"reduced_context_by_default": False},
        },
        miniagent_config=MiniAgentConfig(miniagent_id="mini-1").to_miniagent_config(),
    )

    assert result.effective_config.values["model"] == "qwen2.5-coder:14b"
    assert result.source_map["model"] == ConfigSource.AGENT_CONFIG
    assert result.effective_config.values["context_policy"] == {"reduced_context_by_default": False}
    assert result.source_map["context_policy"] == ConfigSource.AGENT_CONFIG


def test_miniagent_metadata_does_not_become_explicit_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    config = MiniAgentConfig(
        miniagent_id="mini-1",
        parent_swarm_id="swarm-1",
        parent_agent_id="agent-1",
        miniagent_role="CssPatchMiniAgent",
    ).to_miniagent_config()

    result = resolve_effective_config(
        agent_config={"miniagent_role": "agent_default_role"},
        miniagent_config=config,
    )

    assert config == {}
    assert result.effective_config.values["miniagent_role"] == "agent_default_role"
    assert result.source_map["miniagent_role"] == ConfigSource.AGENT_CONFIG


def test_miniagent_export_reuse_bundle_and_skill_policy_defaults_safe():
    config = MiniAgentConfig(miniagent_id="mini-1")

    assert config.export_policy["exportable"] is False
    assert config.export_policy["include_sensitive_data"] is False
    assert config.reuse_policy["reusable"] is False
    assert config.reuse_policy["requires_user_approval"] is True
    assert config.bundle_policy["can_export_with_bundle"] is False
    assert config.skill_policy["can_use_skills"] is True
    assert config.skill_policy["can_request_skills"] is True
    assert config.skill_policy["can_create_skills"] is False
    assert config.skill_policy["can_assign_skills"] is False
    assert config.skill_policy["can_validate_skills"] is False


def test_effective_hash_changes_when_miniagent_config_changes():
    from backend.apps.configuration.resolver import resolve_effective_config

    first = resolve_effective_config(miniagent_config=MiniAgentConfig(miniagent_id="mini-1").to_miniagent_config())
    second = resolve_effective_config(
        miniagent_config=MiniAgentConfig(miniagent_id="mini-1", specialization="css_patch").to_miniagent_config()
    )

    assert first.effective_config_hash != second.effective_config_hash
