from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


RUNTIME_E2E_VERSION = "1.0"


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


def _contract_dict(value: Any) -> dict[str, Any]:
    safe = _safe(value)
    return safe if isinstance(safe, dict) else {}


def _text(value: Any, default: str = "", *, limit: int = 1000) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return (text or default)[:limit]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value, limit=500)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


@dataclass(frozen=True)
class RuntimeE2EIntegrationRequest:
    source_kind: str = "runtime_e2e_integration"
    runtime_e2e_kind: str = "runtime_e2e_integration_request"
    runtime_e2e_version: str = RUNTIME_E2E_VERSION
    swarm_id: str = ""
    agent_id: str = ""
    candidate_id: str = ""
    workspace_path: str = ""
    policy_matrix_ref: str = ""
    approval_id: str = ""
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class RuntimeE2EIntegrationState:
    source_kind: str = "runtime_e2e_integration"
    runtime_e2e_kind: str = "runtime_e2e_integration_state"
    runtime_e2e_version: str = RUNTIME_E2E_VERSION
    swarm_id: str = ""
    agent_id: str = ""
    candidate_id: str = ""
    stage: str = "blocked"
    sdd_gate: dict[str, Any] = field(default_factory=dict)
    tdd_gate: dict[str, Any] = field(default_factory=dict)
    materialization_execution: dict[str, Any] = field(default_factory=dict)
    post_validation: dict[str, Any] = field(default_factory=dict)
    rollback: dict[str, Any] = field(default_factory=dict)
    materialization_gate: dict[str, Any] = field(default_factory=dict)
    e2e_gate: dict[str, Any] = field(default_factory=dict)
    completion_conditions: dict[str, bool] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    process_trace_refs: list[str] = field(default_factory=list)
    can_start_runtime_e2e: bool = False
    can_mark_runtime_e2e_complete: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


def dump_runtime_e2e_integration_contract(value: Any) -> dict[str, Any]:
    dumped = _safe(value)
    return dumped if isinstance(dumped, dict) else {}


def build_runtime_e2e_integration_request(
    *,
    swarm_id: Any = "",
    agent_id: Any = "",
    candidate_id: Any = "",
    workspace_path: Any = "",
    policy_matrix_ref: Any = "",
    approval_id: Any = "",
) -> RuntimeE2EIntegrationRequest:
    required = ["review_runtime_e2e_integration_request"]
    if not _text(candidate_id):
        required.append("attach_candidate_id")
    if not _text(workspace_path):
        required.append("attach_workspace_path")
    if not _text(policy_matrix_ref):
        required.append("attach_policy_matrix_ref")
    if not _text(approval_id):
        required.append("attach_approval_id")

    return RuntimeE2EIntegrationRequest(
        swarm_id=_text(swarm_id, limit=240),
        agent_id=_text(agent_id, limit=240),
        candidate_id=_text(candidate_id, limit=240),
        workspace_path=_text(workspace_path, limit=1000),
        policy_matrix_ref=_text(policy_matrix_ref, limit=240),
        approval_id=_text(approval_id, limit=240),
        required_actions=_dedupe_text(required),
    )


