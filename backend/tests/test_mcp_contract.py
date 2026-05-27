from backend.apps.swarms.mcp_contract import (
    build_mcp_client_contract,
    build_mcp_contract_from_tool_definition,
    build_mcp_host_contract,
    build_mcp_server_contract,
    sanitize_mcp_server_name,
    summarize_mcp_host_contract,
)


def test_sanitize_mcp_server_name_matches_runtime_slug_shape():
    assert sanitize_mcp_server_name("Google Workspace!") == "google-workspace"
    assert sanitize_mcp_server_name("  Discord MCP  ") == "discord-mcp"


def test_build_mcp_server_contract_keeps_activation_side_effect_free():
    contract = build_mcp_server_contract(
        server_id="tool-1",
        name="Google Workspace",
        description="Email and calendar tools",
        mcp_config={
            "type": "stdio",
            "command": "python",
            "args": ["-m", "gmail_mcp"],
            "env": {"GOOGLE_TOKEN": "secret"},
        },
        enabled=True,
        auth_status="connected",
        tool_permissions={"query_gmail_emails": "ask", "delete_email": "deny"},
        connected_account_email="user@example.com",
        active=False,
    )

    assert contract["contract_kind"] == "mcp_server"
    assert contract["server_name"] == "google-workspace"
    assert contract["transport"] == "stdio"
    assert contract["command"] == "python"
    assert contract["args"] == ["-m", "gmail_mcp"]
    assert contract["env_keys"] == ["GOOGLE_TOKEN"]
    assert contract["gate_state"] == "inactive"
    assert contract["requires_activation"] is True
    assert contract["requires_user_approval"] is True
    assert contract["callable_now"] is False
    assert contract["allowed_tool_names"] == ["query_gmail_emails"]
    assert contract["denied_tool_names"] == ["delete_email"]
    assert contract["connected_account_email"] == "user@example.com"
    assert contract["executed"] is False
    assert contract["execution_result"] is None


def test_build_mcp_server_contract_marks_active_server_callable_without_execution():
    contract = build_mcp_server_contract(
        name="Slack",
        mcp_config={"type": "streamable-http", "url": "https://example.invalid/mcp"},
        enabled=True,
        auth_status="configured",
        active=True,
    )

    assert contract["server_name"] == "slack"
    assert contract["transport"] == "streamable_http"
    assert contract["gate_state"] == "active"
    assert contract["requires_activation"] is False
    assert contract["callable_now"] is True
    assert contract["executed"] is False


def test_build_mcp_server_contract_blocks_disabled_or_bad_auth():
    disabled = build_mcp_server_contract(name="Disabled", enabled=False, auth_status="connected")
    expired = build_mcp_server_contract(name="Expired", enabled=True, auth_status="expired")

    assert disabled["gate_state"] == "unavailable"
    assert disabled["callable_now"] is False
    assert expired["gate_state"] == "blocked"
    assert expired["requires_activation"] is False


def test_build_mcp_client_contract_records_activation_policy():
    contract = build_mcp_client_contract(
        client_id="client-1",
        session_id="session-1",
        allowed_tools=["Read", "mcp:Google Workspace"],
        active_mcps=["Google Workspace"],
        provider="anthropic",
        model="claude",
    )

    assert contract["contract_kind"] == "mcp_client"
    assert contract["session_id"] == "session-1"
    assert contract["active_mcps"] == ["google-workspace"]
    assert contract["activation_required_for_unlisted_servers"] is True
    assert contract["activation_tool_names"] == ["MCPList", "MCPSearch", "MCPActivate"]
    assert contract["child_sessions_inherit_active_mcps"] is False
    assert contract["executed"] is False


def test_build_mcp_host_contract_summarizes_server_gate_states():
    active = build_mcp_server_contract(name="Active", active=True, auth_status="connected")
    inactive = build_mcp_server_contract(name="Inactive", active=False, auth_status="connected")
    blocked = build_mcp_server_contract(name="Blocked", active=False, auth_status="expired")
    client = build_mcp_client_contract(session_id="session-2", active_mcps=["Active"])

    contract = build_mcp_host_contract(
        host_id="host-1",
        host_name="openswarm",
        client=client,
        servers=[active, inactive, blocked],
    )

    assert contract["contract_kind"] == "mcp_host"
    assert contract["server_count"] == 3
    assert contract["active_server_count"] == 1
    assert contract["inactive_server_count"] == 1
    assert contract["blocked_server_count"] == 1
    assert contract["activation_gate"]["activation_tool"] == "MCPActivate"
    assert contract["activation_gate"]["user_approval_required"] is True
    assert contract["executed"] is False
    assert contract["execution_result"] is None


def test_build_mcp_contract_from_tool_definition_dict_uses_active_mcps():
    tool = {
        "id": "tool-2",
        "name": "Discord",
        "description": "Discord integration",
        "mcp_config": {"type": "stdio", "command": "python", "args": ["-m", "backend.apps.discord_mcp_shim"]},
        "enabled": True,
        "auth_status": "connected",
        "tool_permissions": {"send_message": "ask"},
        "connected_account_email": None,
    }

    contract = build_mcp_contract_from_tool_definition(tool, active_mcps=["discord"])

    assert contract["server_id"] == "tool-2"
    assert contract["server_name"] == "discord"
    assert contract["gate_state"] == "active"
    assert contract["callable_now"] is True
    assert contract["source"] == "tool_definition"


def test_summarize_mcp_host_contract_is_compact_and_non_executing():
    contract = build_mcp_host_contract(
        servers=[
            build_mcp_server_contract(name="A", active=True, auth_status="connected"),
            build_mcp_server_contract(name="B", active=False, auth_status="connected"),
        ]
    )

    summary = summarize_mcp_host_contract(contract)

    assert "MCP Host:" in summary
    assert "servers=2" in summary
    assert "active=1" in summary
    assert "inactive=1" in summary
    assert "activation_gate=required" in summary
    assert "executed=False" in summary
