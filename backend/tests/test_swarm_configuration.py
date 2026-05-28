from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.apps.agents.orchestration.models import SwarmState
from backend.apps.configuration.models import SwarmConfig


def test_swarm_config_requires_swarm_id():
    with pytest.raises(ValidationError):
        SwarmConfig()


def test_swarm_state_legacy_without_configuration_loads_defaults():
    swarm = SwarmState(
        id="swarm-legacy",
        title="Legacy",
        user_prompt="Do work",
    )

    dumped = swarm.model_dump(mode="json")
    dumped.pop("configuration")
    dumped.pop("effective_configuration")
    dumped.pop("configuration_sources")
    dumped.pop("configuration_conflicts")

    loaded = SwarmState(**dumped)

    assert loaded.configuration == {}
    assert loaded.effective_configuration == {}
    assert loaded.configuration_sources == {}
    assert loaded.configuration_conflicts == []


def test_swarm_config_sanitizes_secrets_and_mcp_activation():
    from backend.apps.configuration.models import sanitize_swarm_config_payload

    sanitized = sanitize_swarm_config_payload(
        {
            "api_key": "sk-test",
            "token": "t",
            "password": "p",
            "credential": "c",
            "private_key": "k",
            "mcp_policy": {"active_mcps": ["gmail"], "activate_from_config_load": True},
            "tool_policy": {"auth_token": "nested", "never_assume_permissions": True},
        },
        swarm_id="swarm-1",
    )

    assert sanitized["swarm_id"] == "swarm-1"
    assert "api_key" not in sanitized
    assert "token" not in sanitized
    assert "password" not in sanitized
    assert "credential" not in sanitized
    assert "private_key" not in sanitized
    assert "auth_token" not in sanitized["tool_policy"]
    assert "active_mcps" not in sanitized["mcp_policy"]
    assert "activate_from_config_load" not in sanitized["mcp_policy"]


def test_swarm_config_to_swarm_config_can_feed_resolver():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    config = SwarmConfig(swarm_id="swarm-1", orchestration_style="balanced")
    result = resolve_effective_config(swarm_config=config.to_swarm_config())

    assert result.effective_config.values["orchestration_style"] == "balanced"
    assert result.source_map["orchestration_style"] == ConfigSource.SWARM_CONFIG


def test_swarm_override_wins_over_project_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        project_config={"planning_depth": "shallow"},
        swarm_config=SwarmConfig(swarm_id="swarm-1", planning_depth="deep").to_swarm_config(),
    )

    assert result.effective_config.values["planning_depth"] == "deep"
    assert result.source_map["planning_depth"] == ConfigSource.SWARM_CONFIG


def test_project_config_wins_over_user_global_when_swarm_does_not_override():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        user_global={"default_language": "es"},
        project_config={"default_language": "pt"},
        swarm_config=SwarmConfig(swarm_id="swarm-1").to_swarm_config(),
    )

    assert result.effective_config.values["default_language"] == "pt"
    assert result.source_map["default_language"] == ConfigSource.PROJECT_CONFIG


def test_user_global_works_without_project_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        user_global={"default_language": "es"},
        swarm_config=SwarmConfig(swarm_id="swarm-1").to_swarm_config(),
    )

    assert result.effective_config.values["default_language"] == "es"
    assert result.source_map["default_language"] == ConfigSource.USER_GLOBAL


def test_effective_hash_changes_when_swarm_config_changes():
    from backend.apps.configuration.resolver import resolve_effective_config

    first = resolve_effective_config(swarm_config=SwarmConfig(swarm_id="swarm-1").to_swarm_config())
    second = resolve_effective_config(
        swarm_config=SwarmConfig(swarm_id="swarm-1", orchestration_style="balanced").to_swarm_config()
    )

    assert first.effective_config_hash != second.effective_config_hash


def test_swarm_inherit_defaults_do_not_override_project_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        user_global={"planning_depth": "shallow"},
        project_config={"planning_depth": "standard"},
        swarm_config=SwarmConfig(swarm_id="swarm-1").to_swarm_config(),
    )

    assert result.effective_config.values["planning_depth"] == "standard"
    assert result.source_map["planning_depth"] == ConfigSource.PROJECT_CONFIG


def test_swarm_default_dicts_do_not_override_project_config():
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config

    result = resolve_effective_config(
        project_config={
            "preferred_models": {"primary": "qwen2.5-coder:32b"},
            "tool_policy": {"require_approval_for_privileged_tools": False},
            "validation_policy": {"run_targeted_tests": False},
        },
        swarm_config=SwarmConfig(swarm_id="swarm-1").to_swarm_config(),
    )

    assert result.effective_config.values["preferred_models"] == {"primary": "qwen2.5-coder:32b"}
    assert result.source_map["preferred_models"] == ConfigSource.PROJECT_CONFIG
    assert result.effective_config.values["tool_policy"] == {"require_approval_for_privileged_tools": False}
    assert result.source_map["tool_policy"] == ConfigSource.PROJECT_CONFIG
    assert result.effective_config.values["validation_policy"] == {"run_targeted_tests": False}
    assert result.source_map["validation_policy"] == ConfigSource.PROJECT_CONFIG
