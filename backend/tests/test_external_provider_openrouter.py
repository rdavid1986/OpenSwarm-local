from backend.apps.swarms.external_provider_openrouter import (
    build_openrouter_model_catalog_snapshot,
    build_openrouter_provider_config,
    build_openrouter_schema_compatibility_report,
    build_openrouter_structured_output_contract,
    decide_openrouter_external_routing,
    decide_openrouter_response_format,
    dump_openrouter_contract,
    evaluate_openrouter_privacy_gate,
    normalize_openrouter_model_catalog_entry,
    select_openrouter_catalog_candidates,
)


def test_provider_config_blocks_raw_api_key_server_tools_and_apply_patch():
    config = build_openrouter_provider_config(
        enabled=True,
        api_key_reference="sk-or-secret",
        allow_web_search=True,
        allow_web_fetch=True,
        allow_fusion=True,
        allow_apply_patch=True,
        zdr_required=False,
        metadata={"token": "leak", "safe": "ok"},
    )

    assert config.provider_id == "openrouter"
    assert config.can_call_provider is False
    assert config.can_execute is False
    assert config.can_use_server_tools is False
    assert config.external_call_performed is False
    assert config.server_tools_disabled is True
    assert config.apply_patch_blocked is True
    assert config.api_key_reference == ""
    assert "replace_raw_api_key_with_reference" in config.required_actions
    assert "disable_openrouter_server_tools_by_default" in config.required_actions
    assert "block_external_apply_patch" in config.required_actions
    assert "require_zdr_for_sensitive_tasks" in config.required_actions
    assert config.metadata["token"] == "[redacted]"


def test_provider_config_uses_reference_not_raw_secret():
    config = build_openrouter_provider_config(api_key_reference="secret-store://openrouter/default", scopes=["project", "agent", "bad"])
    policy = config.policy

    assert config.api_key_reference == "secret-store://openrouter/default"
    assert policy["scopes"] == ["project", "agent"]
    assert policy["allow_apply_patch"] is False
    assert policy["allow_web_search"] is False
    assert policy["can_call_provider"] is False


def test_model_catalog_snapshot_is_caller_provided_and_selects_candidates():
    entry = normalize_openrouter_model_catalog_entry(
        {
            "id": "provider/model-a",
            "name": "Model A",
            "context_length": "128000",
            "input_modalities": ["text", "image"],
            "supports_structured_outputs": True,
            "supports_zdr": True,
            "pricing_prompt": 0.1,
        }
    )
    snapshot = build_openrouter_model_catalog_snapshot([entry], stale_after="2026-06-02T00:00:00Z")
    candidates = select_openrouter_catalog_candidates(snapshot, requires_structured_outputs=True, requires_vision=True, requires_zdr=True)

    assert snapshot.source == "openrouter_catalog"
    assert snapshot.can_call_provider is False
    assert snapshot.external_call_performed is False
    assert snapshot.entry_count == 1
    assert candidates[0]["model_id"] == "provider/model-a"
    assert candidates[0]["can_call_provider"] is False


def test_routing_decision_keeps_local_first_and_blocks_without_gates():
    config = build_openrouter_provider_config(enabled=False, api_key_reference="secret-store://openrouter/default")
    privacy = evaluate_openrouter_privacy_gate({"task": "safe"}, zdr_required=True, zdr_allowed=False)

    decision = decide_openrouter_external_routing(
        {
            "task_kind": "debug",
            "requires_cloud_capability": True,
            "local_model_available": False,
            "local_model_sufficient": False,
            "requested_model_id": "provider/model-a",
        },
        provider_config=config,
        privacy_gate=privacy,
        catalog_candidates=[{"model_id": "provider/model-a"}],
        user_approved=False,
        budget_approved=False,
    )

    assert decision.local_first is True
    assert decision.external_allowed is False
    assert decision.can_call_provider is False
    assert decision.routing_status == "blocked"
    assert "provider_disabled" in decision.blockers
    assert "privacy_gate_not_passed" in decision.blockers
    assert "budget_approval_missing" in decision.blockers
    assert decision.selected_provider == "local"


def test_routing_decision_can_only_recommend_candidate_when_all_gates_pass():
    config = build_openrouter_provider_config(enabled=True, api_key_reference="secret-store://openrouter/default")
    privacy = evaluate_openrouter_privacy_gate({"summary": "safe"}, zdr_required=True, zdr_allowed=True)

    decision = decide_openrouter_external_routing(
        {
            "requires_cloud_capability": True,
            "local_model_available": True,
            "local_model_sufficient": False,
        },
        provider_config=config,
        privacy_gate=privacy,
        catalog_candidates=[{"model_id": "provider/model-a"}],
        user_approved=True,
        budget_approved=True,
    )

    assert decision.routing_status == "candidate"
    assert decision.selected_provider == "openrouter"
    assert decision.selected_model_id == "provider/model-a"
    assert decision.external_allowed is False
    assert decision.can_call_provider is False


def test_privacy_gate_redacts_and_blocks_sensitive_payload():
    gate = evaluate_openrouter_privacy_gate(
        {
            "api_key": "secret",
            "prompt": "raw internal prompt",
            "workspace_path": "C:/Users/name/project/file.py",
            "summary": "safe summary",
        },
        zdr_required=True,
        zdr_allowed=False,
    )

    assert gate.gate_status == "blocked"
    assert gate.can_call_provider is False
    assert gate.external_call_performed is False
    assert gate.redaction_applied is True
    assert gate.secrets_redacted is True
    assert gate.safe_payload_preview["api_key"] == "[redacted]"
    assert gate.safe_payload_preview["prompt"] == "[redacted]"
    assert gate.safe_payload_preview["summary"] == "safe summary"
    assert "zdr_required_not_allowed" in gate.blocked_reasons


def test_privacy_gate_passes_safe_payload_with_zdr_allowed():
    gate = evaluate_openrouter_privacy_gate({"summary": "safe"}, zdr_required=True, zdr_allowed=True)

    assert gate.gate_status == "passed"
    assert gate.zdr_required is True
    assert gate.zdr_allowed is True
    assert gate.can_call_provider is False


def test_structured_output_contract_and_compatibility_report():
    contract = build_openrouter_structured_output_contract(
        response_format="json_schema",
        schema_name="DebugDiagnosis",
        schema_version="v1",
        domain="debug_diagnosis",
        schema={"type": "object", "password": "leak"},
    )
    model = normalize_openrouter_model_catalog_entry({"model_id": "provider/model-a", "supports_structured_outputs": False})
    decision = decide_openrouter_response_format(contract, model)
    report = build_openrouter_schema_compatibility_report(contract, model)

    assert contract.can_call_provider is False
    assert contract.schema["password"] == "[redacted]"
    assert decision.supported_by_model is False
    assert decision.fallback_mode == "json_object"
    assert decision.can_call_provider is False
    assert report.status == "warning"
    assert report.validation_required is True
    assert report.can_call_provider is False
    assert "debug_diagnosis" in report.compatible_domains


def test_dump_openrouter_contract_sanitizes_dicts():
    dumped = dump_openrouter_contract({"token": "secret", "safe": "ok"})

    assert dumped["token"] == "[redacted]"
    assert dumped["safe"] == "ok"
