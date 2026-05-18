"""Minimal provider adapter interface for OpenSwarm.

Phase 3 goal:
- Define the provider boundary before moving Claude SDK or Ollama code.
- Keep the contract dependency-light and side-effect free.
- Let providers *propose* messages/tool calls while OpenSwarm runtimes execute
  tools, approvals, policy, session persistence, and tracing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Protocol


ProviderEventType = Literal[
    "provider_request",
    "provider_response",
    "message_delta",
    "message_final",
    "tool_requested",
    "error",
]


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declared capabilities for a concrete provider/model route."""

    supports_streaming: bool = False
    supports_tools: bool = False
    supports_json_mode: bool = False
    supports_structured_output: bool = False
    supports_parallel_tool_calls: bool = False
    supports_vision: bool = False
    context_window: int = 0


@dataclass(frozen=True)
class ProviderTurnContext:
    """Provider input for one model turn.

    The context references OpenSwarm-owned state but does not grant ownership
    of execution. Tool execution, approvals, policy checks, persistence, and
    trace emission remain outside the provider adapter.
    """

    session_id: str
    model: str
    messages: list[dict[str, Any]]
    system_prompt: str | None = None
    agent_id: str | None = None
    task_id: str | None = None
    provider_state: dict[str, Any] = field(default_factory=dict)
    runtime_state: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderEvent:
    """Normalized event emitted by provider adapters."""

    type: ProviderEventType
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    agent_id: str | None = None
    task_id: str | None = None


class ProviderAdapter(Protocol):
    """Minimal async provider adapter contract."""

    id: str
    capabilities: ProviderCapabilities

    async def run_turn(
        self,
        context: ProviderTurnContext,
    ) -> AsyncIterator[ProviderEvent]:
        """Run a single provider turn and yield normalized provider events."""
        ...
