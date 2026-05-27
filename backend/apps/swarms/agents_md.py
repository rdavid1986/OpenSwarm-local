"""Side-effect-free AGENTS.md discovery helpers.

AGENTS-MD.1 discovers repository instruction files without parsing or injecting
their content. Callers provide a repository path; this module only walks the
filesystem, normalizes metadata, and applies conservative ignore rules.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


AGENTS_MD_FILENAMES = {"AGENTS.md", "agents.md"}
DEFAULT_DISCOVERY_EXCLUDES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
    "coverage",
}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_path(value: str | Path | None) -> Path:
    return value if isinstance(value, Path) else Path(_as_text(value) or ".")


def _safe_relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except Exception:
        return path.as_posix()


def should_skip_agents_md_discovery_dir(path: Path, *, extra_excludes: set[str] | None = None) -> bool:
    """Return True when a directory should not be walked during discovery."""

    excludes = set(DEFAULT_DISCOVERY_EXCLUDES)
    if extra_excludes:
        excludes.update(extra_excludes)
    return path.name in excludes


def normalize_agents_md_discovery_result(path: Path, root: Path) -> dict[str, Any]:
    """Normalize one discovered AGENTS.md path without reading file content."""

    resolved_root = root.resolve()
    resolved_path = path.resolve()
    relative_path = _safe_relative_path(resolved_path, resolved_root)
    parent_relative = _safe_relative_path(resolved_path.parent, resolved_root)
    scope_path = "." if parent_relative in {"", "."} else parent_relative

    return {
        "path": relative_path,
        "filename": resolved_path.name,
        "scope_path": scope_path,
        "depth": 0 if scope_path == "." else len(Path(scope_path).parts),
        "exists": resolved_path.exists(),
        "is_file": resolved_path.is_file(),
        "content_loaded": False,
        "parser_applied": False,
        "injection_ready": False,
    }


def discover_agents_md_files(
    repo_root: str | Path,
    *,
    max_results: int = 50,
    extra_excludes: set[str] | None = None,
) -> dict[str, Any]:
    """Discover AGENTS.md files under repo_root without reading their content."""

    root = _as_path(repo_root).resolve()
    results: list[dict[str, Any]] = []

    if not root.exists() or not root.is_dir():
        return {
            "repo_root": root.as_posix(),
            "found": [],
            "count": 0,
            "ok": False,
            "reason": "repo_root_missing",
        }

    limit = max(int(max_results or 0), 0) or 50

    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not should_skip_agents_md_discovery_dir(current_path / dirname, extra_excludes=extra_excludes)
        ]

        for filename in sorted(filenames):
            if filename not in AGENTS_MD_FILENAMES:
                continue
            results.append(normalize_agents_md_discovery_result(current_path / filename, root))
            if len(results) >= limit:
                return {
                    "repo_root": root.as_posix(),
                    "found": results,
                    "count": len(results),
                    "ok": True,
                    "reason": "max_results_reached",
                }

    results.sort(key=lambda item: (item["depth"], item["path"]))
    return {
        "repo_root": root.as_posix(),
        "found": results,
        "count": len(results),
        "ok": True,
        "reason": "discovery_complete",
    }
