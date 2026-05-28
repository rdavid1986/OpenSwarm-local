"""Configuration model contracts for CONFIG.1/CONFIG.2."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


GLOBAL_CONFIG_SCHEMA_VERSION = 1
PROJECT_CONFIG_SCHEMA_VERSION = 1
SWARM_CONFIG_SCHEMA_VERSION = 1
AGENT_CONFIG_SCHEMA_VERSION = 1

SECRET_KEY_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "credential",
    "auth_token",
    "bearer",
    "private_key",
)

MCP_ACTIVATION_KEYS = {
    "active_mcps",
    "activated_mcps",
    "activate_mcp",
    "mcp_activation",
    "mcp_enabled",
    "enabled_mcp_servers",
    "activate_from_config_load",
}


class GlobalUserConfig(BaseModel):
    """Persisted global user configuration.

    This model intentionally contains no secret fields. Nested policy dicts are
    sanitized before validation/persistence by ``sanitize_global_config_payload``.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int = GLOBAL_CONFIG_SCHEMA_VERSION
    default_language: str = "es"
    default_response_style: Literal["brief", "balanced", "detailed"] = "brief"
    default_workflow_methodology: Literal["inspect_then_change", "plan_then_execute", "direct"] = "inspect_then_change"
    default_model: str = "auto"
    default_thinking_level: Literal["off", "low", "medium", "high", "auto"] = "auto"
    default_code_style: dict[str, Any] = Field(default_factory=lambda: {
        "technical_names_language": "english",
        "prefer_minimal_patches": True,
    })
    default_console_shell: Literal["powershell", "bash", "cmd", "auto"] = "powershell"
    default_validation_policy: dict[str, Any] = Field(default_factory=lambda: {
        "run_targeted_tests": True,
        "run_typecheck_when_useful": True,
        "run_build_when_useful": False,
    })
    default_commit_policy: Literal["never_without_explicit_request", "ask_first", "allowed"] = "never_without_explicit_request"
    default_docs_update_policy: dict[str, Any] = Field(default_factory=lambda: {
        "update_roadmap_every_closed_phases": 4,
        "preserve_existing_content": True,
    })
    default_memory_policy: dict[str, Any] = Field(default_factory=lambda: {
        "scope": "project",
        "allow_sensitive_global_memory_in_miniagents": False,
    })
    default_tool_policy: dict[str, Any] = Field(default_factory=lambda: {
        "require_approval_for_privileged_tools": True,
        "never_assume_permissions": True,
    })
    default_mcp_policy: dict[str, Any] = Field(default_factory=lambda: {
        "allow_configured_catalog_visibility": True,
        "activation_requires_explicit_user_action": True,
        "activate_from_config_load": False,
    })

    def to_user_global_config(self) -> dict[str, Any]:
        """Return a JSON-safe mapping for CONFIG.0 ``user_global`` resolution."""
        return sanitize_global_config_payload(self.model_dump())


