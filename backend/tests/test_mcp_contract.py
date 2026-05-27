from backend.apps.swarms.mcp_contract import (
    build_mcp_client_contract,
    build_mcp_contract_from_tool_definition,
    build_mcp_fallback_adapter_contract,
    build_mcp_fallback_plan,
    build_mcp_host_contract,
    build_mcp_required_user_action,
    build_mcp_server_contract,
    build_mcp_tool_definition_budget,
    build_mcp_tool_registry,
    estimate_mcp_definition_cost,
    filter_mcp_registry_servers,
    inspect_mcp_server_contract,
    inspect_mcp_tool_registry,
    normalize_mcp_fallback_type,
    sanitize_mcp_server_name,
    score_mcp_server_for_budget,
    search_mcp_tool_registry,
    summarize_mcp_fallback_plan,
    summarize_mcp_host_contract,
    summarize_mcp_inspection,
    summarize_mcp_tool_definition_budget,
    summarize_mcp_tool_registry,
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


def test_build_mcp_tool_registry_normalizes_local_tools_without_runtime_effects():
    tools = [
        {
            "id": "tool-gmail",
            "name": "Google Workspace",
            "description": "Email and calendar",
            "mcp_config": {"type": "stdio", "command": "python", "args": ["-m", "gmail_mcp"]},
            "enabled": True,
            "auth_status": "connected",
            "tool_permissions": {"query_gmail_emails": "ask", "delete_email": "deny"},
        },
        {
            "id": "tool-slack",
            "name": "Slack",
            "description": "Team chat",
            "mcp_config": {"type": "streamable-http", "url": "https://example.invalid/mcp"},
            "enabled": True,
            "auth_status": "configured",
            "tool_permissions": {"send_message": "ask"},
        },
        {
            "id": "tool-expired",
            "name": "Expired Service",
            "description": "Expired auth",
            "mcp_config": {"type": "stdio", "command": "expired"},
            "enabled": True,
            "auth_status": "expired",
        },
    ]

    registry = build_mcp_tool_registry(
        tools=tools,
        active_mcps=["Slack"],
        allowed_tools=["Read", "mcp:Google Workspace", "mcp:Slack"],
    )

    assert registry["contract_kind"] == "mcp_tool_registry"
    assert registry["server_count"] == 3
    assert registry["active_server_count"] == 1
    assert registry["inactive_server_count"] == 1
    assert registry["blocked_server_count"] == 1
    assert registry["client_blocked_server_count"] == 1
    assert registry["active_mcps"] == ["slack"]
    assert registry["activation_gate"]["activation_tool"] == "MCPActivate"
    assert registry["executed"] is False
    assert registry["execution_result"] is None

    gmail = next(server for server in registry["servers"] if server["server_name"] == "google-workspace")
    slack = next(server for server in registry["servers"] if server["server_name"] == "slack")
    expired = next(server for server in registry["servers"] if server["server_name"] == "expired-service")

    assert gmail["gate_state"] == "inactive"
    assert gmail["allowed_by_client"] is True
    assert slack["gate_state"] == "active"
    assert slack["callable_now"] is True
    assert expired["gate_state"] == "blocked"
    assert expired["allowed_by_client"] is False


def test_build_mcp_tool_registry_keeps_remote_candidates_non_callable():
    registry = build_mcp_tool_registry(
        registry_servers=[
            {
                "name": "github/server",
                "title": "GitHub MCP",
                "description": "Repository automation",
                "source": "community",
                "remoteUrl": "https://example.invalid/mcp",
                "repositoryUrl": "https://github.com/example/server",
                "keywords": ["git", "repo"],
            }
        ]
    )

    assert registry["server_count"] == 0
    assert registry["candidate_count"] == 1
    candidate = registry["registry_candidates"][0]
    assert candidate["contract_kind"] == "mcp_registry_candidate"
    assert candidate["installed"] is False
    assert candidate["callable_now"] is False
    assert candidate["executed"] is False


def test_filter_mcp_registry_servers_filters_by_gate_and_client_policy():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "A", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
            {"name": "B", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
            {"name": "C", "mcp_config": {"type": "stdio"}, "auth_status": "expired"},
        ],
        active_mcps=["A"],
        allowed_tools=["mcp:A"],
    )

    active = filter_mcp_registry_servers(registry, gate_state="active")
    blocked_by_client = filter_mcp_registry_servers(registry, allowed_by_client=False)

    assert [server["server_name"] for server in active] == ["a"]
    assert [server["server_name"] for server in blocked_by_client] == ["b", "c"]


