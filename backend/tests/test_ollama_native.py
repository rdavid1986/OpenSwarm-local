from backend.apps.agents.providers.ollama_native import (
    build_embedding_request,
    build_keep_alive_policy,
    build_modelfile_role_profile,
    build_ollama_capability_snapshot_from_payloads,
    build_ollama_chat_options,
    build_structured_output_request,
    fetch_ollama_capability_snapshot,
    normalize_embedding_response,
    normalize_ollama_runtime_metrics,
    normalize_ollama_stream_chunks,
    normalize_ollama_thinking_metadata,
    normalize_ollama_tool_calls,
    normalize_openai_compatibility_adapter_metadata,
    normalize_reasoning_effort,
    normalize_vision_attachment,
    validate_structured_output,
)


def test_build_ollama_capability_snapshot_from_payloads_normalizes_reported_and_inferred_data():
    snapshot = build_ollama_capability_snapshot_from_payloads(
        base_url="http://localhost:11434/",
        version_payload={"version": "0.6.0"},
        tags_payload={
            "models": [
                {
                    "name": "qwen3.6:latest",
                    "modified_at": "2026-05-30T10:00:00Z",
                    "size": 123,
                    "digest": "abc",
                }
            ]
        },
        show_payloads={
            "qwen3.6:latest": {
                "details": {
                    "family": "qwen35moe",
                    "families": ["qwen35moe"],
                    "format": "gguf",
                    "parameter_size": "36B",
                    "quantization_level": "Q4_K_M",
                },
                "model_info": {"qwen35moe.context_length": 262144},
                "capabilities": ["tools"],
            }
        },
        ps_payload={"models": [{"name": "qwen3.6:latest", "expires_at": "2026-05-30T10:10:00Z"}]},
    )

    model = snapshot["models"][0]
    assert snapshot["provider"] == "ollama"
    assert snapshot["base_url"] == "http://localhost:11434"
    assert snapshot["version"] == "0.6.0"
    assert model["model"] == "qwen3.6:latest"
    assert model["family"] == "qwen35moe"
    assert model["context_window"] == 262144
    assert model["supports_tools"] is True
    assert model["capabilities"]["tools"]["source"] == "reported"
    assert model["supports_thinking"] is True
    assert model["capabilities"]["thinking"]["source"] == "inferred"
    assert model["running"] is True
    assert model["expires_at"] == "2026-05-30T10:10:00Z"


def test_fetch_ollama_capability_snapshot_uses_injected_request_json_without_real_ollama():
    calls = []

    def fake_request_json(url, *, method="GET", body=None, timeout_seconds=2.0):
        calls.append((url, method, body, timeout_seconds))
        if url.endswith("/api/version"):
            return {"version": "0.6.0"}
        if url.endswith("/api/tags"):
            return {"models": [{"name": "nomic-embed-text:latest"}]}
        if url.endswith("/api/ps"):
            return {"models": []}
        if url.endswith("/api/show"):
            assert method == "POST"
            return {"details": {"family": "nomic-embed"}, "capabilities": ["embedding"]}
        return {}

    snapshot = fetch_ollama_capability_snapshot(base_url="http://ollama.local", request_json=fake_request_json)

    assert snapshot["health"] == "available"
    assert snapshot["models"][0]["supports_embedding"] is True
    assert any(call[0].endswith("/api/show") for call in calls)


def test_reasoning_effort_maps_to_boolean_think_when_levels_not_reported():
    unsupported = normalize_reasoning_effort("high", supports_thinking=False)
    supported = normalize_reasoning_effort("xhigh", supports_thinking=True, supports_levels=False)
    off = normalize_reasoning_effort("off", supports_thinking=True)

    assert unsupported["applied_level"] == "off"
    assert unsupported["ollama_think"] is False
    assert supported["ollama_think"] is True
    assert supported["source"] == "degraded_to_boolean_think"
    assert off["ollama_think"] is False


def test_build_ollama_chat_options_combines_thinking_keep_alive_and_structured_output():
    options = build_ollama_chat_options(
        reasoning_effort="medium",
        supports_thinking=True,
        keep_alive="10m",
        structured_output={"requested": True, "schema": {"type": "object"}},
    )

    assert options["think"] is True
    assert options["keep_alive"] == "10m"
    assert options["format"] == {"type": "object"}
    assert options["metadata"]["structured_output"]["schema_used"] is True


