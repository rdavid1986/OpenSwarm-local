from backend.apps.agents.runtime.model_runtime_lifecycle import (
    ModelRuntimeRequest,
    attach_model_runtime_to_handoff,
    attach_model_runtime_to_task_packet,
    build_default_model_role_profiles,
    build_model_runtime_trace_source,
    dump_model_runtime_resolution,
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
