"""Side-effect-free MCP host/client/server contracts for OpenSwarm.

This module does not start MCP servers, call providers, execute tools, mutate
sessions, write files, or change agent_manager.py dispatch behavior.
"""

from __future__ import annotations

import re
from typing import Any


VALID_MCP_TRANSPORTS = {"stdio", "sse", "http", "streamable_http", "unknown"}
VALID_MCP_AUTH_STATUSES = {"none", "configured", "connected", "expired", "error", "unknown"}
VALID_MCP_GATE_STATES = {"inactive", "active", "blocked", "unavailable", "unknown"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def sanitize_mcp_server_name(value: Any) -> str:
    """Normalize a tool/server name into the MCP server slug used by dispatch."""

    text = _as_text(value).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def normalize_mcp_transport(value: Any) -> str:
    """Normalize supported MCP transport names without opening transports."""

    transport = _as_text(value).lower()
    if transport in {"streamable-http", "streamable http"}:
        transport = "streamable_http"
    return transport if transport in VALID_MCP_TRANSPORTS else "unknown"


def normalize_mcp_auth_status(value: Any) -> str:
    """Normalize auth status values from ToolDefinition-like records."""

    status = _as_text(value).lower()
    return status if status in VALID_MCP_AUTH_STATUSES else "unknown"


def normalize_mcp_permission(value: Any) -> str:
    """Normalize per-tool permission policy."""

    policy = _as_text(value).lower()
    return policy if policy in {"always_allow", "ask", "deny"} else "ask"


def normalize_mcp_tool_permissions(value: Any) -> dict[str, str]:
    """Normalize sub-tool permissions without evaluating runtime access."""

    raw = _as_dict(value)
    return {
        _as_text(name): normalize_mcp_permission(policy)
        for name, policy in raw.items()
        if _as_text(name)
    }


def build_mcp_server_contract(
    *,
    server_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    mcp_config: dict[str, Any] | None = None,
    enabled: bool | None = None,
    auth_status: str | None = None,
    tool_permissions: dict[str, Any] | None = None,
    connected_account_email: str | None = None,
    active: bool | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized MCP server contract without starting the server."""

    config = _as_dict(mcp_config)
    display_name = _as_text(name) or _as_text(server_id) or "unknown"
    slug = sanitize_mcp_server_name(display_name)
    config_type = normalize_mcp_transport(config.get("type") or config.get("transport"))
    command = _as_text(config.get("command"))
    args = [_as_text(item) for item in _as_list(config.get("args")) if _as_text(item)]
    url = _as_text(config.get("url") or config.get("remoteUrl"))
    env = _as_dict(config.get("env"))

    resolved_enabled = True if enabled is None else bool(enabled)
    resolved_auth = normalize_mcp_auth_status(auth_status)
    permissions = normalize_mcp_tool_permissions(tool_permissions)
    denied_tools = sorted(name for name, policy in permissions.items() if policy == "deny")
    allowed_tools = sorted(name for name, policy in permissions.items() if policy != "deny")

    if not resolved_enabled:
        gate_state = "unavailable"
    elif bool(active):
        gate_state = "active"
    elif resolved_auth in {"configured", "connected", "none"}:
        gate_state = "inactive"
    else:
        gate_state = "blocked"

    return {
        "contract_kind": "mcp_server",
        "server_id": _as_text(server_id) or slug,
        "name": display_name,
        "server_name": slug,
        "description": _as_text(description),
        "enabled": resolved_enabled,
        "active": bool(active),
        "gate_state": gate_state,
        "auth_status": resolved_auth,
        "transport": config_type,
        "command": command,
        "args": args,
        "url": url,
        "env_keys": sorted(str(key) for key in env.keys()),
        "tool_permissions": permissions,
        "allowed_tool_names": allowed_tools,
        "denied_tool_names": denied_tools,
        "connected_account_email": _as_text(connected_account_email) or None,
        "source": _as_text(source) or "tool_definition",
        "metadata": _as_dict(metadata),
        "requires_activation": gate_state == "inactive",
        "requires_user_approval": gate_state == "inactive",
        "callable_now": gate_state == "active",
        "executed": False,
        "execution_result": None,
    }


def build_mcp_client_contract(
    *,
    client_id: str | None = None,
    session_id: str | None = None,
    allowed_tools: list[Any] | None = None,
    active_mcps: list[Any] | None = None,
    provider: str | None = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized MCP client/session contract without mutating session."""

    allowed = [_as_text(item) for item in _as_list(allowed_tools) if _as_text(item)]
    active = [sanitize_mcp_server_name(item) for item in _as_list(active_mcps) if sanitize_mcp_server_name(item)]

    return {
        "contract_kind": "mcp_client",
        "client_id": _as_text(client_id) or None,
        "session_id": _as_text(session_id) or None,
        "allowed_tools": allowed,
        "active_mcps": active,
        "provider": _as_text(provider) or None,
        "model": _as_text(model) or None,
        "activation_required_for_unlisted_servers": True,
        "activation_tool_names": ["MCPList", "MCPSearch", "MCPActivate"],
        "child_sessions_inherit_active_mcps": False,
        "metadata": _as_dict(metadata),
        "executed": False,
        "execution_result": None,
    }


def build_mcp_host_contract(
    *,
    host_id: str | None = None,
    host_name: str | None = None,
    servers: list[Any] | None = None,
    client: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build MCP host contract from server/client contracts without dispatch."""

    normalized_servers = [
        build_mcp_server_contract(**item) if isinstance(item, dict) and item.get("contract_kind") != "mcp_server" else item
        for item in _as_list(servers)
        if isinstance(item, dict)
    ]
    normalized_client = _as_dict(client)

    active_servers = [item for item in normalized_servers if _as_dict(item).get("gate_state") == "active"]
    inactive_servers = [item for item in normalized_servers if _as_dict(item).get("gate_state") == "inactive"]
    blocked_servers = [item for item in normalized_servers if _as_dict(item).get("gate_state") in {"blocked", "unavailable"}]

    return {
        "contract_kind": "mcp_host",
        "host_id": _as_text(host_id) or None,
        "host_name": _as_text(host_name) or "openswarm",
        "client": normalized_client or None,
        "servers": normalized_servers,
        "server_count": len(normalized_servers),
        "active_server_count": len(active_servers),
        "inactive_server_count": len(inactive_servers),
        "blocked_server_count": len(blocked_servers),
        "activation_gate": {
            "required": True,
            "discovery_tools": ["MCPList", "MCPSearch"],
            "activation_tool": "MCPActivate",
            "active_mcps_filter_required": True,
            "user_approval_required": True,
        },
        "metadata": _as_dict(metadata),
        "executed": False,
        "execution_result": None,
    }


def build_mcp_contract_from_tool_definition(
    tool: Any,
    *,
    active_mcps: list[Any] | None = None,
) -> dict[str, Any]:
    """Build a server contract from a ToolDefinition-like dict or object."""

    if hasattr(tool, "model_dump"):
        data = tool.model_dump(mode="json")
    elif isinstance(tool, dict):
        data = tool
    else:
        data = {
            "id": getattr(tool, "id", None),
            "name": getattr(tool, "name", None),
            "description": getattr(tool, "description", None),
            "mcp_config": getattr(tool, "mcp_config", None),
            "enabled": getattr(tool, "enabled", None),
            "auth_status": getattr(tool, "auth_status", None),
            "tool_permissions": getattr(tool, "tool_permissions", None),
            "connected_account_email": getattr(tool, "connected_account_email", None),
        }

    slug = sanitize_mcp_server_name(data.get("name"))
    active_set = {sanitize_mcp_server_name(item) for item in _as_list(active_mcps)}

    return build_mcp_server_contract(
        server_id=data.get("id"),
        name=data.get("name"),
        description=data.get("description"),
        mcp_config=data.get("mcp_config"),
        enabled=data.get("enabled"),
        auth_status=data.get("auth_status"),
        tool_permissions=data.get("tool_permissions"),
        connected_account_email=data.get("connected_account_email"),
        active=slug in active_set,
        source="tool_definition",
    )


def summarize_mcp_host_contract(contract: dict[str, Any] | None) -> str:
    """Return compact summary for prompts and audit logs."""

    data = _as_dict(contract)
    return (
        "MCP Host: "
        f"servers={data.get('server_count', 0)}; "
        f"active={data.get('active_server_count', 0)}; "
        f"inactive={data.get('inactive_server_count', 0)}; "
        f"blocked={data.get('blocked_server_count', 0)}; "
        "activation_gate=required; "
        "executed=False"
    )


def build_mcp_tool_registry(
    *,
    tools: list[Any] | None = None,
    active_mcps: list[Any] | None = None,
    allowed_tools: list[Any] | None = None,
    registry_servers: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a side-effect-free MCP registry view from local tool records.

    This does not read files, call network registry endpoints, activate servers,
    derive runtime configs, refresh OAuth, or mutate sessions.
    """

    active_set = {sanitize_mcp_server_name(item) for item in _as_list(active_mcps)}
    allowed_set = {_as_text(item) for item in _as_list(allowed_tools) if _as_text(item)}

    local_servers: list[dict[str, Any]] = []
    for tool in _as_list(tools):
        server = build_mcp_contract_from_tool_definition(tool, active_mcps=list(active_set))
        tool_ref = f"mcp:{server['name']}"
        slug_ref = f"mcp:{server['server_name']}"
        server["allowed_by_client"] = not allowed_set or tool_ref in allowed_set or slug_ref in allowed_set
        local_servers.append(server)

    remote_candidates: list[dict[str, Any]] = []
    for item in _as_list(registry_servers):
        raw = _as_dict(item)
        if not raw:
            continue
        remote_candidates.append({
            "contract_kind": "mcp_registry_candidate",
            "name": _as_text(raw.get("name")),
            "server_name": sanitize_mcp_server_name(raw.get("name")),
            "title": _as_text(raw.get("title")),
            "description": _as_text(raw.get("description")),
            "source": _as_text(raw.get("source")) or "registry",
            "remote_url": _as_text(raw.get("remoteUrl") or raw.get("remote_url")),
            "repository_url": _as_text(raw.get("repositoryUrl") or raw.get("repository_url")),
            "keywords": [_as_text(value) for value in _as_list(raw.get("keywords")) if _as_text(value)],
            "installed": False,
            "active": False,
            "callable_now": False,
            "executed": False,
            "execution_result": None,
        })

    active_servers = [item for item in local_servers if item.get("gate_state") == "active"]
    inactive_servers = [item for item in local_servers if item.get("gate_state") == "inactive"]
    blocked_servers = [item for item in local_servers if item.get("gate_state") in {"blocked", "unavailable"}]
    client_blocked_servers = [item for item in local_servers if item.get("allowed_by_client") is False]

    return {
        "contract_kind": "mcp_tool_registry",
        "servers": local_servers,
        "registry_candidates": remote_candidates,
        "server_count": len(local_servers),
        "active_server_count": len(active_servers),
        "inactive_server_count": len(inactive_servers),
        "blocked_server_count": len(blocked_servers),
        "client_blocked_server_count": len(client_blocked_servers),
        "candidate_count": len(remote_candidates),
        "active_mcps": sorted(active_set),
        "allowed_tools": sorted(allowed_set),
        "activation_gate": {
            "required": True,
            "discovery_tools": ["MCPList", "MCPSearch"],
            "activation_tool": "MCPActivate",
            "user_approval_required": True,
        },
        "metadata": _as_dict(metadata),
        "executed": False,
        "execution_result": None,
    }


def filter_mcp_registry_servers(
    registry: dict[str, Any] | None,
    *,
    gate_state: str | None = None,
    callable_now: bool | None = None,
    allowed_by_client: bool | None = None,
) -> list[dict[str, Any]]:
    """Filter normalized local MCP servers without changing registry state."""

    data = _as_dict(registry)
    servers = [_as_dict(item) for item in _as_list(data.get("servers")) if _as_dict(item)]
    result: list[dict[str, Any]] = []
    for server in servers:
        if gate_state is not None and server.get("gate_state") != gate_state:
            continue
        if callable_now is not None and bool(server.get("callable_now")) is not callable_now:
            continue
        if allowed_by_client is not None and bool(server.get("allowed_by_client", True)) is not allowed_by_client:
            continue
        result.append(server)
    return result


def search_mcp_tool_registry(
    registry: dict[str, Any] | None,
    query: str | None,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Search normalized local/candidate MCP registry records side-effect free."""

    data = _as_dict(registry)
    query_text = _as_text(query).lower()
    if not query_text:
        return []

    records = [
        *_as_list(data.get("servers")),
        *_as_list(data.get("registry_candidates")),
    ]

    scored: list[tuple[int, dict[str, Any]]] = []
    for raw in records:
        item = _as_dict(raw)
        if not item:
            continue
        haystack = " ".join([
            _as_text(item.get("name")),
            _as_text(item.get("server_name")),
            _as_text(item.get("title")),
            _as_text(item.get("description")),
            " ".join(_as_text(keyword) for keyword in _as_list(item.get("keywords"))),
            " ".join(_as_text(tool_name) for tool_name in _as_list(item.get("allowed_tool_names"))),
            " ".join(_as_text(tool_name) for tool_name in _as_list(item.get("denied_tool_names"))),
        ]).lower()
        if query_text not in haystack:
            continue

        score = 1
        if query_text in _as_text(item.get("name")).lower():
            score += 5
        if query_text in _as_text(item.get("server_name")).lower():
            score += 4
        if bool(item.get("callable_now")):
            score += 3
        if item.get("gate_state") == "inactive":
            score += 2
        if item.get("contract_kind") == "mcp_server":
            score += 1
        scored.append((score, item))

    scored.sort(key=lambda pair: (-pair[0], _as_text(pair[1].get("server_name"))))
    safe_limit = max(0, int(limit or 0))
    return [item for _, item in scored[:safe_limit]]


def summarize_mcp_tool_registry(registry: dict[str, Any] | None) -> str:
    """Return compact registry summary for prompts and audits."""

    data = _as_dict(registry)
    return (
        "MCP Registry: "
        f"servers={data.get('server_count', 0)}; "
        f"active={data.get('active_server_count', 0)}; "
        f"inactive={data.get('inactive_server_count', 0)}; "
        f"blocked={data.get('blocked_server_count', 0)}; "
        f"client_blocked={data.get('client_blocked_server_count', 0)}; "
        f"candidates={data.get('candidate_count', 0)}; "
        "executed=False"
    )


def build_mcp_required_user_action(
    *,
    action_type: str,
    target: str,
    label: str,
    reason: str,
    server_name: str | None = None,
    required: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build structured UI action metadata for user-resolvable MCP blockers."""

    return {
        "action_type": _as_text(action_type) or "open_settings",
        "target": _as_text(target),
        "label": _as_text(label),
        "reason": _as_text(reason),
        "server_name": sanitize_mcp_server_name(server_name),
        "required": bool(required),
        "metadata": _as_dict(metadata),
        "executed": False,
        "execution_result": None,
    }


def inspect_mcp_server_contract(server: dict[str, Any] | None) -> dict[str, Any]:
    """Inspect one MCP server contract without activating or probing it."""

    data = _as_dict(server)
    server_name = _as_text(data.get("server_name")) or sanitize_mcp_server_name(data.get("name"))
    findings: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    if not data:
        findings.append({
            "severity": "error",
            "code": "mcp_server_missing",
            "message": "MCP server contract is missing.",
        })
        return {
            "contract_kind": "mcp_server_inspection",
            "server_name": None,
            "status": "blocked",
            "ready": False,
            "findings": findings,
            "required_user_actions": actions,
            "executed": False,
            "execution_result": None,
        }

    gate_state = _as_text(data.get("gate_state")) or "unknown"
    auth_status = _as_text(data.get("auth_status")) or "unknown"

    if not data.get("enabled", True):
        findings.append({
            "severity": "error",
            "code": "mcp_server_disabled",
            "message": "MCP server is disabled.",
        })
        actions.append(build_mcp_required_user_action(
            action_type="open_settings",
            target=f"tools/mcp/{server_name}",
            label=f"Enable {data.get('name') or server_name}",
            reason="mcp_server_disabled",
            server_name=server_name,
        ))

    if auth_status in {"expired", "error", "unknown"}:
        findings.append({
            "severity": "error",
            "code": "mcp_auth_not_ready",
            "message": f"MCP auth status is {auth_status}.",
        })
        actions.append(build_mcp_required_user_action(
            action_type="connect_account",
            target=f"tools/mcp/{server_name}/auth",
            label=f"Connect {data.get('name') or server_name}",
            reason="mcp_auth_not_ready",
            server_name=server_name,
        ))

    if data.get("allowed_by_client") is False:
        findings.append({
            "severity": "warning",
            "code": "mcp_not_allowed_by_client",
            "message": "MCP server is not included in the current client allowed_tools.",
        })
        actions.append(build_mcp_required_user_action(
            action_type="review_permissions",
            target=f"tools/mcp/{server_name}/permissions",
            label=f"Review permissions for {data.get('name') or server_name}",
            reason="mcp_not_allowed_by_client",
            server_name=server_name,
        ))

    if gate_state == "inactive":
        findings.append({
            "severity": "info",
            "code": "mcp_activation_required",
            "message": "MCP server must be activated before its tools are callable.",
        })
        actions.append(build_mcp_required_user_action(
            action_type="activate_mcp",
            target=f"pending-actions/mcp/{server_name}/activate",
            label=f"Activate {data.get('name') or server_name}",
            reason="mcp_activation_required",
            server_name=server_name,
        ))

    if gate_state == "blocked":
        findings.append({
            "severity": "error",
            "code": "mcp_server_blocked",
            "message": "MCP server is blocked and cannot be activated until configuration is fixed.",
        })
        actions.append(build_mcp_required_user_action(
            action_type="open_settings",
            target=f"tools/mcp/{server_name}",
            label=f"Configure {data.get('name') or server_name}",
            reason="mcp_server_blocked",
            server_name=server_name,
        ))

    if gate_state == "unavailable":
        findings.append({
            "severity": "error",
            "code": "mcp_server_unavailable",
            "message": "MCP server is unavailable.",
        })

    ready = bool(data.get("callable_now")) and not any(item.get("severity") == "error" for item in findings)
    status = "ready" if ready else "needs_user_action" if actions else "blocked" if findings else "unknown"

    return {
        "contract_kind": "mcp_server_inspection",
        "server_name": server_name,
        "status": status,
        "ready": ready,
        "gate_state": gate_state,
        "auth_status": auth_status,
        "findings": findings,
        "required_user_actions": actions,
        "executed": False,
        "execution_result": None,
    }


def inspect_mcp_tool_registry(
    registry: dict[str, Any] | None,
    *,
    target_server_name: str | None = None,
) -> dict[str, Any]:
    """Inspect a registry view and produce actionable MCP readiness metadata."""

    data = _as_dict(registry)
    target = sanitize_mcp_server_name(target_server_name)
    servers = [_as_dict(item) for item in _as_list(data.get("servers")) if _as_dict(item)]
    if target:
        servers = [item for item in servers if item.get("server_name") == target]

    inspections = [inspect_mcp_server_contract(server) for server in servers]
    findings = [finding for item in inspections for finding in _as_list(item.get("findings"))]
    actions = [action for item in inspections for action in _as_list(item.get("required_user_actions"))]

    ready_count = sum(1 for item in inspections if item.get("ready"))
    blocked_count = sum(1 for item in inspections if item.get("status") == "blocked")
    needs_action_count = sum(1 for item in inspections if item.get("status") == "needs_user_action")

    if target and not inspections:
        findings.append({
            "severity": "error",
            "code": "mcp_target_not_installed",
            "message": f"MCP server '{target}' is not installed.",
        })
        actions.append(build_mcp_required_user_action(
            action_type="open_settings",
            target=f"tools/mcp/{target}",
            label=f"Configure {target.replace('-', ' ').title()} MCP",
            reason="mcp_target_not_installed",
            server_name=target,
        ))

    status = (
        "ready" if inspections and ready_count == len(inspections)
        else "needs_user_action" if actions
        else "blocked" if findings
        else "empty"
    )

    return {
        "contract_kind": "mcp_registry_inspection",
        "target_server_name": target or None,
        "status": status,
        "ready": status == "ready",
        "inspection_count": len(inspections),
        "ready_count": ready_count,
        "needs_action_count": needs_action_count,
        "blocked_count": blocked_count,
        "findings": findings,
        "required_user_actions": actions,
        "executed": False,
        "execution_result": None,
    }


def summarize_mcp_inspection(inspection: dict[str, Any] | None) -> str:
    """Return compact MCP inspection summary for prompts and UI traces."""

    data = _as_dict(inspection)
    return (
        "MCP Inspection: "
        f"status={data.get('status') or 'empty'}; "
        f"ready={bool(data.get('ready'))}; "
        f"inspected={data.get('inspection_count', 0)}; "
        f"actions={len(_as_list(data.get('required_user_actions')))}; "
        f"findings={len(_as_list(data.get('findings')))}; "
        "executed=False"
    )


def estimate_mcp_definition_cost(server: dict[str, Any] | None) -> int:
    """Estimate prompt/tool-definition cost for one MCP server contract."""

    data = _as_dict(server)
    base = 160
    text_cost = (
        len(_as_text(data.get("name")))
        + len(_as_text(data.get("description")))
        + len(_as_text(data.get("server_name")))
    )
    allowed_tool_names = _as_list(data.get("allowed_tool_names"))
    denied_tool_names = _as_list(data.get("denied_tool_names"))
    permission_cost = 32 * (len(allowed_tool_names) + len(denied_tool_names))
    transport_cost = 40 if data.get("transport") and data.get("transport") != "unknown" else 10
    active_cost = 80 if data.get("callable_now") else 0
    return max(1, base + text_cost + permission_cost + transport_cost + active_cost)


def score_mcp_server_for_budget(
    server: dict[str, Any] | None,
    *,
    query: str | None = None,
) -> int:
    """Score one MCP server for context inclusion priority."""

    data = _as_dict(server)
    query_text = _as_text(query).lower()
    score = 0

    if data.get("callable_now"):
        score += 100
    if data.get("gate_state") == "inactive":
        score += 60
    if data.get("gate_state") == "blocked":
        score += 20
    if data.get("allowed_by_client", True):
        score += 25
    if data.get("requires_user_approval"):
        score += 10

    haystack = " ".join([
        _as_text(data.get("name")),
        _as_text(data.get("server_name")),
        _as_text(data.get("description")),
        " ".join(_as_text(item) for item in _as_list(data.get("allowed_tool_names"))),
    ]).lower()
    if query_text and query_text in haystack:
        score += 80

    return score


def build_mcp_tool_definition_budget(
    registry: dict[str, Any] | None,
    *,
    max_definition_cost: int = 1200,
    max_servers: int = 6,
    query: str | None = None,
    include_candidates: bool = False,
) -> dict[str, Any]:
    """Select MCP servers/candidates for prompt inclusion without loading tools."""

    data = _as_dict(registry)
    servers = [_as_dict(item) for item in _as_list(data.get("servers")) if _as_dict(item)]
    candidates = [_as_dict(item) for item in _as_list(data.get("registry_candidates")) if _as_dict(item)]

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, server in enumerate(servers):
        cost = estimate_mcp_definition_cost(server)
        score = score_mcp_server_for_budget(server, query=query)
        scored.append((score, cost, server))

    scored.sort(key=lambda item: (-item[0], item[1], _as_text(item[2].get("server_name"))))

    included: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    used_cost = 0
    safe_limit = max(0, int(max_servers or 0))
    safe_budget = max(0, int(max_definition_cost or 0))

    for score, cost, server in scored:
        record = {
            "server_name": server.get("server_name"),
            "name": server.get("name"),
            "gate_state": server.get("gate_state"),
            "callable_now": bool(server.get("callable_now")),
            "allowed_by_client": bool(server.get("allowed_by_client", True)),
            "definition_cost": cost,
            "priority_score": score,
        }
        if len(included) < safe_limit and used_cost + cost <= safe_budget:
            included.append(record)
            used_cost += cost
        else:
            reason = "server_limit" if len(included) >= safe_limit else "budget_limit"
            deferred.append({**record, "defer_reason": reason})

    candidate_records: list[dict[str, Any]] = []
    if include_candidates:
        for candidate in candidates[:safe_limit]:
            candidate_records.append({
                "server_name": candidate.get("server_name"),
                "name": candidate.get("name"),
                "title": candidate.get("title"),
                "source": candidate.get("source"),
                "callable_now": False,
                "installed": False,
                "definition_cost": 80 + len(_as_text(candidate.get("name"))) + len(_as_text(candidate.get("description"))),
            })

    return {
        "contract_kind": "mcp_tool_definition_budget",
        "max_definition_cost": safe_budget,
        "used_definition_cost": used_cost,
        "remaining_definition_cost": max(0, safe_budget - used_cost),
        "max_servers": safe_limit,
        "included_servers": included,
        "deferred_servers": deferred,
        "candidate_summaries": candidate_records,
        "included_count": len(included),
        "deferred_count": len(deferred),
        "candidate_count": len(candidate_records),
        "query": _as_text(query) or None,
        "executed": False,
        "execution_result": None,
    }


def summarize_mcp_tool_definition_budget(budget: dict[str, Any] | None) -> str:
    """Return compact budget summary for prompts and audits."""

    data = _as_dict(budget)
    return (
        "MCP Tool Definition Budget: "
        f"included={data.get('included_count', 0)}; "
        f"deferred={data.get('deferred_count', 0)}; "
        f"candidates={data.get('candidate_count', 0)}; "
        f"used={data.get('used_definition_cost', 0)}/"
        f"{data.get('max_definition_cost', 0)}; "
        "executed=False"
    )


VALID_MCP_FALLBACK_TYPES = {"cli", "script", "manual", "none"}
VALID_MCP_FALLBACK_STATES = {"available", "requires_user_action", "blocked", "unavailable"}


def normalize_mcp_fallback_type(value: Any) -> str:
    """Normalize fallback adapter type without running it."""

    fallback_type = _as_text(value).lower()
    return fallback_type if fallback_type in VALID_MCP_FALLBACK_TYPES else "none"


def build_mcp_fallback_adapter_contract(
    *,
    server_name: str | None = None,
    fallback_type: str | None = None,
    command: str | None = None,
    args: list[Any] | None = None,
    script_path: str | None = None,
    reason: str | None = None,
    requires_user_approval: bool = True,
    requires_manual_setup: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe a CLI/script/manual fallback without executing it."""

    normalized_type = normalize_mcp_fallback_type(fallback_type)
    normalized_server = sanitize_mcp_server_name(server_name)
    clean_args = [_as_text(item) for item in _as_list(args) if _as_text(item)]
    clean_command = _as_text(command)
    clean_script = _as_text(script_path)

    if normalized_type == "none":
        state = "unavailable"
    elif requires_manual_setup:
        state = "requires_user_action"
    elif normalized_type in {"cli", "script"} and (clean_command or clean_script):
        state = "available"
    elif normalized_type == "manual":
        state = "requires_user_action"
    else:
        state = "blocked"

    actions: list[dict[str, Any]] = []
    if state == "requires_user_action":
        actions.append(build_mcp_required_user_action(
            action_type="open_settings",
            target=f"tools/mcp/{normalized_server}/fallback",
            label=f"Configure {normalized_server.replace('-', ' ').title()} fallback",
            reason="mcp_fallback_requires_manual_setup",
            server_name=normalized_server,
        ))

    return {
        "contract_kind": "mcp_fallback_adapter",
        "server_name": normalized_server or None,
        "fallback_type": normalized_type,
        "state": state,
        "command": clean_command or None,
        "args": clean_args,
        "script_path": clean_script or None,
        "reason": _as_text(reason) or None,
        "requires_user_approval": bool(requires_user_approval),
        "requires_manual_setup": bool(requires_manual_setup),
        "required_user_actions": actions,
        "metadata": _as_dict(metadata),
        "executed": False,
        "execution_result": None,
    }


def build_mcp_fallback_plan(
    *,
    inspection: dict[str, Any] | None = None,
    fallback_adapters: list[Any] | None = None,
    target_server_name: str | None = None,
    allow_cli_fallback: bool = True,
) -> dict[str, Any]:
    """Plan MCP fallback options from inspection state without executing them."""

    inspect_data = _as_dict(inspection)
    target = sanitize_mcp_server_name(target_server_name or inspect_data.get("target_server_name"))
    adapters = [
        item if _as_dict(item).get("contract_kind") == "mcp_fallback_adapter"
        else build_mcp_fallback_adapter_contract(**_as_dict(item))
        for item in _as_list(fallback_adapters)
        if _as_dict(item)
    ]

    if target:
        adapters = [item for item in adapters if _as_dict(item).get("server_name") == target]

    viable = [
        item for item in adapters
        if _as_dict(item).get("state") == "available"
        and (allow_cli_fallback or _as_dict(item).get("fallback_type") != "cli")
    ]
    user_action_adapters = [item for item in adapters if _as_dict(item).get("state") == "requires_user_action"]
    blocked = [item for item in adapters if _as_dict(item).get("state") in {"blocked", "unavailable"}]

    required_actions = []
    for adapter in user_action_adapters:
        required_actions.extend(_as_list(_as_dict(adapter).get("required_user_actions")))

    if inspect_data.get("ready"):
        status = "not_needed"
    elif viable:
        status = "fallback_available"
    elif required_actions:
        status = "requires_user_action"
    else:
        status = "blocked"

    return {
        "contract_kind": "mcp_fallback_plan",
        "target_server_name": target or None,
        "status": status,
        "fallback_available": bool(viable),
        "selected_fallback": viable[0] if viable else None,
        "fallback_adapters": adapters,
        "viable_count": len(viable),
        "requires_user_action_count": len(user_action_adapters),
        "blocked_count": len(blocked),
        "required_user_actions": required_actions,
        "allow_cli_fallback": bool(allow_cli_fallback),
        "executed": False,
        "execution_result": None,
    }


def summarize_mcp_fallback_plan(plan: dict[str, Any] | None) -> str:
    """Return compact fallback summary for prompts, UI, and audit traces."""

    data = _as_dict(plan)
    selected = _as_dict(data.get("selected_fallback"))
    return (
        "MCP Fallback Plan: "
        f"status={data.get('status') or 'empty'}; "
        f"target={data.get('target_server_name') or 'none'}; "
        f"available={bool(data.get('fallback_available'))}; "
        f"selected={selected.get('fallback_type') or 'none'}; "
        f"actions={len(_as_list(data.get('required_user_actions')))}; "
        "executed=False"
    )


def build_mcp_evidence_record(
    *,
    evidence_id: str | None = None,
    server_name: str | None = None,
    registry: dict[str, Any] | None = None,
    inspection: dict[str, Any] | None = None,
    fallback_plan: dict[str, Any] | None = None,
    definition_budget: dict[str, Any] | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build structured MCP evidence without executing MCP or persisting state."""

    registry_data = _as_dict(registry)
    inspection_data = _as_dict(inspection)
    fallback_data = _as_dict(fallback_plan)
    budget_data = _as_dict(definition_budget)
    normalized_server = sanitize_mcp_server_name(
        server_name
        or inspection_data.get("target_server_name")
        or fallback_data.get("target_server_name")
    )

    findings = _as_list(inspection_data.get("findings"))
    actions = [
        *_as_list(inspection_data.get("required_user_actions")),
        *_as_list(fallback_data.get("required_user_actions")),
    ]

    status_parts = []
    if inspection_data.get("status"):
        status_parts.append(f"inspection={inspection_data.get('status')}")
    if fallback_data.get("status"):
        status_parts.append(f"fallback={fallback_data.get('status')}")
    if budget_data.get("contract_kind"):
        status_parts.append(
            f"budget_included={budget_data.get('included_count', 0)}"
        )

    return {
        "contract_kind": "mcp_evidence_record",
        "evidence_id": _as_text(evidence_id) or None,
        "server_name": normalized_server or None,
        "source": _as_text(source) or "mcp_contract",
        "status": "; ".join(status_parts) if status_parts else "empty",
        "registry_summary": summarize_mcp_tool_registry(registry_data) if registry_data else None,
        "inspection_summary": summarize_mcp_inspection(inspection_data) if inspection_data else None,
        "fallback_summary": summarize_mcp_fallback_plan(fallback_data) if fallback_data else None,
        "budget_summary": summarize_mcp_tool_definition_budget(budget_data) if budget_data else None,
        "finding_count": len(findings),
        "required_user_action_count": len(actions),
        "findings": findings,
        "required_user_actions": actions,
        "ready": bool(inspection_data.get("ready")),
        "fallback_available": bool(fallback_data.get("fallback_available")),
        "selected_fallback": _as_dict(fallback_data.get("selected_fallback")) or None,
        "included_mcp_servers": _as_list(budget_data.get("included_servers")),
        "deferred_mcp_servers": _as_list(budget_data.get("deferred_servers")),
        "metadata": _as_dict(metadata),
        "executed": False,
        "execution_result": None,
    }


def build_mcp_evidence_bundle(
    *,
    records: list[Any] | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bundle MCP evidence records for transport into RI/State Context."""

    normalized_records = [
        _as_dict(item)
        for item in _as_list(records)
        if _as_dict(item)
    ]
    ready_count = sum(1 for item in normalized_records if item.get("ready"))
    fallback_available_count = sum(1 for item in normalized_records if item.get("fallback_available"))
    action_count = sum(int(item.get("required_user_action_count") or 0) for item in normalized_records)
    finding_count = sum(int(item.get("finding_count") or 0) for item in normalized_records)

    return {
        "contract_kind": "mcp_evidence_bundle",
        "source": _as_text(source) or "mcp_contract",
        "record_count": len(normalized_records),
        "ready_count": ready_count,
        "fallback_available_count": fallback_available_count,
        "finding_count": finding_count,
        "required_user_action_count": action_count,
        "records": normalized_records,
        "metadata": _as_dict(metadata),
        "executed": False,
        "execution_result": None,
    }


def summarize_mcp_evidence_record(record: dict[str, Any] | None) -> str:
    """Return compact MCP evidence record summary for prompts and traces."""

    data = _as_dict(record)
    return (
        "MCP Evidence: "
        f"server={data.get('server_name') or 'none'}; "
        f"status={data.get('status') or 'empty'}; "
        f"ready={bool(data.get('ready'))}; "
        f"fallback_available={bool(data.get('fallback_available'))}; "
        f"findings={data.get('finding_count', 0)}; "
        f"actions={data.get('required_user_action_count', 0)}; "
        "executed=False"
    )


def summarize_mcp_evidence_bundle(bundle: dict[str, Any] | None) -> str:
    """Return compact MCP evidence bundle summary for prompts and traces."""

    data = _as_dict(bundle)
    return (
        "MCP Evidence Bundle: "
        f"records={data.get('record_count', 0)}; "
        f"ready={data.get('ready_count', 0)}; "
        f"fallback_available={data.get('fallback_available_count', 0)}; "
        f"findings={data.get('finding_count', 0)}; "
        f"actions={data.get('required_user_action_count', 0)}; "
        "executed=False"
    )


VALID_MCP_SANDBOX_DECISIONS = {"allow", "requires_approval", "block"}
MCP_SANDBOX_DANGEROUS_COMMANDS = {
    "rm",
    "del",
    "erase",
    "format",
    "shutdown",
    "reboot",
    "powershell",
    "pwsh",
    "cmd",
    "bash",
    "sh",
}
MCP_SANDBOX_NETWORK_FLAGS = {"--url", "--host", "--listen", "--port", "--remote", "--server"}
MCP_SANDBOX_WRITE_FLAGS = {
    "--write",
    "--delete",
    "--remove",
    "--force",
    "--output",
    "--out",
    "--projectPath",
    "-projectPath",
}


def classify_mcp_sandbox_risk(
    *,
    command: str | None = None,
    args: list[Any] | None = None,
    script_path: str | None = None,
    fallback_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify MCP/fallback sandbox risk without executing anything."""

    clean_command = _as_text(command)
    command_name = clean_command.replace("\\", "/").split("/")[-1].lower()
    clean_args = [_as_text(item) for item in _as_list(args) if _as_text(item)]
    clean_script = _as_text(script_path)
    normalized_type = normalize_mcp_fallback_type(fallback_type)
    data = _as_dict(metadata)

    risk_flags: list[str] = []

    if command_name in MCP_SANDBOX_DANGEROUS_COMMANDS:
        risk_flags.append("dangerous_command")

    lowered_args = [item.lower() for item in clean_args]
    if any(item in MCP_SANDBOX_NETWORK_FLAGS for item in lowered_args):
        risk_flags.append("network_surface")
    if any(item in MCP_SANDBOX_WRITE_FLAGS for item in clean_args):
        risk_flags.append("write_surface")
    if any(".." in item.replace("\\", "/").split("/") for item in clean_args + [clean_script]):
        risk_flags.append("path_traversal")
    if data.get("requires_network"):
        risk_flags.append("network_required")
    if data.get("writes_files"):
        risk_flags.append("writes_files")
    if data.get("external_app"):
        risk_flags.append("external_app")
    if normalized_type == "manual":
        risk_flags.append("manual_only")
    if normalized_type == "none":
        risk_flags.append("no_fallback")

    if "dangerous_command" in risk_flags or "path_traversal" in risk_flags:
        level = "high"
    elif {"network_surface", "network_required", "writes_files", "write_surface", "external_app"} & set(risk_flags):
        level = "medium"
    elif risk_flags:
        level = "low"
    else:
        level = "low"

    return {
        "contract_kind": "mcp_sandbox_risk",
        "risk_level": level,
        "risk_flags": sorted(set(risk_flags)),
        "command": clean_command or None,
        "args": clean_args,
        "script_path": clean_script or None,
        "fallback_type": normalized_type,
        "executed": False,
        "execution_result": None,
    }


def build_mcp_sandbox_policy_decision(
    *,
    fallback_adapter: dict[str, Any] | None = None,
    fallback_plan: dict[str, Any] | None = None,
    allowed_commands: list[Any] | None = None,
    allowed_script_roots: list[Any] | None = None,
    require_approval_for_external_apps: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build sandbox decision for MCP fallback/tool use without execution."""

    plan = _as_dict(fallback_plan)
    adapter = _as_dict(fallback_adapter) or _as_dict(plan.get("selected_fallback"))
    command = _as_text(adapter.get("command"))
    args = _as_list(adapter.get("args"))
    script_path = _as_text(adapter.get("script_path"))
    fallback_type = adapter.get("fallback_type")
    allowed_command_set = {_as_text(item).lower() for item in _as_list(allowed_commands) if _as_text(item)}
    allowed_roots = [_as_text(item).replace("\\", "/").rstrip("/") for item in _as_list(allowed_script_roots) if _as_text(item)]

    risk = classify_mcp_sandbox_risk(
        command=command,
        args=args,
        script_path=script_path,
        fallback_type=fallback_type,
        metadata={**_as_dict(adapter.get("metadata")), **_as_dict(metadata)},
    )

    reasons: list[str] = []
    command_name = command.replace("\\", "/").split("/")[-1].lower() if command else ""
    if not adapter:
        reasons.append("fallback_adapter_missing")
    if command_name and allowed_command_set and command_name not in allowed_command_set:
        reasons.append("command_not_allowlisted")
    if script_path and allowed_roots:
        normalized_script = script_path.replace("\\", "/")
        if not any(normalized_script.startswith(root + "/") or normalized_script == root for root in allowed_roots):
            reasons.append("script_path_outside_allowed_roots")
    if adapter.get("requires_user_approval"):
        reasons.append("adapter_requires_user_approval")
    if require_approval_for_external_apps and "external_app" in risk.get("risk_flags", []):
        reasons.append("external_app_requires_approval")
    if risk.get("risk_level") == "high":
        reasons.append("high_risk")

    if "high_risk" in reasons or "command_not_allowlisted" in reasons or "script_path_outside_allowed_roots" in reasons:
        decision = "block"
    elif reasons or risk.get("risk_level") == "medium":
        decision = "requires_approval"
    else:
        decision = "allow"

    actions: list[dict[str, Any]] = []
    if decision == "requires_approval":
        actions.append(build_mcp_required_user_action(
            action_type="review_permissions",
            target=f"pending-actions/mcp/{adapter.get('server_name') or 'unknown'}/sandbox",
            label=f"Review sandbox policy for {(adapter.get('server_name') or 'MCP').replace('-', ' ').title()}",
            reason="mcp_sandbox_requires_approval",
            server_name=adapter.get("server_name"),
        ))

    return {
        "contract_kind": "mcp_sandbox_policy_decision",
        "decision": decision,
        "reasons": reasons,
        "risk": risk,
        "fallback_adapter": adapter or None,
        "required_user_actions": actions,
        "allowed_commands": sorted(allowed_command_set),
        "allowed_script_roots": allowed_roots,
        "executed": False,
        "execution_result": None,
    }


def summarize_mcp_sandbox_policy_decision(decision: dict[str, Any] | None) -> str:
    """Return compact MCP sandbox decision summary."""

    data = _as_dict(decision)
    risk = _as_dict(data.get("risk"))
    return (
        "MCP Sandbox Policy: "
        f"decision={data.get('decision') or 'empty'}; "
        f"risk={risk.get('risk_level') or 'unknown'}; "
        f"reasons={len(_as_list(data.get('reasons')))}; "
        f"actions={len(_as_list(data.get('required_user_actions')))}; "
        "executed=False"
    )


VALID_MCP_ACTIVATION_GUARD_DECISIONS = {"allow", "already_active", "requires_approval", "block"}


def build_mcp_activation_guard_decision(
    *,
    server_name: str | None = None,
    registry: dict[str, Any] | None = None,
    inspection: dict[str, Any] | None = None,
    sandbox_policy: dict[str, Any] | None = None,
    active_mcps: list[Any] | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a side-effect-free MCP activation guard decision.

    This does not activate MCP servers, mutate sessions, call tools, or persist
    state. It only decides whether MCPActivate may continue through the existing
    HITL/runtime activation path.
    """

    normalized_server = sanitize_mcp_server_name(server_name)
    active_set = {sanitize_mcp_server_name(item) for item in _as_list(active_mcps)}
    registry_data = _as_dict(registry)
    inspection_data = _as_dict(inspection)
    sandbox_data = _as_dict(sandbox_policy)
    requested_reason = _as_text(reason)

    reasons: list[str] = []
    required_actions: list[dict[str, Any]] = []

    if not normalized_server:
        reasons.append("server_name_missing")

    if normalized_server and normalized_server in active_set:
        decision = "already_active"
    else:
        decision = "requires_approval"

    if registry_data:
        server_names = {
            sanitize_mcp_server_name(item.get("server_name") or item.get("name"))
            for item in _as_list(registry_data.get("servers"))
            if isinstance(item, dict)
        }
        if normalized_server and server_names and normalized_server not in server_names:
            reasons.append("server_not_in_registry")

    if inspection_data:
        inspection_status = _as_text(inspection_data.get("status"))
        target_server_name = sanitize_mcp_server_name(inspection_data.get("target_server_name") or inspection_data.get("server_name"))
        if target_server_name and normalized_server and target_server_name != normalized_server:
            reasons.append("inspection_target_mismatch")
        if inspection_status in {"blocked", "unknown"}:
            reasons.append(f"inspection_{inspection_status}")
        if inspection_status == "needs_user_action":
            reasons.append("inspection_needs_user_action")
        if isinstance(inspection_data.get("required_user_actions"), list):
            required_actions.extend([
                action for action in inspection_data.get("required_user_actions", [])
                if isinstance(action, dict)
            ])

    if sandbox_data:
        sandbox_decision = _as_text(sandbox_data.get("decision"))
        if sandbox_decision == "block":
            reasons.append("sandbox_block")
        elif sandbox_decision == "requires_approval":
            reasons.append("sandbox_requires_approval")
        if isinstance(sandbox_data.get("required_user_actions"), list):
            required_actions.extend([
                action for action in sandbox_data.get("required_user_actions", [])
                if isinstance(action, dict)
            ])

    if "server_name_missing" in reasons or "server_not_in_registry" in reasons or "inspection_target_mismatch" in reasons:
        decision = "block"
    elif "inspection_blocked" in reasons or "inspection_unknown" in reasons or "sandbox_block" in reasons:
        decision = "block"
    elif decision != "already_active":
        decision = "requires_approval"

    if decision == "requires_approval" and not any(action.get("action_type") == "activate_mcp" for action in required_actions):
        required_actions.append(build_mcp_required_user_action(
            action_type="activate_mcp",
            target=f"pending-actions/mcp/{normalized_server or 'unknown'}/activate",
            label=f"Activate {normalized_server or 'MCP'}",
            reason="mcp_activation_requires_approval",
            server_name=normalized_server,
        ))

    return {
        "contract_kind": "mcp_activation_guard_decision",
        "decision": decision,
        "server_name": normalized_server or None,
        "active_mcps": sorted(active_set),
        "reason": requested_reason or None,
        "reasons": sorted(set(reasons)),
        "required_user_actions": required_actions,
        "required_user_action_count": len(required_actions),
        "registry_status": registry_data.get("status") if registry_data else None,
        "inspection_status": inspection_data.get("status") if inspection_data else None,
        "sandbox_decision": sandbox_data.get("decision") if sandbox_data else None,
        "metadata": _as_dict(metadata),
        "executed": False,
        "execution_result": None,
    }


def summarize_mcp_activation_guard_decision(decision: dict[str, Any] | None) -> str:
    """Return compact MCP activation guard summary."""

    data = _as_dict(decision)
    return (
        "MCP Activation Guard: "
        f"decision={data.get('decision') or 'empty'}; "
        f"server={data.get('server_name') or 'none'}; "
        f"reasons={len(_as_list(data.get('reasons')))}; "
        f"actions={len(_as_list(data.get('required_user_actions')))}; "
        "executed=False"
    )
