from backend.apps.agents.runtime.policy_matrix_runtime import (
    build_policy_matrix_trace_source,
    build_provider_model_resource_policy,
    build_tool_permission_contract,
    evaluate_policy_matrix_decision,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def test_process_trace_recognizes_policy_matrix_runtime_allowed():
    tool = build_tool_permission_contract(tool_name="Read", permission_policy="always_allow", allowed_tools=["Read"], risk_level="low")
    provider = build_provider_model_resource_policy(provider_id="ollama", model_id="qwen")
    decision = evaluate_policy_matrix_decision(tool_permission=tool, provider_policy=provider)
    source = build_policy_matrix_trace_source(decision=decision)

    assert normalize_process_trace_source_kind(source) == "policy_matrix_runtime"

    item = build_process_trace_item_from_source(source)

    assert item["subsystem"] == "ConfigCore"
    assert item["kind"] == "config"
    assert item["status"] == "completed"
    assert item["details"]["source_kind"] == "policy_matrix_runtime"
    assert item["details"]["decision"]["status"] == "allowed"


def test_policy_matrix_process_trace_requires_approval_warning():
    tool = build_tool_permission_contract(tool_name="Bash", permission_policy="ask", allowed_tools=["Bash"], risk_level="medium")
    decision = evaluate_policy_matrix_decision(tool_permission=tool)
    source = build_policy_matrix_trace_source(decision=decision)

    item = build_process_trace_item_from_source(source)

    assert item["status"] == "warning"
    assert item["details"]["decision"]["status"] == "requires_approval"
    assert "request_human_approval" in item["details"]["required_actions"]


def test_policy_matrix_process_trace_denied_is_blocked_and_redacted():
    tool = build_tool_permission_contract(tool_name="Bash", permission_policy="deny", metadata={"secret_token": "leak"})
    decision = evaluate_policy_matrix_decision(tool_permission=tool, metadata={"raw_prompt": "leak"})
    source = build_policy_matrix_trace_source(decision=decision, metadata={"response": "leak"})

    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    assert item["status"] == "blocked"
    assert item["subsystem"] == "ConfigCore"
    assert "leak" not in text
    assert "raw_prompt" not in text
    assert "response" not in text
