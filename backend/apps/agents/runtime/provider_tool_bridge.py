"""Provider tool-call bridge.

Isolated adapter from provider-native tool-call payloads to ToolRuntime. This
module does not route AgentManager, Claude SDK, or the current Ollama inline
loop. It is a bench-tested bridge for future provider/session runtime wiring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.apps.agents.runtime.tool_mapping import map_tool_call
from backend.apps.agents.runtime.tools import (
    ToolCall,
    ToolExecutionContext,
    ToolResult,
    ToolRuntime,
    tool_runtime,
)

ProviderToolFormat = Literal["ollama", "openai_compatible"]


@dataclass(frozen=True)
class ProviderToolCallEnvelope:
    provider: ProviderToolFormat
    raw: dict[str, Any]
    normalized: ToolCall


@dataclass(frozen=True)
class ProviderToolBridgeResult:
    provider: ProviderToolFormat
    call: ProviderToolCallEnvelope
    result: ToolResult
    provider_message: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "raw_call": self.call.raw,
            "normalized_call": {
                "id": self.call.normalized.id,
                "name": self.call.normalized.name,
                "raw_name": self.call.normalized.raw_name,
                "provider_call_id": self.call.normalized.provider_call_id,
                "input": self.call.normalized.input,
            },
            "result": self.result.to_history_entry(),
            "provider_message": self.provider_message,
        }


class ProviderToolBridge:
    def __init__(self, *, tools: ToolRuntime | None = None) -> None:
        self.tools = tools or tool_runtime

    def normalize_provider_tool_call(
        self,
        provider: ProviderToolFormat,
        raw_call: dict[str, Any],
    ) -> ProviderToolCallEnvelope:
        if provider == "ollama":
            return self._normalize_ollama(raw_call)
        if provider == "openai_compatible":
            return self._normalize_openai_compatible(raw_call)
        raise ValueError(f"unsupported provider tool-call format: {provider}")

    def execute_provider_tool_call(
        self,
        provider: ProviderToolFormat,
        raw_call: dict[str, Any],
        context: ToolExecutionContext,
        *,
        history: list[dict[str, Any]] | None = None,
    ) -> ProviderToolBridgeResult:
        envelope = self.normalize_provider_tool_call(provider, raw_call)
        result = self.tools.execute_tool(envelope.normalized, context, history=history)
        provider_message = self.build_provider_tool_result_message(provider, envelope, result)
        return ProviderToolBridgeResult(
            provider=provider,
            call=envelope,
            result=result,
            provider_message=provider_message,
        )

    def build_provider_tool_result_message(
        self,
        provider: ProviderToolFormat,
        envelope: ProviderToolCallEnvelope,
        result: ToolResult,
    ) -> dict[str, Any]:
        payload = {
            "ok": result.ok,
            "status": result.status,
            "tool": result.tool_name,
            "result": result.result,
            "error": result.error,
        }
        if provider == "openai_compatible":
            return {
                "role": "tool",
                "tool_call_id": envelope.normalized.provider_call_id or envelope.normalized.id,
                "name": envelope.normalized.name,
                "content": json.dumps(payload, ensure_ascii=False),
            }
        return {
            "role": "tool",
            "tool_name": envelope.normalized.raw_name or envelope.normalized.name,
            "tool_call_id": envelope.normalized.provider_call_id or envelope.normalized.id,
            "content": json.dumps(payload, ensure_ascii=False),
        }

    @staticmethod
    def _normalize_ollama(raw_call: dict[str, Any]) -> ProviderToolCallEnvelope:
        if not isinstance(raw_call, dict):
            raise ValueError("raw tool call must be an object")
        function = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else None
        name = raw_call.get("name") or (function or {}).get("name")
        arguments = raw_call.get("arguments")
        if arguments is None and function is not None:
            arguments = function.get("arguments")
        tool_input = _coerce_arguments(arguments)
        normalized = map_tool_call(
            str(name or ""),
            tool_input,
            call_id=raw_call.get("id"),
            provider_call_id=raw_call.get("id"),
        )
        return ProviderToolCallEnvelope(provider="ollama", raw=raw_call, normalized=normalized)

    @staticmethod
    def _normalize_openai_compatible(raw_call: dict[str, Any]) -> ProviderToolCallEnvelope:
        if not isinstance(raw_call, dict):
            raise ValueError("raw tool call must be an object")
        function = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
        name = function.get("name") or raw_call.get("name")
        arguments = function.get("arguments", raw_call.get("arguments"))
        normalized = map_tool_call(
            str(name or ""),
            _coerce_arguments(arguments),
            call_id=raw_call.get("id"),
            provider_call_id=raw_call.get("id"),
        )
        return ProviderToolCallEnvelope(provider="openai_compatible", raw=raw_call, normalized=normalized)


def _coerce_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return dict(arguments)
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(f"tool arguments must be valid JSON object: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("tool arguments JSON must decode to an object")
        return parsed
    raise ValueError("tool arguments must be an object or JSON object string")


provider_tool_bridge = ProviderToolBridge()
