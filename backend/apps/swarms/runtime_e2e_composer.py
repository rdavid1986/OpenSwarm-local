from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from backend.apps.swarms.runtime_e2e_integration import (
    RuntimeE2EIntegrationState,
    build_runtime_e2e_integration_request,
    build_runtime_e2e_integration_state,
)


RUNTIME_E2E_COMPOSER_VERSION = "1.0"


@dataclass(frozen=True)
class RuntimeE2EComposerSelection:
    source_kind: str = "runtime_e2e_composer"
    composer_kind: str = "runtime_e2e_composer_selection"
    composer_version: str = RUNTIME_E2E_COMPOSER_VERSION
    swarm_id: str = ""
    agent_id: str = ""
    candidate_id: str = ""
    workspace_path: str = ""
    policy_matrix_ref: str = ""
    approval_id: str = ""
    selected_trace_refs: list[str] = field(default_factory=list)
    selected_source_kinds: list[str] = field(default_factory=list)
    selected_contract_kinds: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    can_compose_runtime_e2e: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _as_dict(value: Any) -> dict[str, Any]:
    safe = _safe(value)
    return safe if isinstance(safe, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    return [value]


def _text(value: Any, default: str = "", *, limit: int = 1000) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return (text or default)[:limit]


def _dedupe(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value, limit=500)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _merge_source_payload(source: Any) -> dict[str, Any]:
    data = _as_dict(source)
    details = _as_dict(data.get("details"))
    metadata = _as_dict(data.get("metadata"))
    merged = {**metadata, **data, **details}
    if "source_kind" not in merged:
        source_kind = metadata.get("source_kind") or details.get("source_kind")
        if source_kind:
            merged["source_kind"] = source_kind
    if "trace_id" not in merged and data.get("id"):
        merged["trace_id"] = data.get("id")
    return merged


def _source_payloads_from_value(value: Any) -> list[dict[str, Any]]:
    return [_merge_source_payload(item) for item in _as_list(value) if item is not None]


def _source_payloads_from_swarm(swarm: Any, explicit_sources: Any = None) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    sources.extend(_source_payloads_from_value(explicit_sources))

    for attr in (
        "process_trace",
        "process_trace_items",
        "process_trace_sources",
        "runtime_trace",
        "runtime_events",
        "event_trace",
        "events",
    ):
        sources.extend(_source_payloads_from_value(_field(swarm, attr)))

    final_result = _as_dict(_field(swarm, "final_result"))
    for key in (
        "process_trace",
        "process_trace_items",
        "process_trace_sources",
        "runtime_trace",
        "events",
        "evidence_trace",
    ):
        sources.extend(_source_payloads_from_value(final_result.get(key)))

    return [source for source in sources if source]


def _approval_payloads_from_swarm(swarm: Any, explicit_approvals: Any = None) -> list[dict[str, Any]]:
    approvals: list[dict[str, Any]] = []
    approvals.extend(_source_payloads_from_value(explicit_approvals))

    for attr in (
        "experimental_approvals",
        "approvals",
        "pending_approvals",
        "approval_requests",
    ):
        approvals.extend(_source_payloads_from_value(_field(swarm, attr)))

    final_result = _as_dict(_field(swarm, "final_result"))
    for key in ("experimental_approvals", "approvals", "pending_approvals", "approval_requests"):
        approvals.extend(_source_payloads_from_value(final_result.get(key)))

    return [approval for approval in approvals if approval]


def _candidate_from_payload(payload: dict[str, Any]) -> str:
    metadata = _as_dict(payload.get("metadata"))
    tool_input = _as_dict(payload.get("tool_input"))
    return _text(
        payload.get("candidate_id")
        or metadata.get("candidate_id")
        or tool_input.get("candidate_id")
        or payload.get("candidate")
    )


def _policy_from_payload(payload: dict[str, Any]) -> str:
    metadata = _as_dict(payload.get("metadata"))
    tool_input = _as_dict(payload.get("tool_input"))
    return _text(
        payload.get("policy_matrix_ref")
        or payload.get("policy_ref")
        or metadata.get("policy_matrix_ref")
        or metadata.get("policy_ref")
        or tool_input.get("policy_matrix_ref")
        or tool_input.get("policy_ref")
    )


def _approval_id_from_payload(payload: dict[str, Any]) -> str:
    return _text(payload.get("approval_id") or payload.get("id") or payload.get("request_id"))


def _workspace_from_payload(payload: dict[str, Any]) -> str:
    return _text(
        payload.get("workspace_path")
        or payload.get("workspace")
        or payload.get("cwd")
        or payload.get("project_path")
        or payload.get("output_workspace_path"),
        limit=1000,
    )


def _payload_matches_candidate(payload: dict[str, Any], candidate_id: str) -> bool:
    if not candidate_id:
        return True
    payload_candidate = _candidate_from_payload(payload)
    return not payload_candidate or payload_candidate == candidate_id


def _contract_kind(payload: dict[str, Any]) -> str:
    return _text(
        payload.get("contract_kind")
        or payload.get("runtime_e2e_kind")
        or payload.get("e2e_kind")
        or payload.get("materialization_kind")
        or payload.get("tdd_kind")
        or payload.get("sdd_kind")
        or payload.get("kind")
    )


def _latest_payload(
    sources: list[dict[str, Any]],
    *,
    candidate_id: str,
    predicate,
) -> dict[str, Any]:
    for payload in reversed(sources):
        if not _payload_matches_candidate(payload, candidate_id):
            continue
        if predicate(payload):
            return payload
    return {}


def _source_kind(payload: dict[str, Any]) -> str:
    return _text(payload.get("source_kind"))


def _is_sdd_gate(payload: dict[str, Any]) -> bool:
    contract = _contract_kind(payload)
    return _source_kind(payload) == "sdd_orchestrator_runtime" and (
        payload.get("can_mark_completed") is not None
        or "completion_gate" in contract
        or contract.startswith("sdd_completion")
    )


def _is_tdd_gate(payload: dict[str, Any]) -> bool:
    contract = _contract_kind(payload)
    return _source_kind(payload) == "tdd_agent_runtime" and (
        payload.get("can_complete_tdd_cycle") is not None
        or "runtime_gate" in contract
        or contract.startswith("tdd_runtime")
    )


def _is_materialization_execution(payload: dict[str, Any]) -> bool:
    contract = _contract_kind(payload)
    return _source_kind(payload) == "action_materialization_runtime" and (
        payload.get("can_mark_executed") is not None
        or payload.get("execution_status") is not None
        or "execution" in contract
    )


def _is_post_validation(payload: dict[str, Any]) -> bool:
    contract = _contract_kind(payload)
    if _source_kind(payload) != "action_materialization_runtime":
        return False
    if payload.get("can_mark_materialization_safe") is not None:
        return False
    if "post_validation_gate" in contract or "materialization_safe" in contract:
        return False
    return (
        payload.get("can_mark_validated") is not None
        or payload.get("validation_status") is not None
        or payload.get("post_validation_status") is not None
        or "post_validation_result" in contract
    )


def _is_rollback(payload: dict[str, Any]) -> bool:
    contract = _contract_kind(payload)
    if _source_kind(payload) != "action_materialization_runtime":
        return False
    if payload.get("can_mark_materialization_safe") is not None:
        return False
    if "post_validation_gate" in contract or "materialization_safe" in contract:
        return False
    return (
        payload.get("can_mark_rolled_back") is not None
        or payload.get("rollback_status") is not None
        or "rollback_result" in contract
    )


def _is_materialization_gate(payload: dict[str, Any]) -> bool:
    contract = _contract_kind(payload)
    return _source_kind(payload) == "action_materialization_runtime" and (
        payload.get("can_mark_materialization_safe") is not None
        or "post_validation_gate" in contract
        or "materialization_safe" in contract
    )


def _is_sdd_tdd_materialization_e2e_gate(payload: dict[str, Any]) -> bool:
    contract = _contract_kind(payload)
    return _source_kind(payload) == "sdd_tdd_materialization_e2e" or (
        payload.get("can_mark_change_completed") is not None
        or contract.startswith("sdd_tdd_materialization")
    )


def _process_trace_refs(sources: list[dict[str, Any]]) -> list[str]:
    refs: list[Any] = []
    for payload in sources:
        refs.append(payload.get("trace_id") or payload.get("id"))
        refs.extend(_as_list(payload.get("process_trace_refs")))
    return _dedupe(refs)


def _selected_source_refs(*payloads: dict[str, Any]) -> list[str]:
    return _dedupe([payload.get("trace_id") or payload.get("id") or _contract_kind(payload) for payload in payloads if payload])


def _selected_source_kinds(*payloads: dict[str, Any]) -> list[str]:
    return _dedupe([payload.get("source_kind") for payload in payloads if payload])


def _selected_contract_kinds(*payloads: dict[str, Any]) -> list[str]:
    return _dedupe([_contract_kind(payload) for payload in payloads if payload])


def _derive_candidate_id(explicit: Any, sources: list[dict[str, Any]], approvals: list[dict[str, Any]]) -> str:
    candidate_id = _text(explicit)
    if candidate_id:
        return candidate_id
    for payload in reversed(sources + approvals):
        candidate_id = _candidate_from_payload(payload)
        if candidate_id:
            return candidate_id
    return ""


def _derive_workspace_path(explicit: Any, swarm: Any, sources: list[dict[str, Any]]) -> str:
    workspace_path = _text(explicit, limit=1000)
    if workspace_path:
        return workspace_path
    final_result = _as_dict(_field(swarm, "final_result"))
    workspace_path = _workspace_from_payload(final_result)
    if workspace_path:
        return workspace_path
    for payload in reversed(sources):
        workspace_path = _workspace_from_payload(payload)
        if workspace_path:
            return workspace_path
    return ""


def _derive_approval_and_policy(
    *,
    explicit_approval_id: Any,
    explicit_policy_matrix_ref: Any,
    approvals: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    candidate_id: str,
) -> tuple[str, str]:
    approval_id = _text(explicit_approval_id)
    policy_ref = _text(explicit_policy_matrix_ref)

    matching_approvals = [
        approval for approval in approvals
        if _payload_matches_candidate(approval, candidate_id)
    ]

    for approval in reversed(matching_approvals or approvals):
        if not approval_id:
            approval_id = _approval_id_from_payload(approval)
        if not policy_ref:
            policy_ref = _policy_from_payload(approval)
        if approval_id and policy_ref:
            return approval_id, policy_ref

    for payload in reversed(sources):
        if not _payload_matches_candidate(payload, candidate_id):
            continue
        if not policy_ref:
            policy_ref = _policy_from_payload(payload)
        if not approval_id:
            approval_id = _approval_id_from_payload(payload)
        if approval_id and policy_ref:
            break

    return approval_id, policy_ref


def compose_runtime_e2e_integration_state_from_swarm(
    swarm: Any,
    *,
    candidate_id: Any = "",
    agent_id: Any = "",
    workspace_path: Any = "",
    policy_matrix_ref: Any = "",
    approval_id: Any = "",
    process_trace_sources: Any = None,
    approvals: Any = None,
) -> RuntimeE2EIntegrationState:
    sources = _source_payloads_from_swarm(swarm, explicit_sources=process_trace_sources)
    approval_payloads = _approval_payloads_from_swarm(swarm, explicit_approvals=approvals)

    selected_candidate_id = _derive_candidate_id(candidate_id, sources, approval_payloads)
    selected_workspace_path = _derive_workspace_path(workspace_path, swarm, sources)
    selected_approval_id, selected_policy_ref = _derive_approval_and_policy(
        explicit_approval_id=approval_id,
        explicit_policy_matrix_ref=policy_matrix_ref,
        approvals=approval_payloads,
        sources=sources,
        candidate_id=selected_candidate_id,
    )

    request = build_runtime_e2e_integration_request(
        swarm_id=_field(swarm, "id", ""),
        agent_id=agent_id,
        candidate_id=selected_candidate_id,
        workspace_path=selected_workspace_path,
        policy_matrix_ref=selected_policy_ref,
        approval_id=selected_approval_id,
    )

    sdd_gate = _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_sdd_gate)
    tdd_gate = _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_tdd_gate)
    materialization_execution = _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_materialization_execution)
    post_validation = _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_post_validation)
    rollback = _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_rollback)
    materialization_gate = _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_materialization_gate)
    e2e_gate = _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_sdd_tdd_materialization_e2e_gate)

    return build_runtime_e2e_integration_state(
        request=request,
        sdd_gate=sdd_gate,
        tdd_gate=tdd_gate,
        materialization_execution=materialization_execution,
        post_validation=post_validation,
        rollback=rollback,
        materialization_gate=materialization_gate,
        e2e_gate=e2e_gate,
        process_trace_refs=_process_trace_refs(sources),
    )


