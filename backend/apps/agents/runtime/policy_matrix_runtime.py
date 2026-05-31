"""Side-effect-free policy matrix runtime contracts.

This module unifies policy decisions across tool permissions, provider/model
resource policy, MCP/context budget policy and human approval requirements.
It does not execute tools, call providers, activate MCP servers, mutate config,
or approve actions automatically.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any


SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "chain_of_thought",
    "cookie",
    "credential",
    "credentials",
    "hidden_reasoning",
    "password",
    "private_key",
    "prompt",
    "raw_prompt",
    "raw_response",
    "response",
    "secret",
    "session",
    "token",
}

DECISION_STATES = {
    "allowed",
    "denied",
    "requires_approval",
    "blocked_by_config",
    "blocked_by_scope",
    "blocked_by_risk",
    "blocked_by_budget",
    "unknown",
}

RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}


@dataclass
class ToolPermissionContract:
    contract_kind: str = "tool_permission_contract"
    tool_name: str = ""
    action_name: str = ""
    requested_scope: str = ""
    permission_policy: str = "ask"
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    decision: str = "unknown"
    reason: str = ""
    required_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_execute_tool: bool = False
    can_modify_files: bool = False
    can_activate_mcp: bool = False


@dataclass
class ProviderModelResourcePolicy:
    policy_kind: str = "provider_model_resource_policy"
    provider_id: str = "unknown"
    model_id: str = "unknown"
    local_only_required: bool = True
    remote_provider_allowed: bool = False
    context_limit: int | None = None
    requested_context_tokens: int | None = None
    usage_ratio: float | None = None
    required_capabilities: list[str] = field(default_factory=list)
    available_capabilities: list[str] = field(default_factory=list)
    missing_capabilities: list[str] = field(default_factory=list)
    decision: str = "unknown"
    reason: str = ""
    required_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_call_provider: bool = False
    can_change_model: bool = False


@dataclass
class MCPContextBudgetPolicy:
    policy_kind: str = "mcp_context_budget_policy"
    server_name: str = ""
    active: bool = False
    activation_requested: bool = False
    context_tokens: int = 0
    max_context_tokens: int | None = None
    usage_ratio: float | None = None
    allowed_servers: list[str] = field(default_factory=list)
    active_servers: list[str] = field(default_factory=list)
    decision: str = "unknown"
    reason: str = ""
    required_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_activate_mcp: bool = False
    can_call_mcp_tool: bool = False


@dataclass
class ActionApprovalMatrix:
    matrix_kind: str = "action_approval_matrix"
    action_name: str = ""
    action_type: str = ""
    risk_level: str = "unknown"
    scope: str = ""
    source: str = ""
    mode: str = ""
    approval_policy: str = "ask"
    human_approval_required: bool = True
    existing_approval_id: str = ""
    decision: str = "requires_approval"
    reason: str = ""
    required_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_execute_action: bool = False
    approval_grants_execution: bool = False


@dataclass
class PolicyMatrixDecision:
    decision_kind: str = "policy_matrix_decision"
    status: str = "unknown"
    allowed: bool = False
    reason: str = ""
    tool_permission: dict[str, Any] = field(default_factory=dict)
    provider_policy: dict[str, Any] = field(default_factory=dict)
    mcp_policy: dict[str, Any] = field(default_factory=dict)
    approval_matrix: dict[str, Any] = field(default_factory=dict)
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_execute_tool: bool = False
    can_call_provider: bool = False
    can_activate_mcp: bool = False
    can_modify_files: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:140]:
            normalized = str(key or "").lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS or any(token in normalized for token in ("secret", "token", "password", "credential", "authorization", "cookie", "api_key", "private_key", "prompt", "response", "chain_of_thought")):
                continue
            output[str(key)] = _safe(item)
        if len(value) > 140:
            output["__truncated__"] = f"+{len(value) - 140} more fields"
        return output
    if isinstance(value, list):
        visible = [_safe(item) for item in value[:140]]
        if len(value) > 140:
            visible.append(f"+{len(value) - 140} more")
        return visible
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, str):
        return value[:1600].rstrip() + ("..." if len(value) > 1600 else "")
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:1600]


def _normalize_risk(value: Any) -> str:
    text = _text(value, "unknown").lower()
    return text if text in RISK_LEVELS else "unknown"


def normalize_policy_decision_state(value: Any) -> str:
    text = _text(value, "unknown").lower()
    return text if text in DECISION_STATES else "unknown"


def _normalize_permission_policy(value: Any) -> str:
    text = _text(value, "ask").lower()
    if text in {"always_allow", "allow", "allowed"}:
        return "always_allow"
    if text in {"deny", "denied"}:
        return "deny"
    if text in {"ask", "approval_required", "requires_approval"}:
        return "ask"
    return "ask"


def _path_in_scope(path: str, *, allowed_paths: list[str], forbidden_paths: list[str]) -> bool:
    normalized = path.replace("\\", "/").strip().strip("./")
    if not normalized:
        return False
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized or normalized == ".." or (len(normalized) >= 3 and normalized[1:3] == ":/"):
        return False
    for forbidden in forbidden_paths:
        forbidden_norm = str(forbidden).replace("\\", "/").strip().strip("./")
        if forbidden_norm and (normalized == forbidden_norm or normalized.startswith(f"{forbidden_norm}/")):
            return False
    if not allowed_paths:
        return True
    for allowed in allowed_paths:
        allowed_norm = str(allowed).replace("\\", "/").strip().strip("./")
        if not allowed_norm:
            continue
        if normalized == allowed_norm or normalized.startswith(f"{allowed_norm}/"):
            return True
    return False


def build_tool_permission_contract(
    *,
    tool_name: str = "",
    action_name: str = "",
    requested_scope: str = "",
    permission_policy: str = "ask",
    allowed_tools: list[Any] | None = None,
    denied_tools: list[Any] | None = None,
    allowed_paths: list[Any] | None = None,
    forbidden_paths: list[Any] | None = None,
    target_path: str | None = None,
    risk_level: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> ToolPermissionContract:
    tool = _text(tool_name)
    allowed = _dedupe(_as_list(allowed_tools))
    denied = _dedupe(_as_list(denied_tools))
    allowed_scope = _dedupe(_as_list(allowed_paths))
    forbidden_scope = _dedupe(_as_list(forbidden_paths))
    policy = _normalize_permission_policy(permission_policy)
    risk = _normalize_risk(risk_level)
    required: list[str] = []
    warnings: list[str] = []
    decision = "allowed"
    reason = "Tool is allowed by declarative policy."

    if not tool:
        decision = "denied"
        reason = "tool_name_missing"
    elif tool in denied or policy == "deny":
        decision = "denied"
        reason = "tool_denied_by_permission_policy"
    elif allowed and tool not in allowed:
        decision = "denied"
        reason = "tool_not_in_allowed_tools"
    elif target_path is not None and tool in {"Write", "Edit", "Diff", "Bash"} and not _path_in_scope(target_path, allowed_paths=allowed_scope, forbidden_paths=forbidden_scope):
        decision = "blocked_by_scope"
        reason = "target_path_outside_allowed_scope"
        required.append("review_path_scope")
    elif risk in {"high", "critical"}:
        decision = "requires_approval"
        reason = "high_risk_tool_requires_approval"
        required.append("request_human_approval")
    elif policy == "ask":
        decision = "requires_approval"
        reason = "tool_policy_requires_approval"
        required.append("request_human_approval")

    if target_path and tool not in {"Write", "Edit", "Diff", "Bash"}:
        warnings.append("target_path_ignored_for_non_file_tool")

    return ToolPermissionContract(
        tool_name=tool,
        action_name=_text(action_name),
        requested_scope=_text(requested_scope),
        permission_policy=policy,
        allowed_tools=allowed,
        denied_tools=denied,
        allowed_paths=allowed_scope,
        forbidden_paths=forbidden_scope,
        risk_level=risk,
        decision=decision,
        reason=reason,
        required_actions=required,
        warnings=warnings,
        metadata=_safe(metadata or {}),
        can_execute_tool=decision == "allowed",
        can_modify_files=decision == "allowed" and tool in {"Write", "Edit", "Diff"},
        can_activate_mcp=False,
    )


def dump_tool_permission_contract(contract: ToolPermissionContract | dict[str, Any]) -> dict[str, Any]:
    return _safe(contract)


def build_provider_model_resource_policy(
    *,
    provider_id: str = "unknown",
    model_id: str = "unknown",
    local_only_required: bool = True,
    remote_provider_allowed: bool = False,
    context_limit: int | None = None,
    requested_context_tokens: int | None = None,
    required_capabilities: list[Any] | None = None,
    available_capabilities: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProviderModelResourcePolicy:
    provider = _text(provider_id, "unknown")
    model = _text(model_id, "unknown")
    required_caps = _dedupe(_as_list(required_capabilities))
    available_caps = _dedupe(_as_list(available_capabilities))
    missing_caps = [cap for cap in required_caps if cap not in available_caps]
    required_actions: list[str] = []
    warnings: list[str] = []
    decision = "allowed"
    reason = "Provider/model resource policy allows this request."
    usage_ratio = None

    if local_only_required and provider not in {"ollama", "local", "local_ollama"}:
        if not remote_provider_allowed:
            decision = "blocked_by_config"
            reason = "remote_provider_blocked_by_local_only_policy"
            required_actions.append("review_provider_policy")
    if context_limit is not None and requested_context_tokens is not None and context_limit > 0:
        usage_ratio = round(max(0, requested_context_tokens) / context_limit, 4)
        if requested_context_tokens > context_limit:
            decision = "blocked_by_budget"
            reason = "requested_context_exceeds_model_limit"
            required_actions.append("review_context_budget")
        elif usage_ratio >= 0.85:
            warnings.append("model_context_near_limit")
            required_actions.append("review_context_budget")
    if missing_caps:
        decision = "blocked_by_config"
        reason = "model_missing_required_capabilities"
        required_actions.append("review_model_capabilities")

    return ProviderModelResourcePolicy(
        provider_id=provider,
        model_id=model,
        local_only_required=bool(local_only_required),
        remote_provider_allowed=bool(remote_provider_allowed),
        context_limit=context_limit,
        requested_context_tokens=requested_context_tokens,
        usage_ratio=usage_ratio,
        required_capabilities=required_caps,
        available_capabilities=available_caps,
        missing_capabilities=missing_caps,
        decision=decision,
        reason=reason,
        required_actions=_dedupe(required_actions),
        warnings=warnings,
        metadata=_safe(metadata or {}),
        can_call_provider=decision == "allowed",
        can_change_model=False,
    )


def dump_provider_model_resource_policy(policy: ProviderModelResourcePolicy | dict[str, Any]) -> dict[str, Any]:
    return _safe(policy)


def build_mcp_context_budget_policy(
    *,
    server_name: str = "",
    active: bool = False,
    activation_requested: bool = False,
    context_tokens: int = 0,
    max_context_tokens: int | None = None,
    allowed_servers: list[Any] | None = None,
    active_servers: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MCPContextBudgetPolicy:
    server = _text(server_name)
    allowed = _dedupe(_as_list(allowed_servers))
    active_list = _dedupe(_as_list(active_servers))
    required_actions: list[str] = []
    warnings: list[str] = []
    usage_ratio = None
    decision = "allowed"
    reason = "MCP context budget policy allows this request."

    is_active = bool(active or (server and server in active_list))
    if not server:
        decision = "denied"
        reason = "mcp_server_missing"
    elif allowed and server not in allowed:
        decision = "blocked_by_config"
        reason = "mcp_server_not_allowed"
        required_actions.append("review_mcp_allowlist")
    elif activation_requested and not is_active:
        decision = "requires_approval"
        reason = "mcp_activation_requires_approval"
        required_actions.append("request_mcp_activation_approval")
    elif not is_active:
        decision = "requires_approval"
        reason = "mcp_server_inactive"
        required_actions.append("activate_mcp_with_approval")

    if max_context_tokens is not None and max_context_tokens > 0:
        usage_ratio = round(max(0, int(context_tokens or 0)) / max_context_tokens, 4)
        if context_tokens > max_context_tokens:
            decision = "blocked_by_budget"
            reason = "mcp_context_exceeds_budget"
            required_actions.append("review_mcp_context_budget")
        elif usage_ratio >= 0.85:
            warnings.append("mcp_context_near_limit")
            required_actions.append("review_mcp_context_budget")

    return MCPContextBudgetPolicy(
        server_name=server,
        active=is_active,
        activation_requested=bool(activation_requested),
        context_tokens=max(0, int(context_tokens or 0)),
        max_context_tokens=max_context_tokens,
        usage_ratio=usage_ratio,
        allowed_servers=allowed,
        active_servers=active_list,
        decision=decision,
        reason=reason,
        required_actions=_dedupe(required_actions),
        warnings=warnings,
        metadata=_safe(metadata or {}),
        can_activate_mcp=decision == "allowed" and is_active,
        can_call_mcp_tool=decision == "allowed" and is_active,
    )


def dump_mcp_context_budget_policy(policy: MCPContextBudgetPolicy | dict[str, Any]) -> dict[str, Any]:
    return _safe(policy)


def build_action_approval_matrix(
    *,
    action_name: str = "",
    action_type: str = "",
    risk_level: str = "unknown",
    scope: str = "",
    source: str = "",
    mode: str = "",
    approval_policy: str = "ask",
    existing_approval_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> ActionApprovalMatrix:
    risk = _normalize_risk(risk_level)
    policy = _normalize_permission_policy(approval_policy)
    required_actions: list[str] = []
    warnings: list[str] = []
    decision = "requires_approval"
    reason = "Approval is required by default."

    if policy == "deny":
        decision = "denied"
        reason = "approval_policy_denies_action"
    elif risk == "critical":
        decision = "blocked_by_risk"
        reason = "critical_risk_blocks_action"
        required_actions.append("redesign_or_reduce_risk")
    elif existing_approval_id:
        decision = "allowed"
        reason = "existing_approval_reference_present"
    elif policy == "always_allow" and risk in {"low", "unknown"}:
        decision = "allowed"
        reason = "low_risk_action_allowed_by_policy"
    elif risk in {"high", "medium"} or policy == "ask":
        decision = "requires_approval"
        reason = "human_approval_required"
        required_actions.append("request_human_approval")

    return ActionApprovalMatrix(
        action_name=_text(action_name),
        action_type=_text(action_type),
        risk_level=risk,
        scope=_text(scope),
        source=_text(source),
        mode=_text(mode),
        approval_policy=policy,
        human_approval_required=decision == "requires_approval",
        existing_approval_id=_text(existing_approval_id),
        decision=decision,
        reason=reason,
        required_actions=required_actions,
        warnings=warnings,
        metadata=_safe(metadata or {}),
        can_execute_action=decision == "allowed",
        approval_grants_execution=False,
    )


def dump_action_approval_matrix(matrix: ActionApprovalMatrix | dict[str, Any]) -> dict[str, Any]:
    return _safe(matrix)


def evaluate_policy_matrix_decision(
    *,
    tool_permission: ToolPermissionContract | dict[str, Any] | None = None,
    provider_policy: ProviderModelResourcePolicy | dict[str, Any] | None = None,
    mcp_policy: MCPContextBudgetPolicy | dict[str, Any] | None = None,
    approval_matrix: ActionApprovalMatrix | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> PolicyMatrixDecision:
    tool = dump_tool_permission_contract(tool_permission or {})
    provider = dump_provider_model_resource_policy(provider_policy or {})
    mcp = dump_mcp_context_budget_policy(mcp_policy or {})
    approval = dump_action_approval_matrix(approval_matrix or {})

    parts = [part for part in (tool, provider, mcp, approval) if part]
    decisions = [normalize_policy_decision_state(part.get("decision")) for part in parts]
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    required_actions: list[str] = []

    for part in parts:
        decision = normalize_policy_decision_state(part.get("decision"))
        if decision not in {"allowed", "unknown"}:
            blocking_reasons.append(part.get("reason") or decision)
        warnings.extend(_as_list(part.get("warnings")))
        required_actions.extend(_as_list(part.get("required_actions")))

    if any(decision in {"denied", "blocked_by_config", "blocked_by_scope", "blocked_by_risk, blocked_by_budget"} for decision in decisions):
        status = "denied"
        allowed = False
    elif any(decision in {"blocked_by_budget"} for decision in decisions):
        status = "denied"
        allowed = False
    elif any(decision == "requires_approval" for decision in decisions):
        status = "requires_approval"
        allowed = False
    elif decisions and all(decision in {"allowed", "unknown"} for decision in decisions):
        status = "allowed"
        allowed = True
    else:
        status = "unknown"
        allowed = False

    reason = "All policy layers allow the request." if allowed else (blocking_reasons[0] if blocking_reasons else "Policy matrix does not allow execution yet.")
    return PolicyMatrixDecision(
        status=status,
        allowed=allowed,
        reason=reason,
        tool_permission=tool,
        provider_policy=provider,
        mcp_policy=mcp,
        approval_matrix=approval,
        blocking_reasons=_dedupe(blocking_reasons),
        warnings=_dedupe(warnings),
        required_actions=_dedupe(required_actions),
        metadata=_safe(metadata or {"created_at": _now()}),
        can_execute_tool=allowed and bool(tool.get("can_execute_tool")),
        can_call_provider=allowed and bool(provider.get("can_call_provider")),
        can_activate_mcp=allowed and bool(mcp.get("can_activate_mcp")),
        can_modify_files=allowed and bool(tool.get("can_modify_files")),
    )


def dump_policy_matrix_decision(decision: PolicyMatrixDecision | dict[str, Any]) -> dict[str, Any]:
    return _safe(decision)


def build_policy_matrix_trace_source(
    *,
    decision: PolicyMatrixDecision | dict[str, Any] | None = None,
    tool_permission: ToolPermissionContract | dict[str, Any] | None = None,
    provider_policy: ProviderModelResourcePolicy | dict[str, Any] | None = None,
    mcp_policy: MCPContextBudgetPolicy | dict[str, Any] | None = None,
    approval_matrix: ActionApprovalMatrix | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    final_decision = dump_policy_matrix_decision(
        decision
        or evaluate_policy_matrix_decision(
            tool_permission=tool_permission,
            provider_policy=provider_policy,
            mcp_policy=mcp_policy,
            approval_matrix=approval_matrix,
        )
    )
    return _safe({
        "source_kind": "policy_matrix_runtime",
        "policy_kind": "policy_matrix_runtime",
        "status": final_decision.get("status") or "unknown",
        "decision": final_decision,
        "warnings": final_decision.get("warnings") or [],
        "required_actions": final_decision.get("required_actions") or [],
        "can_execute_tool": bool(final_decision.get("can_execute_tool")),
        "can_call_provider": bool(final_decision.get("can_call_provider")),
        "can_activate_mcp": bool(final_decision.get("can_activate_mcp")),
        "can_modify_files": bool(final_decision.get("can_modify_files")),
        "metadata": _safe(metadata or {}),
    })


def attach_policy_matrix_to_metadata(
    metadata: dict[str, Any] | None,
    *,
    decision: PolicyMatrixDecision | dict[str, Any] | None = None,
) -> dict[str, Any]:
    clone = deepcopy(metadata) if isinstance(metadata, dict) else {}
    clone["policy_matrix_runtime"] = dump_policy_matrix_decision(decision or {})
    return _safe(clone)
