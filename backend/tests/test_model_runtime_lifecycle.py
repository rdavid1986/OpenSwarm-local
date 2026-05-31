from backend.apps.agents.runtime.model_runtime_lifecycle import (
    ContextBudgetInput,
    LongTaskHealthInput,
    ModelRuntimeRequest,
    RuntimeEscalationInput,
    attach_context_budget_to_model_runtime,
    attach_escalation_to_model_runtime,
    attach_long_task_health_to_model_runtime,
    attach_model_runtime_to_handoff,
    attach_model_runtime_to_task_packet,
    build_default_model_role_profiles,
    build_context_window_budget,
    build_model_runtime_trace_source,
    build_runtime_escalation_decision,
    dump_model_context_budget,
    dump_model_runtime_resolution,
    dump_runtime_escalation_decision,
    evaluate_long_task_model_health,
    extract_model_runtime_from_metadata,
    resolve_model_runtime,
)


def test_ollama_prefixed_model_resolves_local_runtime_with_inferred_metadata():
    resolution = resolve_model_runtime(ModelRuntimeRequest(requested_model="ollama/qwen2.5-coder:14b"))
    data = dump_model_runtime_resolution(resolution)

    assert data["provider_id"] == "ollama"
    assert data["model_id"] == "ollama/qwen2.5-coder:14b"
    assert data["local_model_name"] == "qwen2.5-coder:14b"
    assert data["context_limit"] is not None
    assert data["context_limit_source"] == "inferred"
    assert data["capability_source"]["tools"] in {"inferred", "reported", "not_reported"}


def test_local_model_without_prefix_defaults_to_ollama():
    resolution = resolve_model_runtime({"model": "qwen2.5-coder:14b"})

    assert resolution.provider_id == "ollama"
    assert resolution.local_model_name == "qwen2.5-coder:14b"
    assert resolution.model_id == "ollama/qwen2.5-coder:14b"


def test_explicit_provider_conflict_with_ollama_prefix_warns_and_prioritizes_ollama():
    resolution = resolve_model_runtime({"model": "ollama/qwen2.5-coder:14b", "provider": "openai"})

    assert resolution.provider_id == "ollama"
    assert "explicit_provider_conflicts_with_ollama_prefix" in resolution.warnings


def test_thinking_level_inherits_from_config():
    resolution = resolve_model_runtime(
        ModelRuntimeRequest(
            requested_model="qwen2.5-coder:14b",
            requested_thinking_level="inherit",
            effective_config={"default_thinking_level": "high"},
        ),
        local_registry={"ollama/qwen2.5-coder:14b": {"supports_thinking": True}},
    )

    assert resolution.thinking_level == "high"
    assert resolution.active_thinking is True


def test_no_thinking_support_disables_active_thinking_and_warns():
    resolution = resolve_model_runtime(
        {"model": "qwen2.5-coder:14b", "thinking_level": "high"},
        local_registry={"ollama/qwen2.5-coder:14b": {"supports_thinking": False}},
    )

    assert resolution.active_thinking is False
    assert "thinking_requested_but_not_supported" in resolution.warnings
    assert resolution.effective_options["metadata"]["reasoning_effort"]["provider_support"] == "unsupported"


def test_default_role_profiles_have_structured_planner_and_vision_requirements():
    profiles = build_default_model_role_profiles()

    assert profiles["planner_model"].requires_structured_output is True
    assert profiles["vision_model"].requires_vision is True


def test_attach_helpers_do_not_mutate_originals_and_can_extract_metadata():
    resolution = resolve_model_runtime({"model": "qwen2.5-coder:14b"})
    packet = {"task_id": "t1", "metadata": {"existing": True}}
    handoff = {"handoff_id": "h1"}

    packet_with_runtime = attach_model_runtime_to_task_packet(packet, resolution)
    handoff_with_runtime = attach_model_runtime_to_handoff(handoff, resolution)

    assert packet == {"task_id": "t1", "metadata": {"existing": True}}
    assert handoff == {"handoff_id": "h1"}
    assert packet_with_runtime["metadata"]["existing"] is True
    assert extract_model_runtime_from_metadata(packet_with_runtime["metadata"])["provider_id"] == "ollama"
    assert handoff_with_runtime["metadata"]["model_runtime"]["provider_id"] == "ollama"


def test_trace_source_is_safe_and_has_no_prompt_response_or_secrets():
    resolution = resolve_model_runtime({"model": "qwen2.5-coder:14b"})
    trace = build_model_runtime_trace_source(resolution)
    text = str(trace).lower()

    assert trace["source_kind"] == "model_runtime"
    for forbidden in ("prompt", "response", "raw_response", "secret", "token"):
        assert forbidden not in text


def test_unknown_model_without_config_is_auto_unresolved():
    resolution = resolve_model_runtime({})

    assert resolution.model_id == "auto"
    assert resolution.model_source == "auto_unresolved"
    assert "select_model" in resolution.required_actions


def test_variant_propagates_into_resolution_and_trace():
    resolution = resolve_model_runtime({"model": "qwen2.5-coder:14b", "variant": "planner-fast"})
    trace = build_model_runtime_trace_source(resolution)

    assert resolution.variant == "planner-fast"
    assert trace["variant"] == "planner-fast"



def _runtime_with_limit(limit=10000):
    return resolve_model_runtime({"model": "qwen2.5-coder:14b"}, local_registry={"ollama/qwen2.5-coder:14b": {"context_window": limit, "supports_thinking": True}})