def build_runtime_e2e_integration_state(
    *,
    request: Any,
    sdd_gate: Any = None,
    tdd_gate: Any = None,
    materialization_execution: Any = None,
    post_validation: Any = None,
    rollback: Any = None,
    materialization_gate: Any = None,
    e2e_gate: Any = None,
    process_trace_refs: list[Any] | None = None,
) -> RuntimeE2EIntegrationState:
    req = _contract_dict(request)
    sdd = _contract_dict(sdd_gate)
    tdd = _contract_dict(tdd_gate)
    execution = _contract_dict(materialization_execution)
    validation = _contract_dict(post_validation)
    rollback_data = _contract_dict(rollback)
    mat_gate = _contract_dict(materialization_gate)
    e2e = _contract_dict(e2e_gate)

    sdd_ok = bool(sdd.get("can_mark_completed") is True and _text(sdd.get("gate_status")).lower() == "completed")
    tdd_ok = bool(tdd.get("can_complete_tdd_cycle") is True and _text(tdd.get("gate_status")).lower() == "completed")
    execution_ok = bool(execution.get("can_mark_executed") is True and _text(execution.get("execution_status")).lower() == "executed")
    post_validation_ok = bool(validation.get("can_mark_validated") is True and _text(validation.get("validation_status")).lower() == "passed")
    rollback_ready = bool(
        mat_gate.get("rollback_ready") is True
        or rollback_data.get("can_mark_rolled_back") is True
        or _text(rollback_data.get("rollback_status")).lower() in {"ready", "rolled_back", "passed"}
    )
    materialization_safe = bool(mat_gate.get("can_mark_materialization_safe") is True and _text(mat_gate.get("gate_status")).lower() == "completed")
    e2e_ok = bool(e2e.get("can_mark_change_completed") is True and _text(e2e.get("gate_status")).lower() == "completed")

    conditions = {
        "request_has_candidate": bool(_text(req.get("candidate_id"))),
        "request_has_workspace": bool(_text(req.get("workspace_path"))),
        "request_has_policy": bool(_text(req.get("policy_matrix_ref"))),
        "request_has_approval": bool(_text(req.get("approval_id"))),
        "sdd_ok": sdd_ok,
        "tdd_ok": tdd_ok,
        "materialization_execution_ok": execution_ok,
        "post_validation_ok": post_validation_ok,
        "rollback_ready": rollback_ready,
        "materialization_safe": materialization_safe,
        "e2e_ok": e2e_ok,
    }

    blockers: list[str] = []
    required: list[str] = ["review_runtime_e2e_integration_state"]

    if not conditions["request_has_candidate"]:
        blockers.append("missing_candidate_id")
        required.append("attach_candidate_id")
    if not conditions["request_has_workspace"]:
        blockers.append("missing_workspace_path")
        required.append("attach_workspace_path")
    if not conditions["request_has_policy"]:
        blockers.append("missing_policy_matrix_ref")
        required.append("attach_policy_matrix_ref")
    if not conditions["request_has_approval"]:
        blockers.append("missing_approval_id")
        required.append("attach_approval_id")
    if not sdd_ok:
        blockers.append("sdd_gate_not_completed")
        required.append("complete_sdd_gate")
    if not tdd_ok:
        blockers.append("tdd_gate_not_completed")
        required.append("complete_tdd_runtime_gate")
    if not execution_ok:
        blockers.append("materialization_execution_not_confirmed")
        required.append("execute_approved_materialization")
    if not post_validation_ok:
        blockers.append("post_validation_not_passed")
        required.append("run_post_validation")
    if not rollback_ready:
        blockers.append("rollback_not_ready")
        required.append("prepare_or_execute_rollback")
    if not materialization_safe:
        blockers.append("materialization_safe_gate_not_completed")
        required.append("complete_materialization_safe_gate")
    if not e2e_ok:
        blockers.append("e2e_completion_gate_not_completed")
        required.append("complete_sdd_tdd_materialization_e2e_gate")

    evidence_refs: list[str] = []
    for data in [sdd, tdd, execution, validation, rollback_data, mat_gate, e2e]:
        evidence_refs.extend(_as_list(data.get("evidence_refs")))

    trace_refs = _dedupe_text(_as_list(process_trace_refs))
    complete = all(conditions.values()) and not blockers

    if complete:
        stage = "completed"
    elif execution_ok and not post_validation_ok:
        stage = "post_validation_required"
    elif execution_ok and post_validation_ok and not rollback_ready:
        stage = "rollback_required"
    elif sdd_ok and tdd_ok and not execution_ok:
        stage = "materialization_required"
    elif sdd_ok and not tdd_ok:
        stage = "tdd_required"
    else:
        stage = "blocked"

    return RuntimeE2EIntegrationState(
        swarm_id=_text(req.get("swarm_id"), limit=240),
        agent_id=_text(req.get("agent_id"), limit=240),
        candidate_id=_text(req.get("candidate_id") or sdd.get("candidate_id") or execution.get("candidate_id") or e2e.get("candidate_id"), limit=240),
        stage=stage,
        sdd_gate=sdd,
        tdd_gate=tdd,
        materialization_execution=execution,
        post_validation=validation,
        rollback=rollback_data,
        materialization_gate=mat_gate,
        e2e_gate=e2e,
        completion_conditions=conditions,
        blockers=_dedupe_text(blockers),
        required_actions=_dedupe_text(required),
        evidence_refs=_dedupe_text(evidence_refs),
        process_trace_refs=trace_refs,
        can_start_runtime_e2e=conditions["request_has_candidate"] and conditions["request_has_workspace"] and conditions["request_has_policy"] and conditions["request_has_approval"],
        can_mark_runtime_e2e_complete=complete,
    )
