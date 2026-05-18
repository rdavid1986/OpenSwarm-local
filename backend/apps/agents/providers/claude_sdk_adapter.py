"""Claude SDK provider adapter boundary.

Phase 4 intentionally keeps this adapter non-routed: AgentManager still owns
the production Claude SDK flow. This class gives the next refactor a stable
boundary without moving the sensitive SDK/session/tool/WS code yet.
"""

from __future__ import annotations

from typing import AsyncIterator

from backend.apps.agents.runtime import (
    ProviderCapabilities,
    ProviderEvent,
    ProviderTurnContext,
)


class ClaudeSDKAdapter:
    """Adapter declaration for the existing claude-agent-sdk runtime path."""

    id = "claude-sdk"

    def __init__(self, *, context_window: int = 200_000) -> None:
        self.capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_json_mode=False,
            supports_structured_output=False,
            supports_parallel_tool_calls=True,
            supports_vision=True,
            context_window=context_window,
        )

    @staticmethod
    def sdk_available() -> bool:
        """Return whether claude-agent-sdk can be imported in this env."""
        try:
            import claude_agent_sdk  # noqa: F401
            return True
        except Exception:
            return False

    async def run_turn(
        self,
        context: ProviderTurnContext,
    ) -> AsyncIterator[ProviderEvent]:
        """Reserved for the future routed Claude SDK path.

        The current production Claude flow is still in AgentManager. Raising
        here is safer than accidentally creating a second Claude execution
        path before Tool/Approval/Event runtimes are connected.
        """
        yield ProviderEvent(
            type="error",
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={
                "provider": self.id,
                "error": (
                    "ClaudeSDKAdapter is declared but not routed yet; "
                    "AgentManager still owns the current Claude SDK flow."
                ),
            },
        )