class ProjectConfig(BaseModel):
    """Persisted project-level configuration.

    ``project_id`` is required because it anchors the controlled persistence
    path. Defaults are intentionally safe and inherit model choice from global
    configuration via ``auto``/``inherit`` values.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int = PROJECT_CONFIG_SCHEMA_VERSION
    project_id: str
    project_name: str | None = None
    project_root: str | None = None
    project_instructions: str = ""
    default_language: str | None = None
    default_model: str | None = None
    preferred_workflow: Literal["inherit", "inspect_then_change", "plan_then_execute", "direct"] = "inherit"
    preferred_models: dict[str, Any] = Field(default_factory=lambda: {
        "primary": "auto",
        "fallback": "inherit",
    })
    tool_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_global": True,
        "require_approval_for_privileged_tools": True,
        "never_assume_permissions": True,
    })
    mcp_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_global": True,
        "activation_requires_explicit_user_action": True,
        "activate_from_config_load": False,
    })
    validation_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_global": True,
        "run_targeted_tests": True,
    })
    docs_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_global": True,
        "preserve_existing_content": True,
    })
    memory_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_global": True,
        "scope": "project",
        "allow_sensitive_global_memory_in_miniagents": False,
    })

    def to_project_config(self) -> dict[str, Any]:
        """Return a JSON-safe mapping for CONFIG.0 ``project_config`` resolution."""
        return sanitize_project_config_payload(self.model_dump(exclude_none=True))


class SwarmConfig(BaseModel):
    """Persisted swarm-level configuration.

    ``swarm_id`` is required because this config is stored on SwarmState and
    must remain associated with one swarm. Defaults are safe and inherit model
    choices via ``auto``/``inherit`` values.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int = SWARM_CONFIG_SCHEMA_VERSION
    swarm_id: str
    project_id: str | None = None
    swarm_role: Literal["coordinator", "implementation", "review", "research", "general"] = "general"
    orchestration_style: Literal["inherit", "conservative", "balanced", "parallel"] = "inherit"
    planning_depth: Literal["inherit", "shallow", "standard", "deep"] = "inherit"
    agent_creation_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_global": True,
        "require_user_approval_for_new_agents": True,
    })
    miniagent_strategy: Literal["inherit", "disabled", "reduced_context", "task_scoped"] = "inherit"
    allowed_domains: list[str] = Field(default_factory=list)
    preferred_models: dict[str, Any] = Field(default_factory=lambda: {
        "primary": "auto",
        "fallback": "inherit",
    })
    tool_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_project": True,
        "require_approval_for_privileged_tools": True,
        "never_assume_permissions": True,
    })
    mcp_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_project": True,
        "activation_requires_explicit_user_action": True,
        "activate_from_config_load": False,
    })
    validation_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_project": True,
        "run_targeted_tests": True,
    })
    memory_scope: Literal["inherit", "swarm", "project", "none"] = "inherit"

    def to_swarm_config(self) -> dict[str, Any]:
        """Return explicit swarm overrides for CONFIG.0 resolution.

        Default swarm values are safe UI/storage defaults, not effective-config
        overrides. Only values that differ from a default SwarmConfig are sent to
        the resolver, so project/global configuration can still inherit normally.
        """
        payload = sanitize_swarm_config_payload(self.model_dump(exclude_none=True))
        defaults = sanitize_swarm_config_payload(
            SwarmConfig(swarm_id=self.swarm_id, project_id=self.project_id).model_dump(exclude_none=True)
        )
        explicit: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"schema_version", "swarm_id"}:
                continue
            if value == "inherit":
                continue
            default_value = defaults.get(key)
            if value == default_value:
                continue
            if isinstance(value, dict):
                default_dict = default_value if isinstance(default_value, dict) else {}
                clean_dict = {
                    nested_key: nested_value
                    for nested_key, nested_value in value.items()
                    if nested_value != "inherit"
                    and not str(nested_key).startswith("inherit_")
                    and nested_value != default_dict.get(nested_key)
                }
                if clean_dict:
                    explicit[key] = clean_dict
                continue
            if isinstance(value, list) and not value:
                continue
            explicit[key] = value
        return explicit


def default_swarm_config(swarm_id: str, *, project_id: str | None = None) -> SwarmConfig:
    return SwarmConfig(swarm_id=swarm_id, project_id=project_id)


