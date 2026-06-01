from backend.apps.swarms.import_compatibility_runtime import (
    build_import_compatibility_report,
    detect_import_source,
    evaluate_import_policy_bridge,
    normalize_import_candidate,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source


def assert_inert(value):
    assert value.can_execute is False
    assert getattr(value, "can_install", False) is False
    if hasattr(value, "can_activate_mcp"):
        assert value.can_activate_mcp is False


def test_tool_schema_candidate_records_schema_sandbox_and_approval_plan():
    envelope = normalize_import_candidate({
        "source_format": "tool",
        "name": "Issue Writer",
        "source_author": "team",
        "source_license": "MIT",
        "source_uri": "file://tools/issue-writer.json",
        "source_hash": "hash",
        "tool_schema": {"type": "object", "properties": {"title": {"type": "string"}}},
        "side_effects": ["writes issue draft"],
        "required_approvals": ["human_review"],
    })
    candidate = envelope.normalized_candidate

    assert envelope.normalized_type == "ToolSpecCandidate"
    assert candidate["tool_schema"]["type"] == "object"
    assert candidate["tool_sandbox_plan"]["policy_matrix_required"] is True
    assert candidate["tool_sandbox_plan"]["dry_run_required"] is True
    assert candidate["tool_sandbox_plan"]["can_execute"] is False
    assert candidate["dry_run_validation_plan"]["execution_blocked"] is True
    assert "missing_validation_plan" in envelope.risk_flags
    assert_inert(envelope)

    report = build_import_compatibility_report(envelope)
    decision = evaluate_import_policy_bridge(envelope, report)
    assert decision.decision == "needs_review"
    assert decision.policy_matrix_required is True
    assert decision.shell_dialect_required is True
    assert decision.safeshell_required is True
    assert "review_tool_schema_compatibility" in decision.required_actions
    assert_inert(decision)


def test_mcp_server_config_candidate_never_activates_mcp():
    detection = detect_import_source({
        "raw_text": '{"mcpServers":{"docs":{"command":"node","args":["server.js"]}}}',
    })
    envelope = normalize_import_candidate({
        "source_format": "mcp_server",
        "name": "Docs MCP",
        "mcp_config": {"docs": {"command": "node", "args": ["server.js"]}},
    }, detection=detection)

    candidate = envelope.normalized_candidate
    decision = evaluate_import_policy_bridge(envelope)

    assert envelope.normalized_type == "MCPServerCandidate"
    assert candidate["mcp_config_candidate"]["activation_enabled"] is False
    assert candidate["mcp_config_candidate"]["can_activate_mcp"] is False
    assert candidate["tool_sandbox_plan"]["mcp_activation_guard_required"] is True
    assert decision.mcp_activation_guard_required is True
    assert "review_mcp_server_config_candidate" in decision.required_actions
    assert_inert(envelope)
    assert_inert(decision)


def test_api_docs_to_tool_candidate_blocks_api_calls():
    envelope = normalize_import_candidate({
        "source_format": "api_tool",
        "name": "Weather API Tool",
        "source_author": "team",
        "source_license": "MIT",
        "source_uri": "file://openapi/weather.yaml",
        "source_hash": "hash",
        "api_docs": "openapi: 3.0.0\npaths:\n  /weather:\n    get: {}",
        "validation_plan": {"dry_run": True},
        "evidence_contract": {"requires_preview": True},
    })
    candidate = envelope.normalized_candidate
    decision = evaluate_import_policy_bridge(envelope)

    assert envelope.normalized_type == "ApiToolCandidate"
    assert candidate["api_tool_candidate"]["can_call_api"] is False
    assert candidate["api_tool_candidate"]["external_provider_gate_required"] is True
    assert candidate["dry_run_validation_plan"]["api_call_blocked"] is True
    assert decision.external_provider_gate_required is True
    assert "confirm_no_api_calls_during_import" in decision.required_actions
    assert_inert(envelope)
    assert_inert(decision)


def test_tool_import_process_trace_includes_sandbox_and_dry_run_without_private_reasoning():
    envelope = normalize_import_candidate({
        "source_format": "tool",
        "name": "Filesystem Tool",
        "tool_schema": {"type": "object"},
        "side_effects": ["writes files"],
    })
    item = build_process_trace_item_from_source(envelope)

    assert item["subsystem"] == "ActionCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_install"] is False
    assert item["details"]["can_activate_mcp"] is False
    assert item["details"]["contains_private_reasoning"] is False
    assert item["details"]["tool_sandbox_plan"]["execution_blocked"] is not True or item["details"]["tool_sandbox_plan"]["can_execute"] is False
    assert item["details"]["dry_run_validation_plan"]["execution_blocked"] is True
