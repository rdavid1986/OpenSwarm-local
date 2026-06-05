from backend.apps.swarms.model_assignment import build_phase_model_requirement
from backend.apps.swarms.task_envelope import build_task_envelope_from_swarm_input


def test_phase_model_requirement_prefers_phase_override():
    requirement = build_phase_model_requirement(
        phase="app_builder",
        risk_profile="low",
        side_effect_policy="none",
        available_context={
            "preferred_models": {
                "app_builder": "model-app-builder",
                "fallback": "model-fallback",
                "default": "model-default",
            }
        },
        trace_context={"source": "unit_test"},
    )

    data = requirement.as_dict()

    assert data["phase"] == "app_builder"
    assert data["suggested_model"] == "model-app-builder"
    assert data["selected_model"] == "model-app-builder"
    assert data["fallback_model"] == "model-fallback"
    assert data["risk_profile"] == "low"
    assert data["side_effect_policy"] == "none"
    assert data["metadata"]["phase"] == "app_builder"
    assert data["metadata"]["preferred_models"]["app_builder"] == "model-app-builder"


def test_task_envelope_embeds_phase_model_requirement():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Quiero crear una app para una peluquería",
        swarm_mode="app_builder",
        available_context={
            "preferred_models": {
                "app_builder": "model-app-builder",
                "fallback": "model-fallback",
            },
            "selected_model": "model-selected",
        },
    )

    data = envelope.as_dict()
    model_requirements = data["model_requirements"]
    phase_requirement = model_requirements["phase_model_requirement"]

    assert phase_requirement["phase"] == "app_builder"
    assert phase_requirement["suggested_model"] == "model-app-builder"
    assert phase_requirement["selected_model"] == "model-app-builder"
    assert phase_requirement["fallback_model"] == "model-fallback"
    assert model_requirements["suggested_model"] == "model-app-builder"
    assert model_requirements["fallback_model"] == "model-fallback"
    assert model_requirements["selected_model"] == "model-app-builder"


def test_task_envelope_preserves_explicit_model_requirements():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Quiero crear una landing para una peluquería",
        swarm_mode="app_builder",
        model_requirements={
            "phase_model_requirement": {
                "phase": "custom_phase",
                "suggested_model": "explicit-model",
                "fallback_model": "explicit-fallback",
                "selected_model": "explicit-model",
            },
            "suggested_model": "explicit-model",
            "fallback_model": "explicit-fallback",
            "selected_model": "explicit-model",
        },
    )

    data = envelope.as_dict()
    model_requirements = data["model_requirements"]

    assert model_requirements["phase_model_requirement"]["phase"] == "custom_phase"
    assert model_requirements["suggested_model"] == "explicit-model"
    assert model_requirements["fallback_model"] == "explicit-fallback"
    assert model_requirements["selected_model"] == "explicit-model"
