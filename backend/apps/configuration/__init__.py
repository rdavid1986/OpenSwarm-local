"""Configuration taxonomy and resolver contracts."""

from backend.apps.configuration.models import GlobalUserConfig, default_global_config, sanitize_global_config_payload
from backend.apps.configuration.resolver import ConfigurationResolution, resolve_effective_config
from backend.apps.configuration.taxonomy import (
    ConfigConflict,
    ConfigRequiredAction,
    ConfigSafetyNote,
    ConfigScope,
    ConfigSource,
    ConfigurationScopeMatrix,
    ConfigurationScopeRule,
    EffectiveConfig,
    build_configuration_scope_matrix,
)

__all__ = [
    "ConfigConflict",
    "ConfigRequiredAction",
    "GlobalUserConfig",
    "ConfigSafetyNote",
    "ConfigScope",
    "ConfigSource",
    "ConfigurationResolution",
    "ConfigurationScopeMatrix",
    "ConfigurationScopeRule",
    "EffectiveConfig",
    "build_configuration_scope_matrix",
    "default_global_config",
    "resolve_effective_config",
    "sanitize_global_config_payload",
]