def test_search_mcp_tool_registry_matches_local_servers_and_candidates():
    registry = build_mcp_tool_registry(
        tools=[
            {
                "name": "Google Workspace",
                "description": "Gmail and Calendar",
                "mcp_config": {"type": "stdio"},
                "auth_status": "connected",
                "tool_permissions": {"query_gmail_emails": "ask"},
            }
        ],
        registry_servers=[
            {
                "name": "community/slack",
                "title": "Slack MCP",
                "description": "Send team chat messages",
                "keywords": ["chat"],
            }
        ],
    )

    gmail_results = search_mcp_tool_registry(registry, "gmail")
    slack_results = search_mcp_tool_registry(registry, "slack")

    assert gmail_results[0]["server_name"] == "google-workspace"
    assert slack_results[0]["server_name"] == "community-slack"
    assert slack_results[0]["contract_kind"] == "mcp_registry_candidate"


def test_summarize_mcp_tool_registry_is_compact_and_non_executing():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "A", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
            {"name": "B", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
        ],
        active_mcps=["A"],
        registry_servers=[{"name": "remote/candidate"}],
    )

    summary = summarize_mcp_tool_registry(registry)

    assert "MCP Registry:" in summary
    assert "servers=2" in summary
    assert "active=1" in summary
    assert "inactive=1" in summary
    assert "candidates=1" in summary
    assert "executed=False" in summary


def test_build_mcp_required_user_action_is_structured_for_deep_links():
    action = build_mcp_required_user_action(
        action_type="open_settings",
        target="tools/mcp/unity",
        label="Configure Unity MCP",
        reason="unity_mcp_not_configured",
        server_name="Unity MCP",
    )

    assert action["action_type"] == "open_settings"
    assert action["target"] == "tools/mcp/unity"
    assert action["label"] == "Configure Unity MCP"
    assert action["reason"] == "unity_mcp_not_configured"
    assert action["server_name"] == "unity-mcp"
    assert action["required"] is True
    assert action["executed"] is False


def test_inspect_mcp_server_contract_reports_activation_action():
    server = build_mcp_server_contract(
        name="Unity",
        mcp_config={"type": "stdio", "command": "unity-mcp"},
        enabled=True,
        auth_status="connected",
        active=False,
    )

    inspection = inspect_mcp_server_contract(server)

    assert inspection["contract_kind"] == "mcp_server_inspection"
    assert inspection["status"] == "needs_user_action"
    assert inspection["ready"] is False
    assert inspection["findings"][0]["code"] == "mcp_activation_required"
    assert inspection["required_user_actions"][0]["action_type"] == "activate_mcp"
    assert inspection["required_user_actions"][0]["target"] == "pending-actions/mcp/unity/activate"
    assert inspection["executed"] is False


def test_inspect_mcp_server_contract_reports_settings_action_for_blocked_auth():
    server = build_mcp_server_contract(
        name="Gmail",
        mcp_config={"type": "stdio", "command": "gmail-mcp"},
        enabled=True,
        auth_status="expired",
        active=False,
    )

    inspection = inspect_mcp_server_contract(server)

    assert inspection["status"] == "needs_user_action"
    assert any(finding["code"] == "mcp_auth_not_ready" for finding in inspection["findings"])
    assert any(action["action_type"] == "connect_account" for action in inspection["required_user_actions"])
    assert any(action["target"] == "tools/mcp/gmail/auth" for action in inspection["required_user_actions"])


def test_inspect_mcp_tool_registry_reports_missing_target_with_configure_action():
    registry = build_mcp_tool_registry(tools=[])

    inspection = inspect_mcp_tool_registry(registry, target_server_name="Unity")

    assert inspection["status"] == "needs_user_action"
    assert inspection["ready"] is False
    assert inspection["findings"][0]["code"] == "mcp_target_not_installed"
    assert inspection["required_user_actions"][0]["action_type"] == "open_settings"
    assert inspection["required_user_actions"][0]["target"] == "tools/mcp/unity"
    assert inspection["required_user_actions"][0]["label"] == "Configure Unity MCP"
    assert inspection["executed"] is False


