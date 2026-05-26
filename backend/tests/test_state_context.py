import json

from backend.apps.swarms.state_context import (
    build_state_context_payload,
    build_state_context_prompt,
    normalize_state_context_value,
)


def test_state_context_payload_normalizes_missing_fields_without_inventing():
    payload = build_state_context_payload()

    assert payload["mode"] == "missing"
    assert payload["route"] == "missing"
    assert payload["user_message"] == "missing"
    assert payload["creation_type"] == "unknown"
    assert payload["project_intake_status"] == "missing"
    assert payload["pending_action_type"] is None
    assert payload["has_pending_action"] is False
    assert payload["output_id"] is None
    assert payload["candidate_iteration_id"] is None
    assert payload["has_candidate_iteration"] is False
    assert payload["evidence_status"] == "missing"
    assert payload["artifact_count"] == 0
    assert payload["provider_health_status"] == "missing"
    assert payload["model_name"] == "missing"
    assert payload["guard_status"] == "missing"
    assert payload["available_context_summary"]["status"] == "missing"


def test_state_context_payload_preserves_core_fields_and_context_summary():
    payload = build_state_context_payload(
        mode="app_builder",
        route="context_clarification",
        user_message="Quiero crear una landing",
        creation_type="web",
        available_context={
            "project_intake_status": "collecting",
            "pending_action": "answer_project_intake",
            "preview_output_id": "out-1",
            "candidate_iteration_id": "iter-1",
            "artifact_count": 2,
            "provider_health": {"status": "available", "model": "qwen2.5-coder:14b"},
            "claim_guard_status": "verified",
        },
    )

    assert payload["mode"] == "app_builder"
    assert payload["route"] == "context_clarification"
    assert payload["user_message"] == "Quiero crear una landing"
    assert payload["creation_type"] == "web"
    assert payload["project_intake_status"] == "collecting"
    assert payload["pending_action_type"] == "answer_project_intake"
    assert payload["has_pending_action"] is True
    assert payload["output_id"] == "out-1"
    assert payload["candidate_iteration_id"] == "iter-1"
    assert payload["has_candidate_iteration"] is True
    assert payload["artifact_count"] == 2
    assert payload["provider_health_status"] == "available"
    assert payload["model_name"] == "qwen2.5-coder:14b"
    assert payload["guard_status"] == "verified"
    assert "preview_output_id" in payload["available_context_summary"]["keys"]


def test_state_context_prompt_explains_missing_and_unknown_semantics():
    payload = build_state_context_payload(mode="debug", user_message="debug")
    prompt = build_state_context_prompt(payload)

    assert "missing/null/empty fields" in prompt
    assert "unknown fields" in prompt
    assert "guards authorize or block actions" in prompt
    assert '"mode": "debug"' in prompt


def test_normalize_state_context_value_is_json_safe_and_bounded():
    normalized = normalize_state_context_value(
        {
            "long": "x" * 1000,
            "items": list(range(20)),
            "nested": {"b": 2, "a": None},
        }
    )

    assert len(normalized["long"]) == 600
    assert len(normalized["items"]) == 12
    assert normalized["nested"] == {"a": None, "b": 2}
    json.dumps(normalized)
