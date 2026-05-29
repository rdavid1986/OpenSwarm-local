"""Read-only SkillSpecCandidate requirements contract mapping.

This module only compares declared SkillSpecCandidate requirements with
available snapshots of tools/actions and modes. It never activates tools or
MCP servers, changes permissions, updates modes, approves candidates, or
installs skills.
"""

from __future__ import annotations

import re
from typing import Any

from backend.apps.modes.models import Mode
from backend.apps.skills.models import SkillSpecCandidate
from backend.apps.tools_lib.models import BuiltinTool, ToolDefinition


PermissionState = str


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, (int, float, bool)):
            result.append(str(item))
    return result


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _server_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    return str(value)


def _builtin_index(builtin_tools: list[BuiltinTool]) -> dict[str, BuiltinTool]:
    index: dict[str, BuiltinTool] = {}
    for tool in builtin_tools:
        index[_norm(tool.name)] = tool
    return index


def _custom_index(tools: list[ToolDefinition]) -> dict[str, ToolDefinition]:
    index: dict[str, ToolDefinition] = {}
    for tool in tools:
        index[_norm(tool.name)] = tool
        index[_norm(tool.id)] = tool
        server = _server_name(tool.name)
        if server:
            index[server] = tool
        configured_server = tool.mcp_config.get("server_name") or tool.mcp_config.get("name")
        if configured_server:
            index[_norm(configured_server)] = tool
            index[_server_name(str(configured_server))] = tool
    return index


def _tool_contract(
    declared_name: str,
    builtin_tools: dict[str, BuiltinTool],
    custom_tools: dict[str, ToolDefinition],
    builtin_permissions: dict[str, str],
) -> dict[str, Any]:
    normalized = _norm(declared_name)
    builtin = builtin_tools.get(normalized)
    custom = custom_tools.get(normalized)

    notes = ["Declared requirement only; this does not grant permission."]
    if builtin:
        permission = builtin_permissions.get(builtin.name, "ask")
        source = "builtin"
        known: bool | str = True
        if permission == "deny":
            notes.append("Builtin tool permission is deny.")
        elif permission == "ask":
            notes.append("Builtin tool requires runtime approval.")
    elif custom:
        permission = "unknown"
        source = "mcp" if custom.mcp_config else "custom"
        known = True
        if custom.enabled is False:
            notes.append("Persisted tool is disabled.")
        notes.append("Persisted custom/MCP top-level permission is not inferred here.")
    else:
        permission = "not_found"
        source = "unknown"
        known = False
        notes.append("No matching builtin, custom, or MCP tool was found in the read-only snapshot.")

    return {
        "name": declared_name,
        "declared": True,
        "known": known,
        "permission": permission,
        "source": source,
        "notes": notes,
    }


def _mcp_contract(declared_name: str, custom_tools: dict[str, ToolDefinition]) -> dict[str, Any]:
    normalized = _norm(declared_name)
    server_key = _server_name(declared_name)
    tool = custom_tools.get(normalized) or custom_tools.get(server_key)
    notes = ["Declared MCP requirement only; this does not activate MCP."]

    if not tool or not tool.mcp_config:
        return {
            "name": declared_name,
            "declared": True,
            "known": False,
            "activation_state": "not_found",
            "notes": notes + ["No matching persisted MCP server configuration was found."],
        }

    activation_state = "unknown"
    if tool.enabled is False:
        activation_state = "inactive"
        notes.append("Persisted MCP tool is disabled.")
    elif tool.auth_status in {"expired", "error"}:
        activation_state = "blocked"
        notes.append(f"Auth status is {tool.auth_status}.")
    else:
        notes.append("Persisted MCP config exists; runtime activation state is not checked here.")

    return {
        "name": declared_name,
        "declared": True,
        "known": True,
        "activation_state": activation_state,
        "notes": notes,
    }