def test_inspect_mcp_tool_registry_summarizes_ready_and_blocked_servers():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "Unity", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
            {"name": "Gmail", "mcp_config": {"type": "stdio"}, "auth_status": "expired"},
        ],
        active_mcps=["Unity"],
    )

    inspection = inspect_mcp_tool_registry(registry)
    summary = summarize_mcp_inspection(inspection)

    assert inspection["status"] == "needs_user_action"
    assert inspection["ready"] is False
    assert inspection["inspection_count"] == 2
    assert inspection["ready_count"] == 1
    assert inspection["needs_action_count"] == 1
    assert any(action["server_name"] == "gmail" for action in inspection["required_user_actions"])
    assert "MCP Inspection:" in summary
    assert "actions=2" in summary
    assert "executed=False" in summary


def test_estimate_mcp_definition_cost_is_deterministic_and_nonzero():
    server = build_mcp_server_contract(
        name="Unity",
        description="Unity Editor automation",
        mcp_config={"type": "stdio"},
        tool_permissions={"create_scene": "ask", "delete_asset": "deny"},
        active=True,
    )

    cost = estimate_mcp_definition_cost(server)

    assert cost > 160
    assert cost == estimate_mcp_definition_cost(server)


def test_score_mcp_server_for_budget_prioritizes_active_and_query_matches():
    active = build_mcp_server_contract(name="Unity", description="Unity Editor", active=True)
    inactive = build_mcp_server_contract(name="Gmail", description="Email", active=False)

    assert score_mcp_server_for_budget(active, query="unity") > score_mcp_server_for_budget(inactive, query="unity")


def test_build_mcp_tool_definition_budget_includes_high_priority_servers_first():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "Unity", "description": "Unity Editor", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
            {"name": "Gmail", "description": "Email", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
            {"name": "Slack", "description": "Chat", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
        ],
        active_mcps=["Unity"],
    )

    budget = build_mcp_tool_definition_budget(
        registry,
        max_definition_cost=600,
        max_servers=2,
        query="unity",
    )

    assert budget["contract_kind"] == "mcp_tool_definition_budget"
    assert budget["included_count"] >= 1
    assert budget["included_servers"][0]["server_name"] == "unity"
    assert budget["included_servers"][0]["callable_now"] is True
    assert budget["used_definition_cost"] <= 600
    assert budget["max_servers"] == 2
    assert budget["executed"] is False


def test_build_mcp_tool_definition_budget_defers_when_server_limit_is_hit():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "A", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
            {"name": "B", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
            {"name": "C", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
        ],
        active_mcps=["A"],
    )

    budget = build_mcp_tool_definition_budget(registry, max_definition_cost=5000, max_servers=1)

    assert budget["included_count"] == 1
    assert budget["deferred_count"] == 2
    assert all(item["defer_reason"] == "server_limit" for item in budget["deferred_servers"])


def test_build_mcp_tool_definition_budget_can_include_candidate_summaries():
    registry = build_mcp_tool_registry(
        registry_servers=[
            {"name": "community/unity", "title": "Unity MCP", "description": "Unity automation"},
            {"name": "community/blender", "title": "Blender MCP", "description": "Blender automation"},
        ]
    )

    budget = build_mcp_tool_definition_budget(registry, include_candidates=True, max_servers=1)

    assert budget["included_count"] == 0
    assert budget["candidate_count"] == 1
    assert budget["candidate_summaries"][0]["server_name"] == "community-unity"
    assert budget["candidate_summaries"][0]["callable_now"] is False


def test_summarize_mcp_tool_definition_budget_is_compact_and_non_executing():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "Unity", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
        ],
        active_mcps=["Unity"],
    )
    budget = build_mcp_tool_definition_budget(registry, max_definition_cost=1000)

    summary = summarize_mcp_tool_definition_budget(budget)

    assert "MCP Tool Definition Budget:" in summary
    assert "included=1" in summary
    assert "used=" in summary
    assert "executed=False" in summary


