from backend.apps.agents.providers.claude_sdk_adapter import ClaudeSDKAdapter
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime import ProviderTurnContext


def test_claude_sdk_adapter_declares_existing_runtime_capabilities():
    adapter = ClaudeSDKAdapter(context_window=200_000)

    assert adapter.id == "claude-sdk"
    assert adapter.capabilities.supports_streaming is True
    assert adapter.capabilities.supports_tools is True
    assert adapter.capabilities.supports_parallel_tool_calls is True
    assert adapter.capabilities.context_window == 200_000


def test_ollama_adapter_declares_local_first_capabilities():
    adapter = OllamaAdapter(base_url="http://localhost:11434", context_window=32_000)

    assert adapter.id == "ollama"
    assert adapter.capabilities.supports_streaming is True
    assert adapter.capabilities.supports_tools is True
    assert adapter.capabilities.supports_json_mode is True
    assert adapter.capabilities.supports_structured_output is True
    assert adapter.capabilities.context_window == 32_000


def test_ollama_native_payload_strips_ollama_prefix_and_keeps_tools():
    adapter = OllamaAdapter(base_url="http://localhost:11434", api_mode="native")
    ctx = ProviderTurnContext(
        session_id="s1",
        model="ollama/qwen2.5-coder:14b",
        system_prompt="system",
        messages=[{"role": "user", "content": "hola"}],
        tools=[{"type": "function", "function": {"name": "Read"}}],
    )

    payload = adapter.build_request_payload(ctx, stream=True)

    assert payload["model"] == "qwen2.5-coder:14b"
    assert payload["stream"] is True
    assert payload["format"] == "json"
    assert payload["think"] is False
    assert payload["metadata"]["reasoning_effort"]["provider_support"] == "unsupported"
    assert payload["tools"] == [{"type": "function", "function": {"name": "Read"}}]
    assert payload["messages"][0] == {"role": "system", "content": "system"}


def test_ollama_openai_compatible_payload_shape():
    adapter = OllamaAdapter(base_url="http://localhost:11434", api_mode="openai-compatible")
    ctx = ProviderTurnContext(
        session_id="s1",
        model="ollama/qwen2.5-coder:14b",
        messages=[{"role": "user", "content": "hola"}],
    )

    payload = adapter.build_request_payload(ctx, stream=False)

    assert payload["model"] == "qwen2.5-coder:14b"
    assert payload["stream"] is False
    assert payload["response_format"] == {"type": "json_object"}


def test_ollama_adapter_response_events_include_safe_runtime_metadata():
    adapter = OllamaAdapter(base_url="http://localhost:11434", api_mode="native")
    ctx = ProviderTurnContext(
        session_id="s1",
        model="ollama/qwen3.6:latest",
        messages=[{"role": "user", "content": "hola"}],
        metadata={"supports_thinking": True, "reasoning_effort": "high", "structured_output": {"requested": True, "json_mode": True}},
    )

    events = adapter.parse_response_events(
        {
            "model": "qwen3.6:latest",
            "message": {"content": '{"answer":"ok"}'},
            "eval_count": 5,
            "eval_duration": 1_000_000_000,
        },
        ctx,
    )

    metadata = events[-1].payload["metadata"]
    assert metadata["metrics"]["tokens_per_second"] == 5.0
    assert metadata["reasoning_effort"]["requested_effort"] == "high"
    assert metadata["structured_output"]["validation_status"] == "valid"
