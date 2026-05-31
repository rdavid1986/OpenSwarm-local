"""Prepared repo/zip/folder ingestion guard for skill import preview.

This module never reads paths, extracts archives, clones repositories, executes
source material, installs skills, activates tools, or activates MCP. It only
validates caller-provided `files[]` payloads before preview normalization.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

MAX_PREPARED_FILE_COUNT = 80
MAX_PREPARED_FILE_BYTES = 64_000
MAX_PREPARED_TOTAL_BYTES = 256_000

_ALLOWED_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
}
_ALLOWED_FILENAMES = {
    "agents.md",
    "skill.md",
    "readme.md",
    "copilot-instructions.md",
}
_BLOCKED_PATH_PARTS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
}
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[a-zA-Z]:/")


def _as_files(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    files = input_data.get("files") if isinstance(input_data, dict) else []
    return [item for item in files if isinstance(item, dict)] if isinstance(files, list) else []


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _normalize_path(file: dict[str, Any]) -> str:
    raw = _text(file.get("path") or file.get("name") or "unnamed")
    return raw.replace("\\", "/").strip()


def _is_unsafe_path(path: str) -> str | None:
    normalized = path.replace("\\", "/").strip()
    lowered = normalized.lower()
    parts = [part for part in lowered.split("/") if part]
    if not normalized:
        return "empty_path"
    if "\x00" in normalized:
        return "null_byte_path"
    if normalized.startswith("/") or _WINDOWS_ABSOLUTE_RE.match(normalized):
        return "absolute_path"
    if any(part == ".." for part in parts):
        return "path_traversal"
    if any(part in _BLOCKED_PATH_PARTS for part in parts):
        return "blocked_path_segment"
    if normalized.startswith("~"):
        return "home_path"
    return None


def _extension_status(path: str) -> str | None:
    name = PurePosixPath(path.lower()).name
    suffix = PurePosixPath(path.lower()).suffix
    if name in _ALLOWED_FILENAMES:
        return None
    if suffix in _ALLOWED_EXTENSIONS:
        return None
    return "unsupported_extension"


def _content(file: dict[str, Any]) -> str:
    content = file.get("content")
    return content if isinstance(content, str) else ""


def _size_bytes(file: dict[str, Any]) -> int:
    explicit = file.get("size_bytes")
    if isinstance(explicit, (int, float)) and explicit >= 0:
        return int(explicit)
    return len(_content(file).encode("utf-8", errors="ignore"))


def _binary_status(file: dict[str, Any], content: str) -> str | None:
    if file.get("binary") is True:
        return "binary_file"
    encoding = _text(file.get("encoding")).lower()
    if encoding in {"base64", "binary"}:
        return "binary_encoding"
    mime = _text(file.get("mime_type")).lower()
    if mime and not (
        mime.startswith("text/")
        or mime in {"application/json", "application/yaml", "application/x-yaml", "application/toml"}
    ):
        return "binary_mime_type"
    if "\x00" in content:
        return "binary_content"
    return None


def _reject(path: str, code: str, message: str, severity: str = "high") -> dict[str, Any]:
    return {
        "path": path or "unknown",
        "code": code,
        "message": message,
        "severity": severity,
    }


def _inspect_prepared_files(input_data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str], int]:
    accepted: list[dict[str, Any]] = []
    sanitized: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    warnings: list[str] = []
    total_bytes = 0

    files = _as_files(input_data)
    if len(files) > MAX_PREPARED_FILE_COUNT:
        rejected.append(_reject(
            "files[]",
            "prepared_file_count_exceeded",
            f"Prepared file count exceeds limit {MAX_PREPARED_FILE_COUNT}.",
            "critical",
        ))

    for file in files[:MAX_PREPARED_FILE_COUNT]:
        path = _normalize_path(file)
        content = _content(file)
        size = _size_bytes(file)
        total_bytes += size

        path_issue = _is_unsafe_path(path)
        ext_issue = _extension_status(path)
        binary_issue = _binary_status(file, content)

        if path_issue:
            rejected.append(_reject(path, path_issue, "Unsafe prepared file path rejected.", "critical"))
            continue
        if ext_issue:
            rejected.append(_reject(path, ext_issue, "Prepared file extension is not allowed for skill import preview.", "high"))
            continue
        if binary_issue:
            rejected.append(_reject(path, binary_issue, "Binary prepared file rejected from skill import preview.", "high"))
            continue
        if size > MAX_PREPARED_FILE_BYTES:
            rejected.append(_reject(path, "prepared_file_too_large", f"Prepared file exceeds {MAX_PREPARED_FILE_BYTES} bytes.", "high"))
            continue
        if not content:
            warnings.append(f"{path}:content_missing")
            continue

        accepted.append({
            "path": path,
            "name": PurePosixPath(path).name,
            "size_bytes": size,
            "role": _text(file.get("role"), "prepared_preview_file"),
        })
        sanitized.append({
            "path": path,
            "name": PurePosixPath(path).name,
            "content": content,
            "size_bytes": size,
            "role": _text(file.get("role"), "prepared_preview_file"),
        })

    if total_bytes > MAX_PREPARED_TOTAL_BYTES:
        rejected.append(_reject(
            "files[]",
            "prepared_total_size_exceeded",
            f"Prepared file total size exceeds {MAX_PREPARED_TOTAL_BYTES} bytes.",
            "critical",
        ))

    return accepted, sanitized, rejected, warnings, total_bytes


def build_prepared_skill_import_ingestion_guard(input_data: dict[str, Any]) -> dict[str, Any]:
    accepted, _sanitized, rejected, warnings, total_bytes = _inspect_prepared_files(input_data or {})
    files = _as_files(input_data or {})

    if not files:
        status = "not_applicable"
    elif any(item.get("severity") in {"critical", "high"} for item in rejected):
        status = "blocked"
    elif warnings or rejected:
        status = "needs_review"
    else:
        status = "allowed_preview"

    return {
        "guard_kind": "prepared_skill_import_ingestion_guard",
        "status": status,
        "prepared_file_count": len(files),
        "accepted_file_count": len(accepted),
        "rejected_file_count": len(rejected),
        "prepared_total_bytes": total_bytes,
        "accepted_files": accepted,
        "rejected_files": rejected,
        "warnings": warnings,
        "limits": {
            "max_prepared_file_count": MAX_PREPARED_FILE_COUNT,
            "max_prepared_file_bytes": MAX_PREPARED_FILE_BYTES,
            "max_prepared_total_bytes": MAX_PREPARED_TOTAL_BYTES,
            "allowed_extensions": sorted(_ALLOWED_EXTENSIONS),
            "allowed_filenames": sorted(_ALLOWED_FILENAMES),
        },
        "preview_only": True,
        "read_external_paths": False,
        "extracted_archives": False,
        "cloned_repositories": False,
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }


def sanitize_prepared_skill_import_files(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    _accepted, sanitized, _rejected, _warnings, _total_bytes = _inspect_prepared_files(input_data or {})
    return sanitized