class AgentConfig(BaseModel):
    """Persisted agent-level configuration.

    ``agent_id`` is required because this config is stored on AgentContract and
    must remain associated with one agent contract inside a SwarmState.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int = AGENT_CONFIG_SCHEMA_VERSION
    agent_id: str
    swarm_id: str | None = None
    agent_role: str | None = None
    provider: str | None = None
    model: str | None = None
    thinking_level: Literal["inherit", "off", "low", "medium", "high", "auto"] = "inherit"
    tool_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_swarm": True,
        "require_approval_for_privileged_tools": True,
        "never_assume_permissions": True,
    })
    mcp_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_swarm": True,
        "activation_requires_explicit_user_action": True,
        "activate_from_config_load": False,
    })
    validation_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_swarm": True,
        "run_targeted_tests": True,
    })
    memory_scope: Literal["inherit", "agent", "swarm", "project", "none"] = "inherit"
    context_policy: dict[str, Any] = Field(default_factory=lambda: {
        "inherit_swarm": True,
        "reduced_context_by_default": True,
    })

    def to_agent_config(self) -> dict[str, Any]:
        """Return explicit agent overrides for CONFIG.0 resolution."""
        payload = sanitize_agent_config_payload(self.model_dump(exclude_none=True))
        defaults = sanitize_agent_config_payload(
            AgentConfig(agent_id=self.agent_id, swarm_id=self.swarm_id).model_dump(exclude_none=True)
        )
        explicit: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"schema_version", "agent_id", "swarm_id", "agent_role"}:
                continue
            if value == "inherit":
                continue
            default_value = defaults.get(key)
            if value == default_value:
                continue
            if isinstance(value, dict):
                default_dict = default_value if isinstance(default_value, dict) else {}
                clean_dict = {
                    nested_key: nested_value
                    for nested_key, nested_value in value.items()
                    if nested_value != "inherit"
                    and not str(nested_key).startswith("inherit_")
                    and nested_value != default_dict.get(nested_key)
                }
                if clean_dict:
                    explicit[key] = clean_dict
                continue
            if isinstance(value, list) and not value:
                continue
            explicit[key] = value
        return explicit


def default_agent_config(agent_id: str, *, swarm_id: str | None = None, agent_role: str | None = None) -> AgentConfig:
    return AgentConfig(agent_id=agent_id, swarm_id=swarm_id, agent_role=agent_role)


def default_project_config(project_id: str, *, project_name: str | None = None) -> ProjectConfig:
    return ProjectConfig(project_id=project_id, project_name=project_name)


def default_global_config() -> GlobalUserConfig:
    return GlobalUserConfig()


def sanitize_global_config_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Remove secrets and unsafe activation keys from global config payloads."""
    if not isinstance(payload, dict):
        return {}
    sanitized = _sanitize_value(payload)
    if not isinstance(sanitized, dict):
        return {}
    sanitized["schema_version"] = GLOBAL_CONFIG_SCHEMA_VERSION
    return sanitized



def sanitize_project_config_payload(payload: dict[str, Any] | None, *, project_id: str | None = None) -> dict[str, Any]:
    """Remove secrets and unsafe activation keys from project config payloads."""
    if not isinstance(payload, dict):
        payload = {}
    sanitized = _sanitize_value(payload)
    if not isinstance(sanitized, dict):
        sanitized = {}
    if project_id is not None:
        sanitized["project_id"] = project_id
    sanitized["schema_version"] = PROJECT_CONFIG_SCHEMA_VERSION
    return sanitized



def sanitize_swarm_config_payload(payload: dict[str, Any] | None, *, swarm_id: str | None = None) -> dict[str, Any]:
    """Remove secrets and unsafe activation keys from swarm config payloads."""
    if not isinstance(payload, dict):
        payload = {}
    sanitized = _sanitize_value(payload)
    if not isinstance(sanitized, dict):
        sanitized = {}
    if swarm_id is not None:
        sanitized["swarm_id"] = swarm_id
    sanitized["schema_version"] = SWARM_CONFIG_SCHEMA_VERSION
    return sanitized


def sanitize_agent_config_payload(payload: dict[str, Any] | None, *, agent_id: str | None = None) -> dict[str, Any]:
    """Remove secrets and unsafe activation keys from agent config payloads."""
    if not isinstance(payload, dict):
        payload = {}
    sanitized = _sanitize_value(payload)
    if not isinstance(sanitized, dict):
        sanitized = {}
    if agent_id is not None:
        sanitized["agent_id"] = agent_id
    sanitized["schema_version"] = AGENT_CONFIG_SCHEMA_VERSION
    return sanitized


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            key_lower = key.lower()
            if _is_secret_key(key_lower) or (_is_mcp_activation_key(key_lower) and bool(raw_value)):
                continue
            clean[key] = _sanitize_value(raw_value)
        return clean
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _is_secret_key(key_lower: str) -> bool:
    return any(fragment in key_lower for fragment in SECRET_KEY_FRAGMENTS)


def _is_mcp_activation_key(key_lower: str) -> bool:
    return key_lower in MCP_ACTIVATION_KEYS or (
        key_lower.startswith("mcp") and any(fragment in key_lower for fragment in ("active", "activate", "enabled"))
    )