def _mode_contract(mode: Mode, required_tools: list[str]) -> dict[str, Any]:
    mode_tools = mode.tools
    if mode_tools is None:
        mentions: bool | str = "unknown"
        policy = "all_actions"
        notes = ["Mode allows all actions; explicit required-tool mentions are not enumerated."]
    else:
        normalized_tools = {_norm(tool) for tool in mode_tools}
        mentions = any(_norm(tool) in normalized_tools for tool in required_tools)
        policy = "specific_actions"
        notes = []
        if not mentions and required_tools:
            notes.append("Mode does not explicitly list declared required tools.")

    return {
        "mode_id": mode.id,
        "name": mode.name,
        "mentions_required_tools": mentions,
        "allowed_tools_policy": policy,
        "notes": notes,
    }


def build_skill_candidate_requirements_contract(
    candidate: SkillSpecCandidate,
    *,
    tools: list[ToolDefinition] | None = None,
    builtin_tools: list[BuiltinTool] | None = None,
    builtin_permissions: dict[str, str] | None = None,
    modes: list[Mode] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSON-safe read-only requirements contract for a candidate."""

    spec = candidate.skill_spec
    tools = tools or []
    builtin_tools = builtin_tools or []
    builtin_permissions = builtin_permissions or {}
    modes = modes or []
    warnings = list(warnings or [])

    requirements = {
        "required_tools": _as_list(getattr(spec, "required_tools", [])),
        "required_mcp_servers": _as_list(getattr(spec, "required_mcp_servers", [])),
        "compatible_providers": _as_list(getattr(spec, "compatible_providers", [])),
        "tested_models": _as_list(getattr(spec, "tested_models", [])),
        "recommended_models": _as_list(getattr(spec, "recommended_models", [])),
        "unsupported_models": _as_list(getattr(spec, "unsupported_models", [])),
    }

    builtin_by_name = _builtin_index(builtin_tools)
    custom_by_name = _custom_index(tools)

    tool_rows = [
        _tool_contract(name, builtin_by_name, custom_by_name, builtin_permissions)
        for name in requirements["required_tools"]
    ]
    mcp_rows = [
        _mcp_contract(name, custom_by_name)
        for name in requirements["required_mcp_servers"]
    ]
    mode_rows = [_mode_contract(mode, requirements["required_tools"]) for mode in modes]

    known_tool_count = sum(1 for row in tool_rows if row["known"] is True)
    missing_tool_count = sum(1 for row in tool_rows if row["known"] is False or row["permission"] == "not_found")
    known_mcp_count = sum(1 for row in mcp_rows if row["known"] is True)
    missing_mcp_count = sum(1 for row in mcp_rows if row["known"] is False or row["activation_state"] == "not_found")
    blocked_count = (
        sum(1 for row in tool_rows if row["permission"] == "deny")
        + sum(1 for row in mcp_rows if row["activation_state"] in {"blocked", "inactive"})
    )
    unknown_count = (
        sum(1 for row in tool_rows if row["permission"] == "unknown" or row["known"] == "unknown")
        + sum(1 for row in mcp_rows if row["activation_state"] == "unknown" or row["known"] == "unknown")
        + sum(1 for row in mode_rows if row["mentions_required_tools"] == "unknown")
    )

    if not requirements["required_tools"] and not requirements["required_mcp_servers"]:
        warnings.append("No required tools or MCP servers declared by this candidate.")

    contract = {
        "contract_kind": "skill_candidate_requirements_contract",
        "candidate_id": candidate.candidate_id,
        "candidate_status": candidate.status,
        "install_approved": candidate.install_approved,
        "requirements": requirements,
        "tools": tool_rows,
        "mcp_servers": mcp_rows,
        "modes": mode_rows,
        "summary": {
            "declared_tool_count": len(requirements["required_tools"]),
            "known_tool_count": known_tool_count,
            "missing_tool_count": missing_tool_count,
            "declared_mcp_count": len(requirements["required_mcp_servers"]),
            "known_mcp_count": known_mcp_count,
            "missing_mcp_count": missing_mcp_count,
            "blocked_count": blocked_count,
            "unknown_count": unknown_count,
        },
        "warnings": warnings,
    }
    return _json_safe(contract)
