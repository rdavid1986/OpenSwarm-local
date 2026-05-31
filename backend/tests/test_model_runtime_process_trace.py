from backend.apps.agents.runtime.model_runtime_lifecycle import (
    attach_context_budget_to_model_runtime,
    attach_escalation_to_model_runtime,
    attach_long_task_health_to_model_runtime,
    build_context_window_budget,
    build_model_runtime_trace_source,
    build_runtime_escalation_decision,
    evaluate_long_task_model_health,
    resolve_model_runtime,
)
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



def test_process_trace_modelcore_includes_budget_health_and_escalation_summaries():
    resolution = resolve_model_runtime({"model": "qwen2.5-coder:14b"}, local_registry={"ollama/qwen2.5-coder:14b": {"context_window": 10000}})
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 12000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": True}})
    decision = build_runtime_escalation_decision({
        "resolution": resolution,
        "context_budget": budget,
        "health": health,
        "available_models": [{"model": "qwen2.5-coder:32b", "provider_id": "ollama", "context_window": 64000}],
    })
    runtime = attach_escalation_to_model_runtime(attach_long_task_health_to_model_runtime(attach_context_budget_to_model_runtime(resolution, budget), health), decision)
    item = build_process_trace_item_from_source(build_model_runtime_trace_source(runtime))

    assert item["subsystem"] == "ModelCore"
    assert item["details"]["context_budget"]["status"] == "over_limit"
    assert item["details"]["long_task_health"]["status"] == "context_over_limit"
    assert item["details"]["escalation_decision"]["decision"] == "suggest_installed_model"


def test_process_trace_model_runtime_extended_details_are_redacted():
    source = {
        "source_kind": "model_runtime",
        "runtime_kind": "model_runtime_resolution",
        "provider_id": "ollama",
        "model_id": "ollama/qwen2.5-coder:14b",
        "context_budget": {"status": "within_budget", "prompt": "leak"},
        "long_task_health": {"status": "healthy", "response": "leak"},
        "escalation_decision": {"decision": "continue_current_model", "secret_token": "leak"},
    }

    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    for forbidden in ("leak", "prompt", "response", "raw_response", "secret_token"):
        assert forbidden not in text


def test_process_trace_status_reflects_escalation_warning():
    source = {
        "source_kind": "model_runtime",
        "runtime_kind": "model_runtime_resolution",
        "provider_id": "ollama",
        "model_id": "ollama/qwen2.5-coder:14b",
        "warnings": ["model_change_suggestion_not_applied"],
        "escalation_decision": {"decision": "suggest_installed_model", "requires_user_approval": True},
    }

    item = build_process_trace_item_from_source(source)

    assert item["status"] == "warning"
    assert item["details"]["escalation_requires_user_approval"] is True