def test_build_mcp_fallback_adapter_contract_describes_cli_without_execution():
    adapter = build_mcp_fallback_adapter_contract(
        server_name="Unity",
        fallback_type="cli",
        command="unity",
        args=["-batchmode", "-projectPath", "."],
        reason="unity_mcp_not_available",
    )

    assert adapter["contract_kind"] == "mcp_fallback_adapter"
    assert adapter["server_name"] == "unity"
    assert adapter["fallback_type"] == "cli"
    assert adapter["state"] == "available"
    assert adapter["command"] == "unity"
    assert adapter["args"] == ["-batchmode", "-projectPath", "."]
    assert adapter["requires_user_approval"] is True
    assert adapter["executed"] is False


def test_build_mcp_fallback_adapter_contract_creates_setup_action_when_required():
    adapter = build_mcp_fallback_adapter_contract(
        server_name="Unity",
        fallback_type="script",
        script_path="tools/unity_bridge.py",
        requires_manual_setup=True,
    )

    assert adapter["state"] == "requires_user_action"
    assert adapter["required_user_actions"][0]["action_type"] == "open_settings"
    assert adapter["required_user_actions"][0]["target"] == "tools/mcp/unity/fallback"
    assert adapter["required_user_actions"][0]["label"] == "Configure Unity fallback"


def test_build_mcp_fallback_plan_selects_available_adapter_for_blocked_mcp():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "Unity", "mcp_config": {"type": "stdio"}, "auth_status": "expired"},
        ],
    )
    inspection = inspect_mcp_tool_registry(registry, target_server_name="Unity")
    adapter = build_mcp_fallback_adapter_contract(
        server_name="Unity",
        fallback_type="script",
        script_path="tools/unity_cli_adapter.py",
        reason="mcp_auth_expired",
    )

    plan = build_mcp_fallback_plan(
        inspection=inspection,
        fallback_adapters=[adapter],
        target_server_name="Unity",
    )

    assert plan["contract_kind"] == "mcp_fallback_plan"
    assert plan["status"] == "fallback_available"
    assert plan["fallback_available"] is True
    assert plan["selected_fallback"]["script_path"] == "tools/unity_cli_adapter.py"
    assert plan["executed"] is False


def test_build_mcp_fallback_plan_reports_not_needed_when_mcp_ready():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "Unity", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
        ],
        active_mcps=["Unity"],
    )
    inspection = inspect_mcp_tool_registry(registry, target_server_name="Unity")

    plan = build_mcp_fallback_plan(
        inspection=inspection,
        fallback_adapters=[
            build_mcp_fallback_adapter_contract(server_name="Unity", fallback_type="cli", command="unity")
        ],
        target_server_name="Unity",
    )

    assert plan["status"] == "not_needed"
    assert plan["fallback_available"] is True
    assert plan["executed"] is False


def test_build_mcp_fallback_plan_respects_cli_fallback_disabled():
    inspection = inspect_mcp_tool_registry(build_mcp_tool_registry(tools=[]), target_server_name="Unity")
    adapter = build_mcp_fallback_adapter_contract(server_name="Unity", fallback_type="cli", command="unity")

    plan = build_mcp_fallback_plan(
        inspection=inspection,
        fallback_adapters=[adapter],
        target_server_name="Unity",
        allow_cli_fallback=False,
    )

    assert plan["status"] == "blocked"
    assert plan["fallback_available"] is False
    assert plan["viable_count"] == 0


def test_summarize_mcp_fallback_plan_is_compact_and_non_executing():
    adapter = build_mcp_fallback_adapter_contract(server_name="Unity", fallback_type="cli", command="unity")
    plan = build_mcp_fallback_plan(
        inspection={"ready": False, "target_server_name": "unity"},
        fallback_adapters=[adapter],
        target_server_name="Unity",
    )

    summary = summarize_mcp_fallback_plan(plan)

    assert "MCP Fallback Plan:" in summary
    assert "status=fallback_available" in summary
    assert "target=unity" in summary
    assert "selected=cli" in summary
    assert "executed=False" in summary


def test_normalize_mcp_fallback_type_rejects_unknown_values():
    assert normalize_mcp_fallback_type("cli") == "cli"
    assert normalize_mcp_fallback_type("bad") == "none"
