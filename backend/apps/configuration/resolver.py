"""Deterministic, side-effect free configuration resolver for CONFIG.0."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from backend.apps.configuration.taxonomy import (
    ConfigConflict,
    ConfigRequiredAction,
    ConfigSafetyNote,
    ConfigScope,
    ConfigSource,
    EffectiveConfig,
)


SOURCE_PRECEDENCE: tuple[ConfigSource, ...] = (
    ConfigSource.SYSTEM_DEFAULT,
    ConfigSource.USER_GLOBAL,
    ConfigSource.PROJECT_CONFIG,
    ConfigSource.DASHBOARD_CONFIG,
    ConfigSource.SWARM_CONFIG,
    ConfigSource.AGENT_CONFIG,
    ConfigSource.MINIAGENT_CONFIG,
    ConfigSource.MODE_CONFIG,
    ConfigSource.RUNTIME_OVERRIDE,
    ConfigSource.TURN_INSTRUCTION,
)

SOURCE_TO_SCOPE: dict[ConfigSource, ConfigScope] = {
    ConfigSource.SYSTEM_DEFAULT: ConfigScope.GLOBAL,
    ConfigSource.USER_GLOBAL: ConfigScope.GLOBAL,
    ConfigSource.PROJECT_CONFIG: ConfigScope.PROJECT,
    ConfigSource.DASHBOARD_CONFIG: ConfigScope.DASHBOARD,
    ConfigSource.SWARM_CONFIG: ConfigScope.SWARM,
    ConfigSource.AGENT_CONFIG: ConfigScope.AGENT,
    ConfigSource.MINIAGENT_CONFIG: ConfigScope.MINIAGENT,
    ConfigSource.MODE_CONFIG: ConfigScope.MODE,
    ConfigSource.RUNTIME_OVERRIDE: ConfigScope.RUNTIME_SESSION,
    ConfigSource.TURN_INSTRUCTION: ConfigScope.MESSAGE_TURN,
}

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

PERMISSION_GRANT_FRAGMENTS = (
    "assume_permission",
    "grant_permission",
    "sandbox_override",
    "disable_guard",
    "bypass_guard",
    "allow_unsafe",
)


@dataclass(frozen=True)
class ConfigurationResolution:
    effective_config: EffectiveConfig
    sources: dict[str, ConfigSource]
    source_map: dict[str, ConfigSource]
    overrides: tuple[dict[str, Any], ...]
    conflicts: tuple[ConfigConflict, ...]
    blocked_entries: tuple[dict[str, Any], ...]
    required_user_actions: tuple[ConfigRequiredAction, ...]
    safety_notes: tuple[ConfigSafetyNote, ...]
    effective_config_hash: str


def resolve_effective_config(
    *,
    system_default: Mapping[str, Any] | None = None,
    user_global: Mapping[str, Any] | None = None,
    project_config: Mapping[str, Any] | None = None,
    dashboard_config: Mapping[str, Any] | None = None,
    swarm_config: Mapping[str, Any] | None = None,
    agent_config: Mapping[str, Any] | None = None,
    miniagent_config: Mapping[str, Any] | None = None,
    mode_config: Mapping[str, Any] | None = None,
    runtime_override: Mapping[str, Any] | None = None,
    turn_instruction: Mapping[str, Any] | None = None,
) -> ConfigurationResolution:
    """Resolve effective config by precedence while preserving source labels.

    The resolver is pure: it never reads from disk, never activates MCP servers,
    never assumes permissions, and never executes tool/model/memory side effects.
    """

    source_payloads: dict[ConfigSource, Mapping[str, Any] | None] = {
        ConfigSource.SYSTEM_DEFAULT: system_default,
        ConfigSource.USER_GLOBAL: user_global,
        ConfigSource.PROJECT_CONFIG: project_config,
        ConfigSource.DASHBOARD_CONFIG: dashboard_config,
        ConfigSource.SWARM_CONFIG: swarm_config,
        ConfigSource.AGENT_CONFIG: agent_config,
        ConfigSource.MINIAGENT_CONFIG: miniagent_config,
        ConfigSource.MODE_CONFIG: mode_config,
        ConfigSource.RUNTIME_OVERRIDE: runtime_override,
        ConfigSource.TURN_INSTRUCTION: turn_instruction,
    }

    values: dict[str, Any] = {}
    source_map: dict[str, ConfigSource] = {}
    overrides: list[dict[str, Any]] = []
    conflicts: list[ConfigConflict] = []
    blocked_entries: list[dict[str, Any]] = []
    required_actions: list[ConfigRequiredAction] = []
    safety_notes: list[ConfigSafetyNote] = []

    for source in SOURCE_PRECEDENCE:
        payload = source_payloads[source]
        if not payload:
            continue
        for key, value in payload.items():
            normalized_key = str(key)
            block_reason = _blocked_reason(normalized_key, value, source, payload, values)
            if block_reason:
                blocked_entries.append({"key": normalized_key, "source": source, "value_preview": _safe_preview(value), "reason": block_reason})
                conflicts.append(
                    ConfigConflict(
                        key=normalized_key,
                        existing_source=source_map.get(normalized_key),
                        incoming_source=source,
                        reason=block_reason,
                        blocked=True,
                    )
                )
                required_actions.append(_required_action_for_block(normalized_key, source, block_reason))
                safety_notes.append(
                    ConfigSafetyNote(
                        code="blocked_by_safety_rule",
                        message=block_reason,
                        key=normalized_key,
                        source=source,
                        scope=SOURCE_TO_SCOPE[source],
                    )
                )
                continue

            if normalized_key in values:
                previous_source = source_map[normalized_key]
                if values[normalized_key] != value or previous_source != source:
                    overrides.append(
                        {
                            "key": normalized_key,
                            "from_source": previous_source,
                            "to_source": source,
                            "from_value_preview": _safe_preview(values[normalized_key]),
                            "to_value_preview": _safe_preview(value),
                        }
                    )
                    conflicts.append(
                        ConfigConflict(
                            key=normalized_key,
                            existing_source=previous_source,
                            incoming_source=source,
                            reason="more specific configuration source overrides previous value",
                            blocked=False,
                        )
                    )

            values[normalized_key] = _copy_jsonish(value)
            source_map[normalized_key] = source

    config_hash = _effective_hash(values)
    effective = EffectiveConfig(
        values=_copy_jsonish(values),
        source_map=dict(source_map),
        safety_notes=tuple(safety_notes),
        effective_config_hash=config_hash,
    )
    return ConfigurationResolution(
        effective_config=effective,
        sources=dict(source_map),
        source_map=dict(source_map),
        overrides=tuple(overrides),
        conflicts=tuple(conflicts),
        blocked_entries=tuple(blocked_entries),
        required_user_actions=tuple(required_actions),
        safety_notes=tuple(safety_notes),
        effective_config_hash=config_hash,
    )


def _blocked_reason(
    key: str,
    value: Any,
    source: ConfigSource,
    payload: Mapping[str, Any],
    current_values: Mapping[str, Any],
) -> str | None:
    key_lower = key.lower()
    if _is_secret_key(key_lower):
        return "secret values cannot be exposed through effective configuration"
    if _attempts_mcp_activation(key_lower, value):
        return "MCP cannot be activated by configuration load alone"
    if _attempts_permission_grant(key_lower, value):
        return "configuration cannot assume permissions or bypass sandbox/guards"
    if source == ConfigSource.MINIAGENT_CONFIG and _is_sensitive_global_memory_key(key_lower):
        if payload.get("allow_sensitive_global_memory") is not True:
            return "miniagent scope cannot receive sensitive global memory unless explicitly allowed"
    if _requests_full_context(key_lower, value):
        return "full context cannot be passed when reduced context is sufficient"
    if _marks_estimated_as_measured(key, value, payload, current_values):
        return "estimated data cannot be presented as measured or real"
    return None


def _is_secret_key(key_lower: str) -> bool:
    return any(fragment in key_lower for fragment in SECRET_KEY_FRAGMENTS)


def _attempts_mcp_activation(key_lower: str, value: Any) -> bool:
    if key_lower in MCP_ACTIVATION_KEYS and bool(value):
        return True
    if key_lower.startswith("mcp.") and any(fragment in key_lower for fragment in ("active", "activate", "enabled")) and bool(value):
        return True
    if key_lower.startswith("mcp_") and any(fragment in key_lower for fragment in ("active", "activate")) and bool(value):
        return True
    return False


def _attempts_permission_grant(key_lower: str, value: Any) -> bool:
    if bool(value) and any(fragment in key_lower for fragment in PERMISSION_GRANT_FRAGMENTS):
        return True
    if key_lower in {"permissions", "sandbox_permissions"} and value not in (None, {}, [], ""):
        return True
    return False


def _is_sensitive_global_memory_key(key_lower: str) -> bool:
    return "sensitive_global_memory" in key_lower or key_lower in {"global_memory", "memory.global_sensitive"}


def _requests_full_context(key_lower: str, value: Any) -> bool:
    return key_lower in {"full_context", "pass_full_context", "context.full"} and value is True


def _marks_estimated_as_measured(key: str, value: Any, payload: Mapping[str, Any], current_values: Mapping[str, Any]) -> bool:
    key_lower = key.lower()
    if isinstance(value, Mapping):
        source = str(value.get("source") or value.get("data_source") or value.get("evidence") or "").lower()
        status = str(value.get("status") or value.get("quality") or value.get("measurement") or "").lower()
        if source == "estimated" and status in {"measured", "real"}:
            return True
    if key_lower.endswith("_measurement") and str(value).lower() in {"measured", "real"}:
        prefix = key[: -len("_measurement")]
        source_value = payload.get(f"{prefix}_source", current_values.get(f"{prefix}_source"))
        if str(source_value).lower() == "estimated":
            return True
    if key_lower.endswith("_source") and str(value).lower() == "measured":
        prefix = key[: -len("_source")]
        estimate_flag = payload.get(f"{prefix}_estimated", current_values.get(f"{prefix}_estimated"))
        if estimate_flag is True:
            return True
    return False


def _required_action_for_block(key: str, source: ConfigSource, reason: str) -> ConfigRequiredAction:
    if "MCP" in reason:
        return ConfigRequiredAction("explicit_mcp_activation_required", "Activate MCP through the explicit runtime/user action path.", key, source)
    if "secret" in reason:
        return ConfigRequiredAction("remove_secret_from_config", "Move secret material to the credential store and keep it out of effective config.", key, source)
    if "permissions" in reason or "sandbox" in reason or "guards" in reason:
        return ConfigRequiredAction("explicit_permission_approval_required", "Request explicit approval before changing permissions or guards.", key, source)
    if "sensitive global memory" in reason:
        return ConfigRequiredAction("explicit_memory_scope_approval_required", "Explicitly allow sensitive global memory before using it in miniagent scope.", key, source)
    if "full context" in reason:
        return ConfigRequiredAction("use_reduced_context", "Provide reduced context unless full context is explicitly justified and approved.", key, source)
    if "estimated data" in reason:
        return ConfigRequiredAction("provide_measured_evidence", "Keep the value labeled estimated or provide measured evidence.", key, source)
    return ConfigRequiredAction("user_action_required", reason, key, source)


def _copy_jsonish(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _safe_preview(value: Any) -> Any:
    if isinstance(value, str):
        return "<redacted>" if len(value) > 0 else ""
    if isinstance(value, Mapping):
        return {str(k): "<redacted>" if _is_secret_key(str(k).lower()) else _safe_preview(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_preview(item) for item in value[:5]]
    return value


def _effective_hash(values: Mapping[str, Any]) -> str:
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
