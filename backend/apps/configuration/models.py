"""Global user configuration contracts for CONFIG.1."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


GLOBAL_CONFIG_SCHEMA_VERSION = 1

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
        "update_roadmap_every_closed_phases": 2,
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


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            key_lower = key.lower()
            if _is_secret_key(key_lower) or _is_mcp_activation_key(key_lower):
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