def test_context_budget_within_budget():
    budget = build_context_window_budget(ContextBudgetInput(resolution=_runtime_with_limit(10000), estimated_input_tokens=1000, requested_output_tokens=500))

    assert budget.status == "within_budget"
    assert budget.usage_ratio is not None and budget.usage_ratio < 0.85


def test_context_budget_near_limit():
    budget = build_context_window_budget({"resolution": _runtime_with_limit(10000), "estimated_input_tokens": 7700, "requested_output_tokens": 500})

    assert budget.status == "near_limit"
    assert "context_budget_near_limit" in budget.warnings


def test_context_budget_over_limit():
    budget = build_context_window_budget({"resolution": _runtime_with_limit(10000), "estimated_input_tokens": 12000, "requested_output_tokens": 500})

    assert budget.status == "over_limit"
    assert "reduce_context_or_select_larger_model" in budget.required_actions


def test_context_budget_missing_context_limit():
    budget = build_context_window_budget({"resolution": {"provider_id": "unknown", "model_id": "custom"}, "estimated_input_tokens": 100})

    assert budget.status == "missing_context_limit"
    assert "context_limit_missing" in budget.warnings


def test_long_task_health_healthy_with_provider_ok_and_budget_within():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 1000, "requested_output_tokens": 500})
    health = evaluate_long_task_model_health(LongTaskHealthInput(resolution=resolution, context_budget=budget, provider_health={"ok": True, "status": "available"}))

    assert health.status == "healthy"
    assert health.can_continue is True
    assert health.should_pause is False


def test_long_task_health_provider_unavailable_blocks_continue():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 1000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": False, "status": "unavailable"}})

    assert health.status == "provider_unavailable"
    assert health.can_continue is False
    assert health.should_pause is True
    assert health.should_escalate is True


def test_long_task_health_context_over_limit_pauses_and_escalates():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 20000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": True}})

    assert health.status == "context_over_limit"
    assert health.should_pause is True
    assert health.should_escalate is True


def test_long_task_health_stream_stalled_detected():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 1000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": True}, "stream_last_event_ms_ago": 60000})

    assert health.status == "stream_stalled"
    assert "stream_stalled" in health.risks


def test_long_task_health_output_truncated_warns_and_escalates():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 1000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": True}, "output_truncated": True})

    assert health.status == "output_truncated"
    assert "output_truncated" in health.warnings
    assert health.should_escalate is True


def test_escalation_continue_current_model_when_healthy():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 1000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": True}})
    decision = build_runtime_escalation_decision(RuntimeEscalationInput(resolution=resolution, health=health, context_budget=budget))

    assert decision.decision == "continue_current_model"
    assert decision.allowed_without_approval is True


def test_escalation_suggest_installed_model_when_explicit_better_alternative_exists():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 12000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": True}})
    decision = build_runtime_escalation_decision({
        "resolution": resolution,
        "health": health,
        "context_budget": budget,
        "available_models": [{"model": "qwen2.5-coder:32b", "provider_id": "ollama", "context_window": 64000}],
    })

    assert decision.decision == "suggest_installed_model"
    assert decision.suggested_model_id == "ollama/qwen2.5-coder:32b"
    assert decision.requires_user_approval is True
    assert decision.allowed_without_approval is False


def test_escalation_blocked_no_safe_fallback_when_no_alternative():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 12000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": True}})
    decision = build_runtime_escalation_decision({"resolution": resolution, "health": health, "context_budget": budget, "available_models": []})

    assert decision.decision == "blocked_no_safe_fallback"
    assert decision.requires_user_approval is True


def test_fallback_never_allows_model_change_without_user_approval():
    decision = dump_runtime_escalation_decision({"decision": "suggest_installed_model", "suggested_model_id": "ollama/other", "requires_user_approval": False, "allowed_without_approval": True})

    assert decision["requires_user_approval"] is True
    assert decision["allowed_without_approval"] is False


def test_budget_health_escalation_attach_helpers_do_not_mutate_originals():
    resolution = dump_model_runtime_resolution(_runtime_with_limit(10000))
    original = dict(resolution)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 12000})
    health = evaluate_long_task_model_health({"resolution": resolution, "context_budget": budget, "provider_health": {"ok": True}})
    decision = build_runtime_escalation_decision({"resolution": resolution, "health": health, "context_budget": budget})

    with_budget = attach_context_budget_to_model_runtime(resolution, budget)
    with_health = attach_long_task_health_to_model_runtime(with_budget, health)
    with_decision = attach_escalation_to_model_runtime(with_health, decision)

    assert resolution == original
    assert with_decision["context_budget"]["status"] == "over_limit"
    assert with_decision["long_task_health"]["status"] == "context_over_limit"
    assert with_decision["escalation_decision"]["decision"] == "blocked_no_safe_fallback"


def test_budget_health_escalation_dump_and_trace_redact_sensitive_metadata():
    resolution = _runtime_with_limit(10000)
    budget = build_context_window_budget({"resolution": resolution, "estimated_input_tokens": 100, "metadata": {"secret_token": "leak", "prompt": "leak"}})
    runtime = attach_context_budget_to_model_runtime(resolution, budget)
    trace = build_model_runtime_trace_source(runtime)
    text = str({"budget": dump_model_context_budget(budget), "trace": trace}).lower()

    for forbidden in ("leak", "secret_token", "prompt", "response", "raw_response", "token"):
        assert forbidden not in text
