from backend.apps.agents.runtime.policy_matrix_runtime import (
    attach_policy_matrix_to_metadata,
    build_action_approval_matrix,
    build_mcp_context_budget_policy,
    build_policy_matrix_trace_source,
    build_provider_model_resource_policy,
    build_tool_permission_contract,
    dump_policy_matrix_decision,
    evaluate_policy_matrix_decision,
    normalize_policy_decision_state,
)


def test_tool_permission_allows_low_risk_allowed_tool():
    contract = build_tool_permission_contract(
        tool_name="Read",
        permission_policy="always_allow",
        allowed_tools=["Read"],
        risk_level="low",
    )

    assert contract.decision == "allowed"
    assert contract.can_execute_tool is True
    assert contract.can_modify_files is False


def test_tool_permission_blocks_denied_tool():
    contract = build_tool_permission_contract(tool_name="Bash", permission_policy="deny", allowed_tools=["Bash"])

    assert contract.decision == "denied"
    assert contract.can_execute_tool is False
    assert contract.reason == "tool_denied_by_permission_policy"


def test_tool_permission_blocks_path_scope_for_write():
    contract = build_tool_permission_contract(
        tool_name="Edit",
        permission_policy="always_allow",
        allowed_tools=["Edit"],
        allowed_paths=["frontend/src"],
        forbidden_paths=["backend"],
        target_path="backend/app.py",
    )

    assert contract.decision == "blocked_by_scope"
    assert "review_path_scope" in contract.required_actions


def test_provider_model_policy_blocks_remote_when_local_only():
    policy = build_provider_model_resource_policy(provider_id="openai", model_id="gpt", local_only_required=True, remote_provider_allowed=False)

    assert policy.decision == "blocked_by_config"
    assert policy.can_call_provider is False


def test_provider_model_policy_blocks_missing_capability():
    policy = build_provider_model_resource_policy(
        provider_id="ollama",
        model_id="qwen",
        required_capabilities=["tools", "vision"],
        available_capabilities=["tools"],
    )

    assert policy.decision == "blocked_by_config"
    assert policy.missing_capabilities == ["vision"]


def test_provider_model_policy_blocks_context_budget():
    policy = build_provider_model_resource_policy(provider_id="ollama", model_id="qwen", context_limit=100, requested_context_tokens=200)

    assert policy.decision == "blocked_by_budget"
    assert "review_context_budget" in policy.required_actions


def test_mcp_policy_requires_activation_approval():
    policy = build_mcp_context_budget_policy(server_name="blender", active=False, activation_requested=True, allowed_servers=["blender"])

    assert policy.decision == "requires_approval"
    assert policy.can_activate_mcp is False
    assert "request_mcp_activation_approval" in policy.required_actions


def test_mcp_policy_blocks_context_budget():
    policy = build_mcp_context_budget_policy(server_name="unity", active=True, context_tokens=5000, max_context_tokens=1000)

    assert policy.decision == "blocked_by_budget"
    assert policy.can_call_mcp_tool is False


def test_action_approval_matrix_blocks_critical_risk():
    matrix = build_action_approval_matrix(action_name="delete files", action_type="file_write", risk_level="critical", approval_policy="ask")

    assert matrix.decision == "blocked_by_risk"
    assert matrix.can_execute_action is False


def test_action_approval_matrix_allows_existing_approval_reference_but_not_execution_grant():
    matrix = build_action_approval_matrix(action_name="edit", risk_level="medium", existing_approval_id="approval-1")

    assert matrix.decision == "allowed"
    assert matrix.can_execute_action is True
    assert matrix.approval_grants_execution is False


def test_policy_matrix_requires_approval_when_any_layer_requires_approval():
    tool = build_tool_permission_contract(tool_name="Bash", permission_policy="ask", allowed_tools=["Bash"], risk_level="medium")
    provider = build_provider_model_resource_policy(provider_id="ollama", model_id="qwen")
    decision = evaluate_policy_matrix_decision(tool_permission=tool, provider_policy=provider)

    assert decision.status == "requires_approval"
    assert decision.allowed is False
    assert "request_human_approval" in decision.required_actions


def test_policy_matrix_denies_when_any_layer_blocks():
    tool = build_tool_permission_contract(tool_name="Edit", permission_policy="always_allow", allowed_tools=["Edit"], allowed_paths=["frontend"], target_path="backend/app.py")
    provider = build_provider_model_resource_policy(provider_id="ollama", model_id="qwen")
    decision = evaluate_policy_matrix_decision(tool_permission=tool, provider_policy=provider)

    assert decision.status == "denied"
    assert decision.allowed is False
    assert "target_path_outside_allowed_scope" in decision.blocking_reasons


def test_policy_matrix_allows_when_all_layers_allow():
    tool = build_tool_permission_contract(tool_name="Read", permission_policy="always_allow", allowed_tools=["Read"], risk_level="low")
    provider = build_provider_model_resource_policy(provider_id="ollama", model_id="qwen")
    decision = evaluate_policy_matrix_decision(tool_permission=tool, provider_policy=provider)

    assert decision.status == "allowed"
    assert decision.allowed is True
    assert decision.can_execute_tool is True
    assert decision.can_call_provider is True


def test_policy_matrix_trace_source_is_redacted():
    tool = build_tool_permission_contract(tool_name="Read", permission_policy="always_allow", metadata={"secret_token": "leak"})
    decision = evaluate_policy_matrix_decision(tool_permission=tool, metadata={"raw_prompt": "leak"})
    trace = build_policy_matrix_trace_source(decision=decision, metadata={"response": "leak"})

    text = str(trace).lower()

    assert trace["source_kind"] == "policy_matrix_runtime"
    assert trace["policy_kind"] == "policy_matrix_runtime"
    assert "leak" not in text
    assert trace["can_execute_tool"] is True


def test_attach_policy_matrix_to_metadata_does_not_mutate_original():
    decision = evaluate_policy_matrix_decision(tool_permission=build_tool_permission_contract(tool_name="Read", permission_policy="always_allow"))
    original = {"existing": True}

    attached = attach_policy_matrix_to_metadata(original, decision=decision)

    assert original == {"existing": True}
    assert attached["existing"] is True
    assert attached["policy_matrix_runtime"]["status"] == "allowed"


def test_normalize_policy_decision_state_unknown():
    assert normalize_policy_decision_state("blocked_by_scope") == "blocked_by_scope"
    assert normalize_policy_decision_state("something") == "unknown"


def test_dump_policy_matrix_decision_is_safe():
    decision = evaluate_policy_matrix_decision(metadata={"api_key": "leak", "safe": "ok"})
    dumped = dump_policy_matrix_decision(decision)
    text = str(dumped).lower()

    assert "leak" not in text
    assert "api_key" not in text
    assert dumped["metadata"]["safe"] == "ok"
