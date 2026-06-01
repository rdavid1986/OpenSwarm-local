from backend.apps.swarms.external_provider_openrouter import (
    build_openrouter_model_catalog_snapshot,
    build_openrouter_provider_config,
    build_openrouter_schema_compatibility_report,
    build_openrouter_structured_output_contract,
    decide_openrouter_external_routing,
    evaluate_openrouter_privacy_gate,
    normalize_openrouter_model_catalog_entry,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def assert_openrouter_trace_is_safe(source):
    assert normalize_process_trace_source_kind(source) == "external_provider_openrouter"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "external_provider_openrouter"
    assert item["details"]["can_call_provider"] is False
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_use_server_tools"] is False
    assert item["details"]["external_call_performed"] is False
    return item


def test_process_trace_provider_config_is_configcore_blocked_and_safe():
    config = build_openrouter_provider_config(enabled=False, api_key_reference="sk-or-secret", metadata={"token": "leak"})

    item = assert_openrouter_trace_is_safe(config)
    rendered = str(item).lower()

    assert item["kind"] == "config"
    assert item["subsystem"] == "ConfigCore"
    assert item["status"] == "blocked"
    assert item["details"]["server_tools_disabled"] is True
    assert item["details"]["apply_patch_blocked"] is True
    assert "leak" not in rendered
    assert "sk-or-secret" not in rendered


def test_process_trace_model_catalog_uses_modelcore_without_calling_provider():
    entry = normalize_openrouter_model_catalog_entry({"model_id": "provider/model-a", "supports_zdr": True})
    snapshot = build_openrouter_model_catalog_snapshot([entry])

    item = assert_openrouter_trace_is_safe(snapshot)

    assert item["kind"] == "model"
    assert item["subsystem"] == "ModelCore"
    assert item["details"]["entry_count"] == 1


def test_process_trace_routing_decision_uses_policycore_and_requires_approval():
    config = build_openrouter_provider_config(enabled=True, api_key_reference="secret-store://openrouter/default")
    privacy = evaluate_openrouter_privacy_gate({"summary": "safe"}, zdr_required=True, zdr_allowed=True)
    decision = decide_openrouter_external_routing(
        {"requires_cloud_capability": True, "local_model_available": False, "local_model_sufficient": False},
        provider_config=config,
        privacy_gate=privacy,
        catalog_candidates=[{"model_id": "provider/model-a"}],
        user_approved=False,
        budget_approved=True,
    )

    item = assert_openrouter_trace_is_safe(decision)

    assert item["kind"] == "review"
    assert item["subsystem"] == "ReviewCore"
    assert item["status"] == "warning"
    assert item["details"]["user_approval_required"] is True
    assert item["details"]["budget_required"] is True


def test_process_trace_privacy_gate_redacts_payload_and_is_validationcore():
    gate = evaluate_openrouter_privacy_gate({"authorization": "Bearer secret", "summary": "ok"}, zdr_required=True, zdr_allowed=False)

    item = assert_openrouter_trace_is_safe(gate)
    rendered = str(item).lower()

    assert item["kind"] == "validation"
    assert item["subsystem"] == "ValidationCore"
    assert item["status"] == "blocked"
    assert item["details"]["secrets_redacted"] is True
    assert "authorization" not in item["details"]["safe_payload_preview"]
    assert "bearer secret" not in rendered


def test_process_trace_structured_output_compatibility_is_validationcore():
    contract = build_openrouter_structured_output_contract(schema_name="DagPlan", domain="dag_planner")
    model = normalize_openrouter_model_catalog_entry({"model_id": "provider/model-a", "supports_structured_outputs": True})
    report = build_openrouter_schema_compatibility_report(contract, model)

    item = assert_openrouter_trace_is_safe(report)

    assert item["kind"] == "validation"
    assert item["subsystem"] == "ValidationCore"
    assert item["status"] == "completed"
    assert item["details"]["schema_name"] == "DagPlan"
    assert item["details"]["supported_by_model"] is True
    assert item["details"]["apply_patch_blocked"] is True
