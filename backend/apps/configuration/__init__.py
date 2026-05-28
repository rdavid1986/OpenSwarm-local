"""Configuration taxonomy and resolver contracts."""

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
    "ConfigSafetyNote",
    "ConfigScope",
    "ConfigSource",
    "ConfigurationResolution",
    "ConfigurationScopeMatrix",
    "ConfigurationScopeRule",
    "EffectiveConfig",
    "build_configuration_scope_matrix",
    "resolve_effective_config",
]
