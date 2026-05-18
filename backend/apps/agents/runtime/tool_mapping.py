"""Tool-call name/input mapping for local provider compatibility.

This module normalizes legacy/local tool names (notably the current Ollama
inline loop vocabulary) into ToolRuntime `ToolCall` contracts. It does not
execute tools.
"""

from __future__ import annotations

from typing import Any

from backend.apps.agents.runtime.tools import ToolCall


LEGACY_TOOL_NAME_MAP: dict[str, str] = {
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "search_files": "SearchFiles",
    "search_text": "SearchText",
    "list_files": "Glob",
    "Read": "Read",
    "Write": "Write",
    "Edit": "Edit",
    "Glob": "Glob",
    "Grep": "Grep",
    "SearchFiles": "SearchFiles",
    "SearchText": "SearchText",
}


def normalize_tool_name(name: str) -> str:
    """Return the normalized ToolRuntime name for a local/provider tool name."""
    raw = str(name or "").strip()
    return LEGACY_TOOL_NAME_MAP.get(raw, raw)


def normalize_tool_input(name: str, tool_input: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize input keys without changing semantics.

    Ollama/local `search_text` already uses `query`; `search_files` already
    uses `pattern`. Glob/Grep accept both pattern/query at ToolRuntime level,
    so this stays intentionally small.
    """
    if not isinstance(tool_input, dict):
        raise ValueError("tool input must be an object")
    normalized = dict(tool_input)
    normalized_name = normalize_tool_name(name)

    if normalized_name in {"Read", "Write", "Edit", "SearchFiles", "SearchText", "Glob", "Grep"}:
        if "path" not in normalized:
            if "file_path" in normalized:
                normalized["path"] = normalized["file_path"]
            elif "filepath" in normalized:
                normalized["path"] = normalized["filepath"]
            elif "filePath" in normalized:
                normalized["path"] = normalized["filePath"]

    if normalized_name == "SearchFiles" and "pattern" not in normalized and "query" in normalized:
        normalized["pattern"] = normalized["query"]
    if normalized_name == "SearchText" and "query" not in normalized and "pattern" in normalized:
        normalized["query"] = normalized["pattern"]
    return normalized


def map_tool_call(
    name: str,
    tool_input: dict[str, Any] | None,
    *,
    call_id: str | None = None,
    provider_call_id: str | None = None,
) -> ToolCall:
    """Convert a legacy/local provider call into a normalized ToolCall."""
    raw_name = str(name or "").strip()
    normalized_name = normalize_tool_name(raw_name)
    normalized_input = normalize_tool_input(raw_name, tool_input)
    kwargs: dict[str, Any] = {
        "name": normalized_name,
        "input": normalized_input,
        "provider_call_id": provider_call_id,
        "raw_name": raw_name,
    }
    if call_id:
        kwargs["id"] = call_id
    return ToolCall(**kwargs)
