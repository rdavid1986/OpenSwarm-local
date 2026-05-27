from backend.apps.swarms.model_response_contract import (
    build_code_action_prompt_contract,
    build_model_response_contract_prompt,
    normalize_model_response_contract,
    validate_model_response_contract,
)


def test_model_response_contract_prompt_contains_required_fields():
    prompt = build_model_response_contract_prompt("context_clarification")

    for field in [
        "answer",
        "needs_clarification",
        "clarification_question",
        "next_action",
        "allowed_actions",
        "risks",
        "evidence_refs",
        "confidence",
        "reason",
    ]:
        assert field in prompt
    assert "Do not execute tools" in prompt


def test_normalize_model_response_contract_accepts_valid_dict():
    result = normalize_model_response_contract(
        {
            "answer": "Listo.",
            "needs_clarification": False,
            "clarification_question": None,
            "next_action": "no_action",
            "allowed_actions": ["no_action"],
            "risks": ["low_context"],
            "evidence_refs": ["artifact-1"],
            "confidence": 0.8,
            "reason": "Grounded.",
        }
    )

    assert result["answer"] == "Listo."
    assert result["needs_clarification"] is False
    assert result["next_action"] == "no_action"
    assert result["allowed_actions"] == ["no_action"]
    assert result["risks"] == ["low_context"]
    assert result["evidence_refs"] == ["artifact-1"]
    assert result["confidence"] == 0.8


def test_normalize_model_response_contract_accepts_json_string():
    result = normalize_model_response_contract(
        '{"answer":"Necesito el objetivo.","needs_clarification":true,"clarification_question":"¿Qué querés crear?","next_action":"ask_clarification","allowed_actions":["no_action","ask_clarification"],"risks":[],"evidence_refs":[],"confidence":0.7,"reason":"Falta objetivo."}'
    )

    assert result["needs_clarification"] is True
    assert result["clarification_question"] == "¿Qué querés crear?"
    assert result["next_action"] == "ask_clarification"


def test_normalize_model_response_contract_returns_safe_fallback_for_invalid_or_null():
    invalid = normalize_model_response_contract("not json", task_kind="debug")
    null = normalize_model_response_contract(None)

    assert invalid["needs_clarification"] is True
    assert invalid["next_action"] == "ask_clarification"
    assert invalid["confidence"] == 0.0
    assert invalid["evidence_refs"] == []
    assert null["next_action"] == "ask_clarification"


def test_normalize_model_response_contract_clamps_confidence():
    high = normalize_model_response_contract({"confidence": 2, "allowed_actions": ["no_action"], "next_action": "no_action"})
    low = normalize_model_response_contract({"confidence": -4, "allowed_actions": ["no_action"], "next_action": "no_action"})

    assert high["confidence"] == 1.0
    assert low["confidence"] == 0.0


def test_validate_model_response_contract_filters_disallowed_next_action():
    result = validate_model_response_contract(
        {
            "answer": "Voy a ejecutar.",
            "needs_clarification": False,
            "next_action": "run_implementation",
            "allowed_actions": ["run_implementation", "no_action"],
            "confidence": 0.9,
            "reason": "User asked.",
        },
        allowed_actions=["no_action", "ask_clarification"],
    )

    assert result["next_action"] == "ask_clarification"
    assert "run_implementation" not in result["allowed_actions"]
    assert result["allowed_actions"] == ["no_action", "ask_clarification"]


def test_validate_model_response_contract_uses_caller_allowed_fallback_when_safe_defaults_absent():
    result = validate_model_response_contract(
        {
            "next_action": "run_implementation",
            "allowed_actions": ["run_implementation"],
            "confidence": 0.9,
        },
        allowed_actions=["explain_only"],
    )

    assert result["next_action"] == "explain_only"
    assert result["allowed_actions"] == []


def test_normalize_model_response_contract_does_not_invent_evidence_refs():
    result = normalize_model_response_contract(
        {
            "answer": "Sin evidencia.",
            "next_action": "no_action",
            "allowed_actions": ["no_action"],
            "confidence": 0.9,
        }
    )

    assert result["evidence_refs"] == []


def test_low_confidence_prefers_safe_next_action():
    result = normalize_model_response_contract(
        {
            "answer": "Ejecutar.",
            "needs_clarification": False,
            "next_action": "run_implementation",
            "allowed_actions": ["run_implementation", "no_action", "ask_clarification"],
            "confidence": 0.1,
        }
    )

    assert result["next_action"] == "no_action"


def test_code_action_prompt_contract_requires_structured_non_executing_actions():
    prompt = build_code_action_prompt_contract()

    assert "Code action prompt contract" in prompt
    assert "Do not execute" in prompt
    assert "code_action contract" in prompt
    assert "affected_files" in prompt
    assert "suggested_commands" in prompt
    assert "expected_evidence" in prompt
    assert "execution_claim" in prompt
    assert "guards_required" in prompt


def test_model_response_contract_for_code_action_includes_code_action_contract():
    prompt = build_model_response_contract_prompt("code_action")

    assert "propose_code_action" in prompt
    assert "code_actions" in prompt
    assert "Code action prompt contract" in prompt
    assert "Do not claim files changed" in prompt