def build_runtime_e2e_composer_selection(
    swarm: Any,
    *,
    candidate_id: Any = "",
    agent_id: Any = "",
    workspace_path: Any = "",
    policy_matrix_ref: Any = "",
    approval_id: Any = "",
    process_trace_sources: Any = None,
    approvals: Any = None,
) -> RuntimeE2EComposerSelection:
    sources = _source_payloads_from_swarm(swarm, explicit_sources=process_trace_sources)
    approval_payloads = _approval_payloads_from_swarm(swarm, explicit_approvals=approvals)
    selected_candidate_id = _derive_candidate_id(candidate_id, sources, approval_payloads)
    selected_workspace_path = _derive_workspace_path(workspace_path, swarm, sources)
    selected_approval_id, selected_policy_ref = _derive_approval_and_policy(
        explicit_approval_id=approval_id,
        explicit_policy_matrix_ref=policy_matrix_ref,
        approvals=approval_payloads,
        sources=sources,
        candidate_id=selected_candidate_id,
    )

    selected = [
        _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_sdd_gate),
        _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_tdd_gate),
        _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_materialization_execution),
        _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_post_validation),
        _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_rollback),
        _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_materialization_gate),
        _latest_payload(sources, candidate_id=selected_candidate_id, predicate=_is_sdd_tdd_materialization_e2e_gate),
    ]

    blockers: list[str] = []
    required: list[str] = ["review_runtime_e2e_composer_selection"]

    if not selected_candidate_id:
        blockers.append("missing_candidate_id")
        required.append("attach_candidate_id")
    if not selected_workspace_path:
        blockers.append("missing_workspace_path")
        required.append("attach_workspace_path")
    if not selected_policy_ref:
        blockers.append("missing_policy_matrix_ref")
        required.append("attach_policy_matrix_ref")
    if not selected_approval_id:
        blockers.append("missing_approval_id")
        required.append("attach_approval_id")

    labels = [
        ("sdd_gate", selected[0]),
        ("tdd_gate", selected[1]),
        ("materialization_execution", selected[2]),
        ("post_validation", selected[3]),
        ("rollback", selected[4]),
        ("materialization_gate", selected[5]),
        ("e2e_gate", selected[6]),
    ]
    for label, payload in labels:
        if not payload:
            blockers.append(f"missing_{label}")
            required.append(f"provide_{label}")

    return RuntimeE2EComposerSelection(
        swarm_id=_text(_field(swarm, "id", ""), limit=240),
        agent_id=_text(agent_id, limit=240),
        candidate_id=selected_candidate_id,
        workspace_path=selected_workspace_path,
        policy_matrix_ref=selected_policy_ref,
        approval_id=selected_approval_id,
        selected_trace_refs=_selected_source_refs(*selected),
        selected_source_kinds=_selected_source_kinds(*selected),
        selected_contract_kinds=_selected_contract_kinds(*selected),
        required_actions=_dedupe(required),
        blockers=_dedupe(blockers),
        can_compose_runtime_e2e=not blockers,
    )


def dump_runtime_e2e_composer_selection(selection: Any) -> dict[str, Any]:
    dumped = _safe(selection)
    return dumped if isinstance(dumped, dict) else {}
