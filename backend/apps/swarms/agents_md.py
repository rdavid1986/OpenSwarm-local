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


MAX_AGENTS_MD_BYTES = 64_000
MAX_AGENTS_MD_CHARS = 32_000
MAX_AGENTS_MD_LINES = 800
MAX_AGENTS_MD_SECTIONS = 32


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def normalize_agents_md_content(content: str, *, max_chars: int = MAX_AGENTS_MD_CHARS) -> dict[str, Any]:
    """Normalize AGENTS.md text without interpreting it as executable state."""

    bounded = _as_text(content)[: max(int(max_chars or 0), 0) or MAX_AGENTS_MD_CHARS]
    raw_lines = bounded.splitlines()[:MAX_AGENTS_MD_LINES]
    normalized_lines = [line.rstrip() for line in raw_lines]
    normalized_content = "\n".join(normalized_lines).strip()

    return {
        "content": normalized_content,
        "line_count": len(normalized_lines),
        "char_count": len(normalized_content),
        "truncated": len(content) > len(normalized_content) or len(content.splitlines()) > len(normalized_lines),
    }


def parse_agents_md_sections(content: str) -> list[dict[str, Any]]:
    """Parse simple Markdown sections from AGENTS.md content."""

    normalized = normalize_agents_md_content(content)
    sections: list[dict[str, Any]] = []
    current_heading = "root"
    current_level = 0
    current_lines: list[str] = []

    def flush_section() -> None:
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        if not body and current_heading != "root":
            body = ""
        if body or current_heading != "root":
            sections.append(
                {
                    "heading": current_heading,
                    "level": current_level,
                    "content": body,
                    "line_count": len([line for line in current_lines if line.strip()]),
                }
            )
        current_lines = []

    for line in normalized["content"].splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            marker = stripped.split(" ", 1)[0]
            if marker and set(marker) == {"#"} and 1 <= len(marker) <= 6:
                flush_section()
                current_heading = stripped[len(marker) :].strip() or "untitled"
                current_level = len(marker)
                continue
        current_lines.append(line)

    flush_section()
    return sections[:MAX_AGENTS_MD_SECTIONS]


def read_agents_md_file(path: str | Path, root: str | Path) -> dict[str, Any]:
    """Read and parse one AGENTS.md file safely.

    This parser is bounded and local-only. It does not inject instructions into
    prompts, execute content, call models, or mutate repository state.
    """

    resolved_root = _as_path(root).resolve()
    resolved_path = _as_path(path).resolve()
    base = normalize_agents_md_discovery_result(resolved_path, resolved_root)

    if not _is_relative_to(resolved_path, resolved_root):
        return {
            **base,
            "ok": False,
            "reason": "outside_repo_root",
            "content_loaded": False,
            "parser_applied": False,
            "injection_ready": False,
        }

    if resolved_path.name not in AGENTS_MD_FILENAMES:
        return {
            **base,
            "ok": False,
            "reason": "not_agents_md_file",
            "content_loaded": False,
            "parser_applied": False,
            "injection_ready": False,
        }

    if not resolved_path.exists() or not resolved_path.is_file():
        return {
            **base,
            "ok": False,
            "reason": "file_missing",
            "content_loaded": False,
            "parser_applied": False,
            "injection_ready": False,
        }

    size_bytes = resolved_path.stat().st_size
    if size_bytes > MAX_AGENTS_MD_BYTES:
        return {
            **base,
            "ok": False,
            "reason": "file_too_large",
            "size_bytes": size_bytes,
            "content_loaded": False,
            "parser_applied": False,
            "injection_ready": False,
        }

    content = resolved_path.read_text(encoding="utf-8", errors="replace")
    normalized = normalize_agents_md_content(content)
    sections = parse_agents_md_sections(normalized["content"])

    return {
        **base,
        "ok": True,
        "reason": "parsed",
        "size_bytes": size_bytes,
        "content_loaded": True,
        "parser_applied": True,
        "injection_ready": False,
        "content": normalized["content"],
        "line_count": normalized["line_count"],
        "char_count": normalized["char_count"],
        "truncated": normalized["truncated"],
        "sections": sections,
        "section_count": len(sections),
    }


def parse_discovered_agents_md_files(discovery: dict[str, Any], root: str | Path) -> dict[str, Any]:
    """Parse files returned by discover_agents_md_files without prompt injection."""

    discovered = discovery.get("found") if isinstance(discovery, dict) else []
    parsed = [
        read_agents_md_file(_as_path(root) / _as_text(item.get("path")), root)
        for item in discovered
        if isinstance(item, dict)
    ]

    return {
        "repo_root": _as_path(root).resolve().as_posix(),
        "parsed": parsed,
        "count": len(parsed),
        "ok": all(item.get("ok") for item in parsed) if parsed else True,
        "reason": "parse_complete",
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
