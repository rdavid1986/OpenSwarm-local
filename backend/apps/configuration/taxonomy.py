"""Side-effect free configuration taxonomy for OpenSwarm.

CONFIG.0 defines the configuration scopes and contracts only. This module does
not read settings files, touch runtime state, activate MCP servers, or execute
policy checks with side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConfigScope(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    DASHBOARD = "dashboard"
    SWARM = "swarm"
    AGENT = "agent"
    MINIAGENT = "miniagent"
    MODE = "mode"
    TOOL = "tool"
    MCP = "mcp"
    RUNTIME_SESSION = "runtime_session"
    MESSAGE_TURN = "message_turn"


class ConfigSource(str, Enum):
    SYSTEM_DEFAULT = "system_default"
    USER_GLOBAL = "user_global"
    PROJECT_CONFIG = "project_config"
    DASHBOARD_CONFIG = "dashboard_config"
    SWARM_CONFIG = "swarm_config"
    AGENT_CONFIG = "agent_config"
    MINIAGENT_CONFIG = "miniagent_config"
    MODE_CONFIG = "mode_config"
    RUNTIME_OVERRIDE = "runtime_override"
    TURN_INSTRUCTION = "turn_instruction"


@dataclass(frozen=True)
class ConfigSafetyNote:
    code: str
    message: str
    key: str | None = None
    source: ConfigSource | None = None
    scope: ConfigScope | None = None


@dataclass(frozen=True)
class ConfigConflict:
    key: str
    existing_source: ConfigSource | None
    incoming_source: ConfigSource
    reason: str
    blocked: bool = False


@dataclass(frozen=True)
class ConfigRequiredAction:
    code: str
    message: str
    key: str | None = None
    source: ConfigSource | None = None


@dataclass(frozen=True)
class EffectiveConfig:
    values: dict[str, Any]
    source_map: dict[str, ConfigSource]
    safety_notes: tuple[ConfigSafetyNote, ...] = ()
    effective_config_hash: str = ""


@dataclass(frozen=True)
class ConfigurationScopeRule:
    scope: ConfigScope
    configurable_keys: tuple[str, ...]
    persistence_behavior: str
    inheritance_behavior: str
    override_behavior: str
    approval_requirement: str
    can_affect_tools: bool
    can_affect_mcp: bool
    can_affect_models: bool
    can_affect_memory: bool
    security_notes: tuple[str, ...]


@dataclass(frozen=True)
class ConfigurationScopeMatrix:
    rules: tuple[ConfigurationScopeRule, ...] = field(default_factory=tuple)

    def get_rule(self, scope: ConfigScope | str) -> ConfigurationScopeRule:
        normalized = ConfigScope(scope)
        for rule in self.rules:
            if rule.scope == normalized:
                return rule
        raise KeyError(f"configuration scope not registered: {scope}")

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {
            rule.scope.value: {
                "configurable_keys": list(rule.configurable_keys),
                "persistence_behavior": rule.persistence_behavior,
                "inheritance_behavior": rule.inheritance_behavior,
                "override_behavior": rule.override_behavior,
                "approval_requirement": rule.approval_requirement,
                "can_affect_tools": rule.can_affect_tools,
                "can_affect_mcp": rule.can_affect_mcp,
                "can_affect_models": rule.can_affect_models,
                "can_affect_memory": rule.can_affect_memory,
                "security_notes": list(rule.security_notes),
            }
            for rule in self.rules
        }


BASE_SAFETY_NOTES = (
    "never expose secrets",
    "never activate MCP from configuration load alone",
    "never assume permissions",
    "never mix sensitive global memory into miniagent scope unless explicitly allowed",
    "never pass full context when reduced context is enough",
    "never present estimated data as measured/real",
    "never apply override that violates sandbox/guards",
)


CONFIGURATION_SCOPE_MATRIX = ConfigurationScopeMatrix(
    rules=(
        ConfigurationScopeRule(
            scope=ConfigScope.GLOBAL,
            configurable_keys=("default_model", "default_mode", "theme", "provider_preferences", "memory_policy"),
            persistence_behavior="persisted in user-level settings; secrets must remain outside effective config",
            inheritance_behavior="inherited by all lower scopes unless overridden",
            override_behavior="may be overridden by any more specific scope",
            approval_requirement="approval required for permissions, tools, MCP activation, or sensitive memory changes",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=True,
            can_affect_memory=True,
            security_notes=BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.PROJECT,
            configurable_keys=("project_root", "default_model", "allowed_paths", "mode_defaults", "memory_scope"),
            persistence_behavior="persisted with project-local configuration when available",
            inheritance_behavior="inherits global values and provides project defaults",
            override_behavior="overrides global; lower scopes may override within project guards",
            approval_requirement="approval required for path expansion, tool access, or sandbox-affecting values",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=True,
            can_affect_memory=True,
            security_notes=BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.DASHBOARD,
            configurable_keys=("layout", "agent_visibility", "default_dashboard_mode", "ui_preferences"),
            persistence_behavior="persisted as dashboard/UI preference state",
            inheritance_behavior="inherits global/project presentation defaults",
            override_behavior="overrides presentation-level defaults only",
            approval_requirement="approval not required unless it attempts runtime/tool/MCP changes",
            can_affect_tools=False,
            can_affect_mcp=False,
            can_affect_models=False,
            can_affect_memory=False,
            security_notes=("UI configuration must not imply tool or MCP authorization",),
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.SWARM,
            configurable_keys=("swarm_policy", "default_agent_model", "allowed_tools", "active_memory_scope", "context_budget"),
            persistence_behavior="persisted with swarm state when the swarm is persisted",
            inheritance_behavior="inherits project/dashboard defaults relevant to swarm runtime",
            override_behavior="overrides project defaults inside the swarm boundary",
            approval_requirement="approval required for tool expansion, MCP use, or guard relaxation",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=True,
            can_affect_memory=True,
            security_notes=BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.AGENT,
            configurable_keys=("model", "mode", "allowed_tools", "system_prompt", "context_budget", "memory_scope"),
            persistence_behavior="persisted with agent/session metadata when applicable",
            inheritance_behavior="inherits swarm defaults",
            override_behavior="overrides swarm defaults for one agent",
            approval_requirement="approval required for tool/MCP expansion or sensitive context access",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=True,
            can_affect_memory=True,
            security_notes=BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.MINIAGENT,
            configurable_keys=("task_model", "allowed_tools", "reduced_context", "handoff_contract", "memory_access"),
            persistence_behavior="ephemeral unless explicitly checkpointed by the parent runtime",
            inheritance_behavior="inherits only reduced agent context by default",
            override_behavior="overrides agent defaults inside delegated task limits",
            approval_requirement="approval required to access sensitive/global memory or expand tools",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=True,
            can_affect_memory=True,
            security_notes=BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.MODE,
            configurable_keys=("mode_name", "prompt_contract", "allowed_tools", "model_preferences", "approval_policy"),
            persistence_behavior="persisted as mode definition or selected as runtime metadata",
            inheritance_behavior="inherits project/swarm defaults and constrains lower scopes",
            override_behavior="overrides generic behavior while preserving safety guards",
            approval_requirement="approval required for unsafe tool or permission grants",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=True,
            can_affect_memory=True,
            security_notes=BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.TOOL,
            configurable_keys=("tool_policy", "tool_timeout", "tool_input_limits", "path_scope"),
            persistence_behavior="persisted in tool definitions or runtime policy metadata",
            inheritance_behavior="inherits mode/agent/swarm guard constraints",
            override_behavior="may narrow permissions; cannot relax sandbox/guards without approval",
            approval_requirement="approval required for ask-policy tools and any guard relaxation",
            can_affect_tools=True,
            can_affect_mcp=False,
            can_affect_models=False,
            can_affect_memory=False,
            security_notes=("tool configuration cannot authorize paths outside policy scope",) + BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.MCP,
            configurable_keys=("server_ref", "auth_status", "available_tools", "inspection_summary"),
            persistence_behavior="persisted in MCP registry/connection metadata, not activated by taxonomy load",
            inheritance_behavior="inherits policy gates from project/swarm/agent/mode",
            override_behavior="may describe availability; cannot activate by configuration load alone",
            approval_requirement="explicit user/tool action required to activate or authorize MCP access",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=False,
            can_affect_memory=False,
            security_notes=("MCP configuration can describe availability but cannot activate MCP by load",) + BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.RUNTIME_SESSION,
            configurable_keys=("runtime_overrides", "temporary_model", "temporary_allowed_tools", "session_memory_scope"),
            persistence_behavior="ephemeral session state unless separately persisted as evidence",
            inheritance_behavior="inherits all applicable persisted scopes",
            override_behavior="overrides persisted scopes for the current runtime session unless blocked by guards",
            approval_requirement="approval required for privileged runtime changes",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=True,
            can_affect_memory=True,
            security_notes=BASE_SAFETY_NOTES,
        ),
        ConfigurationScopeRule(
            scope=ConfigScope.MESSAGE_TURN,
            configurable_keys=("turn_instruction", "temporary_context_limit", "requested_tool", "requested_output_format"),
            persistence_behavior="ephemeral per message turn; not persisted as default configuration",
            inheritance_behavior="inherits effective session configuration",
            override_behavior="most specific override; cannot bypass safety/guards",
            approval_requirement="approval required for tool/MCP/permission changes requested in-turn",
            can_affect_tools=True,
            can_affect_mcp=True,
            can_affect_models=True,
            can_affect_memory=True,
            security_notes=BASE_SAFETY_NOTES,
        ),
    )
)


def build_configuration_scope_matrix() -> ConfigurationScopeMatrix:
    """Return the side-effect free CONFIG.0.A scope matrix."""
    return CONFIGURATION_SCOPE_MATRIX
