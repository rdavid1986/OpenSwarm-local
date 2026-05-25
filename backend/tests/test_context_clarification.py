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
