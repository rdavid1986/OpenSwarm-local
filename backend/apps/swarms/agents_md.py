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


MAX_AGENTS_MD_CONTEXT_FILES = 8
MAX_AGENTS_MD_CONTEXT_CHARS = 12_000


def _normalize_scope_path(value: Any) -> str:
    text = _as_text(value).replace("\\", "/").strip("/")
    if text in {"", "."}:
        return "."
    return text


def _scope_applies_to_target(scope_path: str, target_path: str | None) -> bool:
    scope = _normalize_scope_path(scope_path)
    target = _normalize_scope_path(target_path or ".")
    if scope == ".":
        return True
    return target == scope or target.startswith(scope + "/")


def rank_agents_md_for_target(parsed_items: list[Any], *, target_path: str | None = None) -> list[dict[str, Any]]:
    """Rank parsed AGENTS.md files by scope relevance for a target path."""

    ranked: list[dict[str, Any]] = []
    for item in parsed_items:
        if not isinstance(item, dict) or not item.get("ok"):
            continue
        scope_path = _normalize_scope_path(item.get("scope_path"))
        if not _scope_applies_to_target(scope_path, target_path):
            continue
        ranked_item = dict(item)
        ranked_item["scope_path"] = scope_path
        ranked_item["applies_to_target"] = True
        ranked_item["scope_depth"] = 0 if scope_path == "." else len(Path(scope_path).parts)
        ranked.append(ranked_item)

    return sorted(ranked, key=lambda item: (item["scope_depth"], item.get("path") or ""))


def build_agents_md_context(
    parsed_policy: dict[str, Any] | None,
    *,
    target_path: str | None = None,
    max_files: int = MAX_AGENTS_MD_CONTEXT_FILES,
    max_chars: int = MAX_AGENTS_MD_CONTEXT_CHARS,
) -> dict[str, Any]:
    """Build scoped AGENTS.md context without injecting it into a model prompt.

    The returned payload is prompt-ready context metadata, but this helper does
    not call models, mutate state, authorize actions, or merge instructions into
    system prompts. Callers decide if and where this context is included.
    """

    parsed_items = parsed_policy.get("parsed") if isinstance(parsed_policy, dict) else []
    ranked = rank_agents_md_for_target(
        [item for item in parsed_items if isinstance(item, dict)],
        target_path=target_path,
    )

    file_limit = max(int(max_files or 0), 0) or MAX_AGENTS_MD_CONTEXT_FILES
    char_limit = max(int(max_chars or 0), 0) or MAX_AGENTS_MD_CONTEXT_CHARS
    selected: list[dict[str, Any]] = []
    used_chars = 0

    for item in ranked[:file_limit]:
        content = _as_text(item.get("content"))
        remaining = max(char_limit - used_chars, 0)
        if remaining <= 0:
            break

        selected_content = content[:remaining]
        used_chars += len(selected_content)
        selected.append(
            {
                "path": item.get("path"),
                "scope_path": item.get("scope_path"),
                "scope_depth": item.get("scope_depth"),
                "applies_to_target": True,
                "content": selected_content,
                "sections": item.get("sections") or [],
                "section_count": item.get("section_count") or 0,
                "char_count": len(selected_content),
                "truncated_for_context": len(selected_content) < len(content),
            }
        )

    return {
        "target_path": _normalize_scope_path(target_path or "."),
        "context_kind": "agents_md",
        "selected": selected,
        "selected_count": len(selected),
        "available_count": len(ranked),
        "context_chars": used_chars,
        "max_context_chars": char_limit,
        "injection_ready": True,
        "injected": False,
        "reason": "agents_md_context_built",
    }


