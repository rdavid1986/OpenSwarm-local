from backend.apps.agents.runtime.model_runtime_lifecycle import build_model_runtime_trace_source, resolve_model_runtime
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def test_process_trace_recognizes_model_runtime_source():
    resolution = resolve_model_runtime({"model": "qwen2.5-coder:14b", "thinking_level": "high"}, local_registry={"ollama/qwen2.5-coder:14b": {"supports_thinking": False}})
    source = build_model_runtime_trace_source(resolution)

    assert normalize_process_trace_source_kind(source) == "model_runtime"
    item = build_process_trace_item_from_source(source)

    assert item["kind"] == "model"
    assert item["subsystem"] == "ModelCore"
    assert item["status"] == "warning"
    assert item["details"]["source_kind"] == "model_runtime"
    assert item["details"]["can_execute_model"] is False


def test_process_trace_model_runtime_details_are_redacted():
    source = {
        "source_kind": "model_runtime",
        "runtime_kind": "model_runtime_resolution",
        "provider_id": "ollama",
        "model_id": "ollama/qwen2.5-coder:14b",
        "prompt": "do not leak",
        "raw_response": "do not leak",
        "secret_token": "do not leak",
    }

    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    assert item["subsystem"] == "ModelCore"
    for forbidden in ("do not leak", "prompt", "raw_response", "secret_token"):
        assert forbidden not in text