def test_stream_chunk_parser_separates_thinking_content_tool_calls_and_metrics():
    parsed = normalize_ollama_stream_chunks(
        [
            {"message": {"thinking": "private native thinking ", "content": "Hello "}},
            {"message": {"content": "world", "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "a.py", "api_key": "secret"}}}]}},
            {"total_duration": 2_000_000_000, "load_duration": 1, "eval_count": 10, "eval_duration": 1_000_000_000},
        ]
    )

    assert parsed["thinking"] == "private native thinking "
    assert parsed["content"] == "Hello world"
    assert parsed["thinking_visible_to_user"] is False
    assert parsed["thinking_metadata"]["thinking_redacted"] is True
    assert parsed["tool_calls"][0]["tool_name"] == "read_file"
    assert parsed["tool_calls"][0]["arguments"]["api_key"] == "[redacted]"
    assert parsed["metrics"]["tokens_per_second"] == 10.0


def test_tool_call_and_runtime_metric_normalizers_are_safe_and_calculate_throughput():
    calls = normalize_ollama_tool_calls([{"id": "call1", "function": {"name": "search", "arguments": {"query": "x"}}}])
    metrics = normalize_ollama_runtime_metrics(
        {
            "model": "qwen",
            "total_duration": 3_000_000_000,
            "load_duration": 100,
            "prompt_eval_count": 5,
            "prompt_eval_duration": 1_000_000_000,
            "eval_count": 20,
            "eval_duration": 2_000_000_000,
        }
    )

    assert calls == [{"tool_call_id": "call1", "tool_name": "search", "arguments": {"query": "x"}, "source": "ollama_native_tool_calls", "status": "requested"}]
    assert metrics["tokens_per_second"] == 10.0
    assert metrics["cold_start_likely"] is True


def test_thinking_metadata_never_exposes_raw_thinking_by_default():
    metadata = normalize_ollama_thinking_metadata("private chain of thought", safe_summary="safe")

    assert metadata["has_native_thinking"] is True
    assert metadata["thinking_redacted"] is True
    assert metadata["thinking_summary"] == "safe"
    assert metadata["visible_to_user"] is False


def test_structured_output_request_and_validation_contracts():
    request = build_structured_output_request(requested=True, json_mode=True)
    valid = validate_structured_output('{"answer":"ok","secret":"hidden"}')
    invalid = validate_structured_output("not json")

    assert request["format"] == "json"
    assert request["metadata"]["structured_output"]["applied"] is True
    assert valid["validation_status"] == "valid"
    assert valid["value"]["secret"] == "[redacted]"
    assert invalid["validation_status"] == "invalid"


def test_embedding_bridge_contracts_truncate_input_and_report_dimensions():
    request = build_embedding_request(model="ollama/nomic-embed-text:latest", input_text="x" * 9000, keep_alive="5m")
    result = normalize_embedding_response({"embeddings": [[0.1, 0.2, 0.3]], "eval_count": 1}, model="nomic-embed-text:latest")

    assert request["model"] == "nomic-embed-text:latest"
    assert len(request["input"]) == 8000
    assert request["keep_alive"] == "5m"
    assert result["dimensions"] == 3
    assert result["embedding_count"] == 1


def test_vision_keep_alive_modelfile_and_compatibility_contracts():
    vision = normalize_vision_attachment({"mime_type": "image/png", "size": 12, "data": "base64", "metadata": {"token": "secret", "safe": True}})
    keep_alive = build_keep_alive_policy("30m", running_model={"expires_at": "soon"})
    profile = build_modelfile_role_profile("Reviewer")
    compat = normalize_openai_compatibility_adapter_metadata(native_snapshot={"provider": "ollama"}, used_compatibility=True)

    assert vision["base64_present"] is True
    assert vision["metadata"] == {"token": "[redacted]", "safe": True}
    assert keep_alive["running"] is True
    assert profile["role"] == "Reviewer"
    assert "Does not run ollama create automatically." in profile["risk_notes"]
    assert compat["api_mode"] == "openai-compatible"
    assert compat["capability_source"] == "native_ollama_snapshot"
    assert compat["compatibility_is_primary_capability_source"] is False
