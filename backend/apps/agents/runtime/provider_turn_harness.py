"""Provider turn harness.

Runs an isolated provider/tool loop without touching AgentManager. Providers
emit normalized ProviderEvents; the harness detects tool calls, executes them
through ProviderToolBridge/ToolRuntime, appends provider-facing tool result
messages, and repeats until a final message or max_turns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

from backend.apps.agents.runtime.events import EventTraceRuntime, event_trace_runtime
from backend.apps.agents.runtime.provider import ProviderAdapter, ProviderEvent, ProviderTurnContext
from backend.apps.agents.runtime.provider_tool_bridge import ProviderToolBridge, provider_tool_bridge
from backend.apps.agents.runtime.tools import ToolExecutionContext

ProviderToolFormat = Literal["ollama", "openai_compatible"]
HarnessStatus = Literal["completed", "failed", "max_turns_exceeded"]


@dataclass(frozen=True)
class ProviderTurnHarnessResult:
    status: HarnessStatus
    messages: list[dict[str, Any]]
    final_message: dict[str, Any] | None = None
    tool_history: list[dict[str, Any]] = field(default_factory=list)
    turns: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    provider_events: list[dict[str, Any]] = field(default_factory=list)


class ProviderTurnHarness:
    def __init__(
        self,
        *,
        provider: ProviderAdapter,
        provider_tool_format: ProviderToolFormat = "ollama",
        bridge: ProviderToolBridge | None = None,
        events: EventTraceRuntime | None = None,
    ) -> None:
        self.provider = provider
        self.provider_tool_format = provider_tool_format
        self.bridge = bridge or provider_tool_bridge
        self.events = events or event_trace_runtime

    async def run_turn(
        self,
        *,
        context: ProviderTurnContext,
        workspace_path: str,
        messages: list[dict[str, Any]] | None = None,
        tool_history: list[dict[str, Any]] | None = None,
    ) -> ProviderTurnHarnessResult:
        base_messages = list(messages if messages is not None else context.messages)
        history = tool_history if tool_history is not None else []
        errors: list[dict[str, Any]] = []
        provider_events: list[dict[str, Any]] = []
        final_message: dict[str, Any] | None = None

        turn_context = self._context_with_messages(context, base_messages)
        async for event in self.provider.run_turn(turn_context):
            provider_events.append({"type": event.type, "payload": event.payload})
            self._trace(event, context)

            if event.type == "message_final":
                final_message = event.payload.get("message") or {
                    "role": "assistant",
                    "content": event.payload.get("content", ""),
                }
                base_messages.append(final_message)
                continue

            if event.type == "tool_requested":
                for raw_call in self._extract_tool_calls(event.payload):
                    try:
                        bridge_result = self.bridge.execute_provider_tool_call(
                            self.provider_tool_format,
                            raw_call,
                            self._tool_context(context, workspace_path),
                            history=history,
                        )
                        base_messages.append(bridge_result.provider_message)
                    except Exception as exc:
                        error = {"type": "tool_call_invalid", "error": str(exc), "raw_call": raw_call}
                        errors.append(error)
                        base_messages.append(self._error_tool_message(raw_call, error))

            if event.type == "error":
                errors.append({"type": "provider_error", "error": event.payload.get("error"), "payload": event.payload})

        status: HarnessStatus = "failed" if errors and final_message is None else "completed"
        return ProviderTurnHarnessResult(
            status=status,
            messages=base_messages,
            final_message=final_message,
            tool_history=list(history),
            turns=1,
            errors=errors,
            provider_events=provider_events,
        )

    async def run_until_final(
        self,
        *,
        context: ProviderTurnContext,
        workspace_path: str,
        max_turns: int = 8,
        tool_history: list[dict[str, Any]] | None = None,
    ) -> ProviderTurnHarnessResult:
        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")

        messages = list(context.messages)
        history = tool_history if tool_history is not None else []
        all_errors: list[dict[str, Any]] = []
        all_provider_events: list[dict[str, Any]] = []
        final_message: dict[str, Any] | None = None

        for turn_index in range(1, max_turns + 1):
            result = await self.run_turn(
                context=self._context_with_messages(context, messages),
                workspace_path=workspace_path,
                messages=messages,
                tool_history=history,
            )
            messages = result.messages
            all_errors.extend(result.errors)
            all_provider_events.extend(result.provider_events)
            if result.final_message is not None:
                final_message = result.final_message
                return ProviderTurnHarnessResult(
                    status="completed" if not all_errors else "failed",
                    messages=messages,
                    final_message=final_message,
                    tool_history=list(history),
                    turns=turn_index,
                    errors=all_errors,
                    provider_events=all_provider_events,
                )

        return ProviderTurnHarnessResult(
            status="max_turns_exceeded",
            messages=messages,
            final_message=None,
            tool_history=list(history),
            turns=max_turns,
            errors=[*all_errors, {"type": "max_turns_exceeded", "max_turns": max_turns}],
            provider_events=all_provider_events,
        )

    @staticmethod
    def _extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        raw = payload.get("tool_calls", payload.get("tool_call"))
        if raw is None:
            return []
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, dict):
            return [raw]
        return []

    @staticmethod
    def _context_with_messages(context: ProviderTurnContext, messages: list[dict[str, Any]]) -> ProviderTurnContext:
        return ProviderTurnContext(
            session_id=context.session_id,
            model=context.model,
            messages=list(messages),
            system_prompt=context.system_prompt,
            agent_id=context.agent_id,
            task_id=context.task_id,
            provider_state=dict(context.provider_state),
            runtime_state=dict(context.runtime_state),
            tools=list(context.tools),
            metadata=dict(context.metadata),
        )

    @staticmethod
    def _tool_context(context: ProviderTurnContext, workspace_path: str) -> ToolExecutionContext:
        return ToolExecutionContext(
            workspace_path=workspace_path,
            session_id=context.session_id,
            swarm_id=context.metadata.get("swarm_id"),
            agent_id=context.agent_id,
            task_id=context.task_id,
            allowed_tools=context.metadata.get("allowed_tools"),
            require_human_approval=bool(context.metadata.get("require_human_approval", False)),
            metadata={
                key: context.metadata[key]
                for key in (
                    "policy_scope",
                    "task_type",
                    "task_type_allowed_tools",
                    "agent_contract_allowed_tools",
                )
                if key in context.metadata
            },
        )

    def _trace(self, event: ProviderEvent, context: ProviderTurnContext) -> None:
        trace_type = "provider_response" if event.type in ("message_delta", "message_final", "tool_requested") else event.type
        if trace_type == "error":
            trace_type = "error"
        self.events.create(
            trace_type,
            session_id=context.session_id,
            swarm_id=context.metadata.get("swarm_id"),
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={"provider_event": event.type, **event.payload},
        )

    def _error_tool_message(self, raw_call: dict[str, Any], error: dict[str, Any]) -> dict[str, Any]:
        call_id = raw_call.get("id") or "invalid_tool_call"
        if self.provider_tool_format == "openai_compatible":
            import json

            return {
                "role": "tool",
                "tool_call_id": call_id,
                "name": raw_call.get("name") or (raw_call.get("function") or {}).get("name") or "unknown",
                "content": json.dumps({"ok": False, "status": "failed", "error": error}, ensure_ascii=False),
            }
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "tool_name": raw_call.get("name") or (raw_call.get("function") or {}).get("name") or "unknown",
            "content": {"ok": False, "status": "failed", "error": error},
        }


class FakeProviderAdapter:
    """Small provider for smoke tests.

    Each scripted item is one provider turn. An item may contain `tool_calls`,
    `final`, or `error`.
    """

    id = "fake-provider"
    capabilities = None

    def __init__(self, script: list[dict[str, Any]]) -> None:
        self.script = list(script)
        self.calls: list[ProviderTurnContext] = []

    async def run_turn(self, context: ProviderTurnContext) -> AsyncIterator[ProviderEvent]:
        self.calls.append(context)
        item = self.script.pop(0) if self.script else {"final": ""}
        yield ProviderEvent(type="provider_request", payload={"message_count": len(context.messages)}, session_id=context.session_id, agent_id=context.agent_id, task_id=context.task_id)
        if "error" in item:
            yield ProviderEvent(type="error", payload={"error": item["error"]}, session_id=context.session_id, agent_id=context.agent_id, task_id=context.task_id)
            return
        if "tool_calls" in item or "tool_call" in item:
            yield ProviderEvent(type="tool_requested", payload={"tool_calls": item.get("tool_calls") or item.get("tool_call")}, session_id=context.session_id, agent_id=context.agent_id, task_id=context.task_id)
            return
        final = item.get("final", "")
        message = final if isinstance(final, dict) else {"role": "assistant", "content": str(final)}
        yield ProviderEvent(type="message_final", payload={"message": message, "content": message.get("content", "")}, session_id=context.session_id, agent_id=context.agent_id, task_id=context.task_id)
