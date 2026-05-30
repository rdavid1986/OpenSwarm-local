"""Ollama provider adapter boundary.

Phase 5 declares Ollama as a first-class provider adapter without routing
AgentManager through it yet. The current inline Ollama loop remains untouched
until Tool Runtime, Approval Runtime, Policy Runtime, and Event/Trace Runtime
are connected.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, AsyncIterator, Literal

from backend.apps.agents.providers.ollama_runtime import (
    build_effective_ollama_request_options,
    build_ollama_runtime_metadata,
)
from backend.apps.agents.providers.provider_health import check_local_model_provider_health
from backend.apps.agents.runtime import (
    ProviderCapabilities,
    ProviderEvent,
    ProviderTurnContext,
)


OllamaApiMode = Literal["native", "openai-compatible"]


class OllamaAdapter:
    """Adapter declaration for local Ollama models."""

    id = "ollama"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_mode: OllamaApiMode = "native",
        context_window: int = 32_000,
        supports_vision: bool = False,
        allow_network: bool = False,
        supports_json_mode: bool = True,
    ) -> None:
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.api_mode: OllamaApiMode = api_mode
        self.allow_network = allow_network
        self.capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_json_mode=supports_json_mode,
            supports_structured_output=True,
            supports_parallel_tool_calls=False,
            supports_vision=supports_vision,
            context_window=context_window,
        )

    @property
    def native_chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    @property
    def openai_chat_url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def healthcheck(self, timeout_seconds: float = 2.0, model: str | None = None) -> dict[str, Any]:
        """Best-effort local Ollama availability check."""
        health = check_local_model_provider_health(model=model, base_url=self.base_url, timeout_seconds=timeout_seconds)
        # Backward compatibility for existing callers that look at ok/base_url/error/models.
        health.setdefault("error", "" if health.get("ok") else health.get("error_detail") or health.get("reason") or "")
        health.setdefault("models", [{"name": name} for name in health.get("available_models", [])])
        return health

    def build_request_payload(self, context: ProviderTurnContext, *, stream: bool = True) -> dict[str, Any]:
        """Build the provider request payload without executing it."""
        messages = []
        if context.system_prompt:
            messages.append({"role": "system", "content": context.system_prompt})
        messages.extend(context.messages)

        model = context.model
        if model.startswith("ollama/"):
            model = model[len("ollama/"):]

        reasoning_effort = (
            context.metadata.get("reasoning_effort")
            or context.runtime_state.get("reasoning_effort")
            or context.provider_state.get("reasoning_effort")
            or "auto"
        )
        structured_output = (
            context.metadata.get("structured_output")
            if isinstance(context.metadata.get("structured_output"), dict)
            else None
        )
        native_options = build_effective_ollama_request_options(
            requested_effort=str(reasoning_effort),
            supports_thinking=bool(context.metadata.get("supports_thinking") or context.provider_state.get("supports_thinking")),
            supports_thinking_levels=bool(context.metadata.get("supports_thinking_levels") or context.provider_state.get("supports_thinking_levels")),
            keep_alive=context.metadata.get("keep_alive") if isinstance(context.metadata.get("keep_alive"), str) else None,
            structured_output=structured_output,
            config_source="ProviderTurnContext.metadata",
        )

        if self.api_mode == "openai-compatible":
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": stream,
                "metadata": {"reasoning_effort": native_options.get("metadata", {}).get("reasoning_effort")},
            }
            if self.capabilities.supports_json_mode:
                payload["response_format"] = {"type": "json_object"}
            if context.tools:
                payload["tools"] = context.tools
            return payload

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "format": "json" if self.capabilities.supports_json_mode else None,
            "think": native_options.get("think"),
            "keep_alive": native_options.get("keep_alive"),
            "metadata": native_options.get("metadata"),
        }
        if native_options.get("format") is not None:
            payload["format"] = native_options.get("format")
        if context.tools:
            # Native Ollama has model-dependent tool support. The adapter only
            # proposes schemas; OpenSwarm Tool Runtime will execute calls.
            payload["tools"] = context.tools
        return {k: v for k, v in payload.items() if v is not None}

    def parse_response_events(self, response: dict[str, Any], context: ProviderTurnContext) -> list[ProviderEvent]:
        """Convert Ollama/native or OpenAI-compatible chat response to ProviderEvents."""
        if self.api_mode == "openai-compatible":
            choices = response.get("choices") or []
            message = (choices[0].get("message") if choices and isinstance(choices[0], dict) else {}) or {}
        else:
            message = response.get("message") or {}

        request_payload = self.build_request_payload(context, stream=False)
        runtime_metadata = build_ollama_runtime_metadata(
            response_payload=response,
            request_payload=request_payload,
            model=context.model,
        )
        tool_calls = message.get("tool_calls") or response.get("tool_calls") or []
        if not tool_calls and context.tools:
            extracted = self._extract_json_tool_call_from_content(message.get("content"), context)
            if extracted:
                tool_calls = [extracted]
        events: list[ProviderEvent] = [
            ProviderEvent(
                type="provider_response",
                session_id=context.session_id,
                agent_id=context.agent_id,
                task_id=context.task_id,
                payload={"provider": self.id, "api_mode": self.api_mode, "response": response, "metadata": runtime_metadata},
            )
        ]
        if tool_calls:
            events.append(
                ProviderEvent(
                    type="tool_requested",
                    session_id=context.session_id,
                    agent_id=context.agent_id,
                    task_id=context.task_id,
                    payload={"tool_calls": tool_calls, "metadata": {"tool_calls": runtime_metadata.get("tool_calls", [])}},
                )
            )
            return events

        events.append(
            ProviderEvent(
                type="message_final",
                session_id=context.session_id,
                agent_id=context.agent_id,
                task_id=context.task_id,
                payload={
                    "message": {
                        "role": message.get("role") or "assistant",
                        "content": message.get("content") or response.get("response") or "",
                    },
                    "metadata": runtime_metadata,
                },
            )
        )
        return events

    @staticmethod
    def _extract_json_tool_call_from_content(content: Any, context: ProviderTurnContext) -> dict[str, Any] | None:
        """Fallback for local models that emit a JSON tool call as content.

        Some Ollama models obey `format=json` by returning
        {"name": "...", "arguments": {...}} instead of native tool_calls.
        This keeps the path isolated to contexts that supplied tool schemas.
        """
        if not isinstance(content, str) or not content.strip():
            return None
        try:
            parsed = json.loads(content)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        function = parsed.get("function") if isinstance(parsed.get("function"), dict) else parsed
        name = function.get("name")
        arguments = function.get("arguments")
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return None

        allowed_names = set()
        for tool in context.tools:
            if isinstance(tool, dict):
                fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
                if fn.get("name"):
                    allowed_names.add(str(fn.get("name")))
        legacy_names = {"read_file", "write_file", "edit_file", "search_files", "search_text", "list_files"}
        if allowed_names and name not in allowed_names and name not in legacy_names:
            return None
        return {"name": name, "arguments": arguments}

    def execute_chat_request(self, context: ProviderTurnContext, *, timeout_seconds: float = 120.0) -> dict[str, Any]:
        """Execute one non-streaming Ollama chat request.

        This is opt-in via allow_network=True and is not used by AgentManager.
        """
        url = self.openai_chat_url if self.api_mode == "openai-compatible" else self.native_chat_url
        body = json.dumps(self.build_request_payload(context, stream=False)).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc

    async def run_turn(self, context: ProviderTurnContext) -> AsyncIterator[ProviderEvent]:
        """Run one opt-in Ollama turn.

        By default this remains non-routed to preserve existing behavior. Smoke
        tests or future experimental paths may instantiate allow_network=True.
        """
        yield ProviderEvent(
            type="provider_request",
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={
                "provider": self.id,
                "api_mode": self.api_mode,
                "base_url": self.base_url,
                "request": self.build_request_payload(context, stream=True),
                "routed": bool(self.allow_network),
            },
        )
        if self.allow_network:
            try:
                response = self.execute_chat_request(context)
                for event in self.parse_response_events(response, context):
                    yield event
            except Exception as exc:
                yield ProviderEvent(
                    type="error",
                    session_id=context.session_id,
                    agent_id=context.agent_id,
                    task_id=context.task_id,
                    payload={"provider": self.id, "error": str(exc)},
                )
            return

        yield ProviderEvent(
            type="error",
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={
                "provider": self.id,
                "error": (
                    "OllamaAdapter is declared but not routed yet; the existing "
                    "inline Ollama loop remains active until runtimes are connected."
                ),
            },
        )
