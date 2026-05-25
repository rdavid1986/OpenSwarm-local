from backend.apps.swarms.context_clarification import resolve_context_clarification


def test_context_clarification_accepts_specific_app_request():
    result = resolve_context_clarification(
        user_message="Quiero crear una landing para una peluquería con horarios y WhatsApp",
        swarm_mode="app_builder",
    )

    assert result["ok"] is True
    assert result["needs_clarification"] is False
    assert result["reason"] == "context_sufficient"


def test_context_clarification_asks_for_empty_message():
    result = resolve_context_clarification(user_message="", swarm_mode="ask")

    assert result["ok"] is False
    assert result["needs_clarification"] is True
    assert result["reason"] == "empty_user_message"


def test_context_clarification_asks_for_vague_project_mode_request():
    result = resolve_context_clarification(user_message="hacelo", swarm_mode="plan")

    assert result["ok"] is False
    assert result["needs_clarification"] is True
    assert result["reason"] == "project_mode_request_too_vague"


def test_context_clarification_asks_for_debug_target_without_context():
    result = resolve_context_clarification(user_message="debug este error", swarm_mode="debug")

    assert result["ok"] is False
    assert result["needs_clarification"] is True
    assert result["reason"] == "debug_request_without_target_context"


def test_context_clarification_allows_debug_when_context_exists():
    result = resolve_context_clarification(
        user_message="debug este error",
        swarm_mode="debug",
        available_context={"logs": "Traceback..."},
    )

    assert result["ok"] is True
    assert result["needs_clarification"] is False


def test_context_clarification_uses_mode_specific_empty_question():
    result = resolve_context_clarification(user_message="", swarm_mode="skill_builder")

    assert result["clarification_question"] == "¿Qué skill querés crear o mejorar?"


def test_context_clarification_uses_mode_specific_vague_question():
    result = resolve_context_clarification(user_message="continuar", swarm_mode="app_builder")

    assert result["clarification_question"] == "¿Qué tipo de app o web querés construir?"


def test_context_clarification_returns_options_with_custom_choice():
    result = resolve_context_clarification(user_message="hacelo", swarm_mode="app_builder")

    assert result["needs_clarification"] is True
    assert result["clarification_options"][-1] == {"label": "Otra opción", "value": "__custom__", "kind": "custom"}
    assert {"label": "Landing simple", "value": "landing simple", "kind": "recommended"} in result["clarification_options"]


def test_context_clarification_success_returns_empty_options():
    result = resolve_context_clarification(
        user_message="Quiero una landing para una peluquería",
        swarm_mode="app_builder",
    )

    assert result["needs_clarification"] is False
    assert result["clarification_options"] == []


def test_context_clarification_marks_possible_options():
    result = resolve_context_clarification(user_message="hacelo", swarm_mode="debug")

    assert {"label": "Revisar archivo", "value": "revisar archivo", "kind": "possible"} in result["clarification_options"]


def test_context_clarification_returns_pending_state():
    result = resolve_context_clarification(user_message="hacelo", swarm_mode="plan")
    state = result["clarification_state"]

    assert state["status"] == "pending_clarification"
    assert state["clarification_id"]
    assert state["mode"] == "plan"
    assert state["reason"] == "project_mode_request_too_vague"
    assert state["question"] == result["clarification_question"]
    assert state["options"] == result["clarification_options"]


def test_context_clarification_success_returns_empty_state():
    result = resolve_context_clarification(
        user_message="Quiero una landing para una peluquería",
        swarm_mode="app_builder",
    )

    assert result["clarification_state"] == {}