def build_agents_md_context_sections(agents_md_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Convert scoped AGENTS.md context into state_context-compatible sections."""

    context = agents_md_context if isinstance(agents_md_context, dict) else {}
    sections: list[dict[str, Any]] = []

    for item in context.get("selected") or []:
        if not isinstance(item, dict):
            continue
        sections.append(
            {
                "kind": "agents_md",
                "source": item.get("path"),
                "scope_path": item.get("scope_path"),
                "content": item.get("content") or "",
                "metadata": {
                    "applies_to_target": item.get("applies_to_target") is True,
                    "scope_depth": item.get("scope_depth"),
                    "section_count": item.get("section_count") or 0,
                    "truncated_for_context": item.get("truncated_for_context") is True,
                },
            }
        )

    return sections


DANGEROUS_AGENTS_MD_TERMS = {
    "ignore previous instructions",
    "ignore all previous instructions",
    "bypass guard",
    "bypass guards",
    "disable guard",
    "disable guards",
    "skip approval",
    "without approval",
    "force push",
    "git push --force",
    "delete everything",
    "remove all files",
    "rm -rf",
    "format disk",
    "exfiltrate",
    "steal",
    "send secrets",
    "print secrets",
    "expose secrets",
    "leak secrets",
}


def _contains_dangerous_agents_md_term(content: str) -> list[str]:
    lowered = _as_text(content).lower()
    return sorted(term for term in DANGEROUS_AGENTS_MD_TERMS if term in lowered)


def _path_matches_scope(path: str, scope_path: str) -> bool:
    normalized_path = _normalize_scope_path(path)
    normalized_scope = _normalize_scope_path(scope_path)
    if normalized_scope == ".":
        return True
    return normalized_path == normalized_scope or normalized_path.startswith(normalized_scope + "/")


def evaluate_agents_md_guard(
    agents_md_context: dict[str, Any] | None,
    *,
    forbidden_files: list[Any] | None = None,
) -> dict[str, Any]:
    """Evaluate AGENTS.md context before any prompt injection.

    This guard is advisory and fail-closed for injection. It does not authorize
    filesystem writes, tool calls, commits, pushes, or guard bypasses.
    """

    context = agents_md_context if isinstance(agents_md_context, dict) else {}
    selected = [item for item in context.get("selected") or [] if isinstance(item, dict)]
    forbidden = [_normalize_scope_path(item) for item in (forbidden_files or []) if _as_text(item)]

    reasons: list[dict[str, Any]] = []
    risk_level = "low"

    def add_reason(code: str, message: str, *, severity: str = "medium", source: Any | None = None) -> None:
        nonlocal risk_level
        if severity == "high":
            risk_level = "high"
        elif severity == "medium" and risk_level == "low":
            risk_level = "medium"
        reasons.append(
            {
                "code": code,
                "message": message,
                "severity": severity,
                "source": source,
            }
        )

    for item in selected:
        dangerous_terms = _contains_dangerous_agents_md_term(_as_text(item.get("content")))
        if dangerous_terms:
            add_reason(
                "dangerous_instruction_detected",
                "AGENTS.md contains instructions that appear to bypass guards, approvals, or secrets policy.",
                severity="high",
                source={
                    "path": item.get("path"),
                    "scope_path": item.get("scope_path"),
                    "terms": dangerous_terms,
                },
            )

        scope_path = _normalize_scope_path(item.get("scope_path"))
        conflicting_forbidden = [path for path in forbidden if _path_matches_scope(path, scope_path)]
        if conflicting_forbidden:
            add_reason(
                "forbidden_scope_overlap",
                "AGENTS.md scope overlaps forbidden files. It cannot authorize access to those files.",
                severity="high",
                source={
                    "path": item.get("path"),
                    "scope_path": scope_path,
                    "forbidden_files": conflicting_forbidden,
                },
            )

    guard_status = "allowed" if risk_level == "low" else "blocked"
    return {
        "guard_status": guard_status,
        "risk_level": risk_level,
        "allowed_to_inject": guard_status == "allowed",
        "reason_count": len(reasons),
        "reasons": reasons,
        "injection_authorizes_actions": False,
        "actions_still_require_runtime_guards": True,
    }


def apply_agents_md_guard(
    agents_md_context: dict[str, Any] | None,
    *,
    forbidden_files: list[Any] | None = None,
) -> dict[str, Any]:
    """Attach guard evaluation to scoped AGENTS.md context."""

    context = dict(agents_md_context) if isinstance(agents_md_context, dict) else {}
    guard = evaluate_agents_md_guard(context, forbidden_files=forbidden_files)
    context["guard"] = guard
    context["injection_ready"] = bool(context.get("injection_ready")) and guard["allowed_to_inject"]
    context["injected"] = False
    return context


def build_guarded_agents_md_context_sections(
    agents_md_context: dict[str, Any] | None,
    *,
    forbidden_files: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Build state_context sections only when AGENTS.md guard allows injection."""

    guarded = apply_agents_md_guard(agents_md_context, forbidden_files=forbidden_files)
    guard = guarded.get("guard") if isinstance(guarded.get("guard"), dict) else {}
    if not guard.get("allowed_to_inject"):
        return []

    sections = build_agents_md_context_sections(guarded)
    for section in sections:
        metadata = section.setdefault("metadata", {})
        metadata["agents_md_guard_status"] = guard.get("guard_status")
        metadata["agents_md_risk_level"] = guard.get("risk_level")
        metadata["injection_authorizes_actions"] = False
    return sections


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
