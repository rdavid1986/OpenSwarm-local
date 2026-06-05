from backend.apps.swarms.task_envelope import (
    build_task_envelope_from_swarm_input,
    dump_task_envelope,
    infer_input_modality,
    infer_side_effect_policy,
)


def test_task_envelope_accepts_specific_landing_request_without_extra_clarification():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Quiero crear una landing para una peluquería con horarios y WhatsApp",
        swarm_mode="app_builder",
        requested_outputs=["preview"],
        success_criteria=["mostrar horarios", "botón de WhatsApp"],
    )

    data = envelope.as_dict()

    assert data["mode"] == "app_builder"
    assert data["creation_type"] == "web"
    assert data["input_modality"] == "text"
    assert data["side_effect_policy"] == "none"
    assert data["risk_profile"] == "low"
    assert data["autonomy_level"] == "direct"
    assert data["clarification"]["needs_clarification"] is False
    assert data["clarification_budget"] == 3
    assert data["requested_outputs"] == ["preview"]
    assert data["success_criteria"] == ["mostrar horarios", "botón de WhatsApp"]


def test_task_envelope_keeps_clarification_for_generic_app_request():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Quiero crear una app",
        swarm_mode="app_builder",
    )

    data = envelope.as_dict()

    assert data["mode"] == "app_builder"
    assert data["creation_type"] == "unknown"
    assert data["clarification"]["needs_clarification"] is True
    assert data["clarification"]["reason"] == "creation_type_unclear"


def test_task_envelope_requires_approval_for_side_effect_requests():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Aplica los cambios y hace commit",
        swarm_mode="app_builder",
    )

    data = envelope.as_dict()

    assert data["side_effect_policy"] == "requires_approval"
    assert data["risk_profile"] == "medium"
    assert data["autonomy_level"] == "approval_required"


def test_task_envelope_blocks_destructive_requests():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Borrar todo el proyecto",
        swarm_mode="debug",
    )

    data = envelope.as_dict()

    assert data["side_effect_policy"] == "blocked"
    assert data["risk_profile"] == "high"
    assert data["autonomy_level"] == "approval_required"
    assert data["clarification_budget"] == 1


def test_task_envelope_detects_multimodal_artifact_refs():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Analiza esta captura y crea un plan",
        swarm_mode="plan",
        available_context={
            "artifact_refs": ["sediment://file_123", "sediment://file_123", "local://other"],
            "image_asset_pointer": "sediment://file_123",
        },
    )

    data = envelope.as_dict()

    assert data["input_modality"] == "multimodal"
    assert data["artifact_refs"] == ["sediment://file_123", "local://other"]


def test_task_envelope_normalizes_mode_alias_and_context_fields():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Quiero una web simple",
        swarm_mode="view-builder",
        available_context={
            "constraints": ["local-first", "local-first", "sin pagos"],
            "model_requirements": {"reasoning": "medium"},
            "clarification_budget": 4,
        },
    )

    data = dump_task_envelope(envelope)

    assert data["mode"] == "app_builder"
    assert data["constraints"] == ["local-first", "sin pagos"]
    assert data["model_requirements"] == {"reasoning": "medium"}
    assert data["clarification_budget"] == 4
    assert data["trace_context"]["source"] == "task_envelope"


def test_input_modality_and_side_effect_helpers_are_side_effect_free():
    assert infer_input_modality(user_message="", available_context={}) == "unknown"
    assert infer_input_modality(user_message="hola", available_context={}) == "text"
    assert infer_input_modality(user_message="", available_context={"files": ["a.py"]}) == "file"
    assert infer_input_modality(user_message="mira", available_context={"image": True}) == "multimodal"

    assert infer_side_effect_policy(user_message="solo explica", available_context={}) == "none"
    assert infer_side_effect_policy(user_message="instala esto", available_context={}) == "requires_approval"
    assert infer_side_effect_policy(user_message="borrar todo", available_context={}) == "blocked"
    assert infer_side_effect_policy(user_message="x", available_context={"side_effect_policy": "requires_approval"}) == "requires_approval"

def test_task_envelope_does_not_treat_informativa_as_format_side_effect():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Quiero una landing informativa para una peluquería con horarios y WhatsApp",
        swarm_mode="app_builder",
    )

    data = envelope.as_dict()

    assert data["creation_type"] == "web"
    assert data["side_effect_policy"] == "none"
    assert data["autonomy_level"] == "direct"


def test_task_envelope_still_blocks_explicit_format_side_effect():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Format drive and delete everything",
        swarm_mode="debug",
    )

    data = envelope.as_dict()

    assert data["side_effect_policy"] == "blocked"
    assert data["risk_profile"] == "high"
