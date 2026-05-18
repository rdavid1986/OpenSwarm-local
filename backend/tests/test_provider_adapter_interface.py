from dataclasses import FrozenInstanceError

import pytest

from backend.apps.agents.runtime import (
    ProviderCapabilities,
    ProviderEvent,
    ProviderTurnContext,
)


def test_provider_capabilities_are_explicit_and_immutable():
    caps = ProviderCapabilities(
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        supports_structured_output=False,
        supports_parallel_tool_calls=False,
        supports_vision=False,
        context_window=32_000,
    )

    assert caps.supports_streaming is True
    assert caps.supports_tools is True
    assert caps.context_window == 32_000

    with pytest.raises(FrozenInstanceError):
        caps.context_window = 1  # type: ignore[misc]


def test_provider_turn_context_keeps_runtime_ownership_outside_provider():
    ctx = ProviderTurnContext(
        session_id="s1",
        agent_id="a1",
        task_id="t1",
        model="ollama/qwen2.5-coder:14b",
        system_prompt="system",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"name": "Read"}],
    )

    assert ctx.session_id == "s1"
    assert ctx.agent_id == "a1"
    assert ctx.task_id == "t1"
    assert ctx.tools == [{"name": "Read"}]
    assert ctx.provider_state == {}
    assert ctx.runtime_state == {}


def test_provider_event_shape_supports_tool_requests_without_execution():
    event = ProviderEvent(
        type="tool_requested",
        session_id="s1",
        agent_id="a1",
        task_id="t1",
        payload={
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
        },
    )

    assert event.type == "tool_requested"
    assert event.payload["tool_name"] == "Read"
    assert event.payload["tool_input"]["file_path"] == "README.md"
