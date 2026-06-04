"""IDE theme compatibility contracts.

This package contains side-effect-free contracts for reviewable IDE theme/profile
candidates. It must not apply themes, install extensions, copy assets, or mutate
settings.
"""

from .ide_theme_candidates import (
    IDEThemeCandidate,
    IDEThemeDiagnosticReport,
    IDEThemeSourceAdapter,
    build_ide_theme_candidate,
    build_ide_theme_diagnostic_report,
    build_ide_theme_source_adapter,
)

__all__ = [
    "IDEThemeCandidate",
    "IDEThemeDiagnosticReport",
    "IDEThemeSourceAdapter",
    "build_ide_theme_candidate",
    "build_ide_theme_diagnostic_report",
    "build_ide_theme_source_adapter",
]

from .api import theme_compat
