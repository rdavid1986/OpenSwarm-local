import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.apps.agents.models import AgentSession
from backend.apps.tools_lib.models import ToolDefinition


class FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


def _fake_mcp_tool(name="Unity"):
    return ToolDefinition(
        name=name,
        description=f"{name} MCP",
        mcp_config={"type": "stdio", "command": "python", "args": ["-m", f"{name.lower()}_mcp"]},
        auth_status="configured",
        enabled=True,
        tool_permissions={},
    )


def _json(response):
    return json.loads(response.body.decode())


@pytest.mark.asyncio
async def test_mcp_meta_activate_uses_guard_and_normalizes_server_name():
    from backend.main import mcp_meta
    from backend.apps.agents.agent_manager import agent_manager

    session = AgentSession(id="session-mcp-activate", name="MCP", model="sonnet", mode="agent")
    agent_manager.sessions[session.id] = session

    try:
        with patch("backend.apps.tools_lib.tools_lib._load_all", return_value=[_fake_mcp_tool("Unity")]), \
             patch("backend.apps.agents.ws_manager.ws_manager.send_to_session", new=AsyncMock()):
            response = await mcp_meta("activate", FakeRequest({
                "parent_session_id": session.id,
                "server_name": "Unity",
                "reason": "Need Unity tools.",
            }))
            data = _json(response)

        assert data["status"] == "activated"
        assert data["server_name"] == "unity"
        assert data["guard"]["decision"] == "requires_approval"
        assert data["guard"]["server_name"] == "unity"
        assert session.active_mcps == ["unity"]
        assert session.needs_fork is True
        assert session.pending_continuation is True
    finally:
        agent_manager.sessions.pop(session.id, None)


@pytest.mark.asyncio
async def test_mcp_meta_activate_preserves_unknown_server_response_before_blocked():
    from backend.main import mcp_meta
    from backend.apps.agents.agent_manager import agent_manager

    session = AgentSession(id="session-mcp-unknown", name="MCP", model="sonnet", mode="agent")
    agent_manager.sessions[session.id] = session

    try:
        with patch("backend.apps.tools_lib.tools_lib._load_all", return_value=[_fake_mcp_tool("Unity")]):
            response = await mcp_meta("activate", FakeRequest({
                "parent_session_id": session.id,
                "server_name": "Blender",
            }))
            data = _json(response)

        assert data["status"] == "unknown_server"
        assert data["available"] == ["unity"]
        assert data["guard"]["decision"] == "block"
        assert "server_not_in_registry" in data["guard"]["reasons"]
        assert session.active_mcps == []
    finally:
        agent_manager.sessions.pop(session.id, None)


@pytest.mark.asyncio
async def test_mcp_meta_activate_already_active_is_idempotent_and_returns_guard():
    from backend.main import mcp_meta
    from backend.apps.agents.agent_manager import agent_manager

    session = AgentSession(id="session-mcp-active", name="MCP", model="sonnet", mode="agent")
    session.active_mcps = ["unity"]
    agent_manager.sessions[session.id] = session

    try:
        with patch("backend.apps.tools_lib.tools_lib._load_all", return_value=[_fake_mcp_tool("Unity")]):
            response = await mcp_meta("activate", FakeRequest({
                "parent_session_id": session.id,
                "server_name": "unity",
            }))
            data = _json(response)

        assert data["status"] == "already_active"
        assert data["server_name"] == "unity"
        assert data["guard"]["decision"] == "already_active"
        assert session.active_mcps == ["unity"]
    finally:
        agent_manager.sessions.pop(session.id, None)
