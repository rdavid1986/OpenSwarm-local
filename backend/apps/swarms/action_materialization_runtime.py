"""Action materialization runtime contracts.

Side-effect-free contracts for converting approved candidates into controlled
action plans. This module does not write files, apply patches, execute commands,
activate tools/MCP, mutate memory, or approve actions.

Real execution must remain behind PolicyMatrix, SafeShell/TestRunner,
explicit approval, evidence capture and rollback gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from hashlib import sha256
import re
from typing import Any


ACTION_MATERIALIZATION_VERSION = "openswarm.action_materialization.v1"

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "private_key",
    "authorization",
    "cookie",
    "chain_of_thought",
}

DANGEROUS_COMMAND_TERMS = {
    "rm -rf",
    "git push",
    "format ",
    "del /s",
    "shutdown",
    "curl | sh",
    "Invoke-WebRequest",
    "iwr ",
}

WRITE_OPERATIONS = {"write", "create", "delete", "move", "copy", "patch", "apply_patch"}


def _text(value: Any, fallback: str = "", *, limit: int = 1200) -> str:
    if value is None:
        return fallback
    result = str(value).strip()
    if not result:
        return fallback
    return result[:limit]


def _as_list(value: Any, *, limit: int = 120) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]
    return raw[:limit]


def _dedupe_text(values: list[Any], *, limit: int = 120) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value, limit=500)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        return _safe(asdict(value))
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in SENSITIVE_KEYS):
                safe[key_text] = "[redacted]"
            else:
                safe[key_text] = _safe(item)
        return safe
    if isinstance(value, list):
        return [_safe(item) for item in value[:160]]
    if isinstance(value, tuple):
        return [_safe(item) for item in list(value)[:160]]
    if isinstance(value, str):
        lowered = value.lower()
        if any(hint.lower() in lowered for hint in {"api_key=", "password=", "bearer ", "begin private key"}):
            return "[redacted]"
        return value[:3000]
    return value


def _slug(value: Any, fallback: str = "action") -> str:
    text = _text(value, fallback, limit=160).lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _hash_payload(value: Any) -> str:
    raw = repr(_safe(value))
    return sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_command(command: Any) -> dict[str, Any]:
    text = _text(command, limit=1000)
    lowered = text.lower()
    dangerous = sorted(term for term in DANGEROUS_COMMAND_TERMS if term.lower() in lowered)
    redacted_command = _safe(text)
    return {
        "command": redacted_command if isinstance(redacted_command, str) else "[redacted]",
        "dangerous_terms": dangerous,
        "requires_safeshell": True,
        "requires_approval": True,
        "can_execute": False,
    }


def _normalize_file_operation(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {"path": value}
    path = _text(raw.get("path") or raw.get("file_path") or raw.get("target"), limit=600)
    operation = _slug(raw.get("operation") or raw.get("op") or "patch")
    if operation not in WRITE_OPERATIONS and operation != "read":
        operation = "patch"
    return {
        "path": path,
        "operation": operation,
        "diff_summary": _text(raw.get("diff_summary") or raw.get("summary"), limit=1000),
        "requires_approval": operation in WRITE_OPERATIONS,
        "can_write": False,
    }


@dataclass(frozen=True)
class ActionMaterializationRequest:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_request"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    source_contract_kind: str = ""
    requested_operations: list[dict[str, Any]] = field(default_factory=list)
    requested_commands: list[dict[str, Any]] = field(default_factory=list)
    approval_id: str = ""
    actor_id: str = ""
    request_hash: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    approval_required: bool = True
    policy_matrix_required: bool = True
    safeshell_required: bool = True
    rollback_required: bool = True
    evidence_required: bool = True
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionMaterializationPolicyGate:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_policy_gate"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    decision: str = "requires_approval"
    risk_level: str = "medium"
    approval_id: str = ""
    policy_matrix_ref: str = ""
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_materialize: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class PatchMaterializationPlan:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "patch_materialization_plan"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    workspace_id: str = ""
    file_operations: list[dict[str, Any]] = field(default_factory=list)
    diff_summary: str = ""
    rollback_plan: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    approval_required: bool = True
    rollback_required: bool = True
    evidence_required: bool = True
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class CommandMaterializationPlan:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "command_materialization_plan"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    cwd: str = ""
    shell: str = "git-bash"
    timeout_seconds: int = 120
    commands: list[dict[str, Any]] = field(default_factory=list)
    allow_network: bool = False
    destructive_commands_blocked: bool = True
    required_actions: list[str] = field(default_factory=list)
    approval_required: bool = True
    safeshell_required: bool = True
    evidence_required: bool = True
    can_execute_commands: bool = False
    can_execute: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionMaterializationEvidencePlan:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_evidence_plan"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    required_evidence: list[str] = field(default_factory=list)
    validation_commands: list[dict[str, Any]] = field(default_factory=list)
    diff_required: bool = True
    changed_files_required: bool = True
    validation_required: bool = True
    rollback_required: bool = True
    required_actions: list[str] = field(default_factory=list)
    can_mark_executed: bool = False
    can_execute: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionRollbackPlan:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_rollback_plan"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    rollback_steps: list[str] = field(default_factory=list)
    rollback_commands: list[dict[str, Any]] = field(default_factory=list)
    rollback_evidence_required: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute_rollback: bool = False
    can_execute: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionMaterializationDecision:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_decision"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    decision: str = "requires_approval"
    candidate_id: str = ""
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    request: dict[str, Any] = field(default_factory=dict)
    policy_gate: dict[str, Any] = field(default_factory=dict)
    patch_plan: dict[str, Any] = field(default_factory=dict)
    command_plan: dict[str, Any] = field(default_factory=dict)
    evidence_plan: dict[str, Any] = field(default_factory=dict)
    rollback_plan: dict[str, Any] = field(default_factory=dict)
    can_materialize: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


def dump_action_materialization_contract(value: Any) -> dict[str, Any]:
    return _safe(value)


def build_action_materialization_request(
    *,
    candidate_id: Any = "",
    source_contract_kind: Any = "",
    requested_operations: list[Any] | None = None,
    requested_commands: list[Any] | None = None,
    approval_id: Any = "",
    actor_id: Any = "",
) -> ActionMaterializationRequest:
    operations = [_normalize_file_operation(item) for item in _as_list(requested_operations)]
    commands = [_normalize_command(item.get("command") if isinstance(item, dict) else item) for item in _as_list(requested_commands)]
    required = ["review_action_materialization_request"]
    if not _text(candidate_id):
        required.append("define_candidate_id")
    if operations:
        required.append("review_file_operations")
    if commands:
        required.append("review_command_execution_plan")
    if not _text(approval_id):
        required.append("request_human_approval")
    payload = {
        "candidate_id": _text(candidate_id),
        "source_contract_kind": _text(source_contract_kind),
        "operations": operations,
        "commands": commands,
    }
    return ActionMaterializationRequest(
        candidate_id=_text(candidate_id, limit=240),
        source_contract_kind=_text(source_contract_kind, limit=240),
        requested_operations=operations,
        requested_commands=commands,
        approval_id=_text(approval_id, limit=240),
        actor_id=_text(actor_id, limit=240),
        request_hash=_hash_payload(payload),
        required_actions=_dedupe_text(required),
    )


def build_action_materialization_policy_gate(
    request: ActionMaterializationRequest | dict[str, Any],
    *,
    policy_matrix_ref: Any = "",
    approval_id: Any = "",
    risk_level: Any = "medium",
) -> ActionMaterializationPolicyGate:
    data = dump_action_materialization_contract(request)
    risk = _text(risk_level, "medium", limit=80).lower()
    approval = _text(approval_id or data.get("approval_id"), limit=240)
    blockers: list[str] = []
    warnings: list[str] = []
    required = ["review_policy_matrix_before_materialization"]

    if not approval:
        blockers.append("missing_human_approval")
        required.append("request_human_approval")
    if not _text(policy_matrix_ref):
        blockers.append("missing_policy_matrix_ref")
        required.append("attach_policy_matrix_decision")
    for command in data.get("requested_commands") or []:
        if command.get("dangerous_terms"):
            blockers.append("dangerous_command_detected")
            required.append("remove_or_rewrite_dangerous_command")
    for operation in data.get("requested_operations") or []:
        if operation.get("operation") in {"delete", "move"}:
            warnings.append("destructive_file_operation_requires_extra_review")
            required.append("review_destructive_file_operation")

    decision = "blocked" if blockers or risk in {"critical", "blocked"} else "requires_approval"
    return ActionMaterializationPolicyGate(
        decision=decision,
        risk_level=risk,
        approval_id=approval,
        policy_matrix_ref=_text(policy_matrix_ref, limit=240),
        blockers=_dedupe_text(blockers),
        warnings=_dedupe_text(warnings),
        required_actions=_dedupe_text(required),
        can_materialize=False,
    )


def build_patch_materialization_plan(
    request: ActionMaterializationRequest | dict[str, Any],
    *,
    workspace_id: Any = "",
    diff_summary: Any = "",
    rollback_plan: list[Any] | None = None,
) -> PatchMaterializationPlan:
    data = dump_action_materialization_contract(request)
    operations = data.get("requested_operations") if isinstance(data.get("requested_operations"), list) else []
    required = ["review_patch_materialization_plan", "confirm_candidate_workspace"]
    if not operations:
        required.append("define_file_operations")
    if not _text(workspace_id):
        required.append("define_candidate_workspace")
    return PatchMaterializationPlan(
        candidate_id=_text(data.get("candidate_id"), limit=240),
        workspace_id=_text(workspace_id, limit=500),
        file_operations=operations,
        diff_summary=_text(diff_summary, limit=1200),
        rollback_plan=_dedupe_text(_as_list(rollback_plan or ["restore_previous_workspace_state"])),
        required_actions=_dedupe_text(required),
    )


def build_command_materialization_plan(
    request: ActionMaterializationRequest | dict[str, Any],
    *,
    cwd: Any = "",
    shell: Any = "git-bash",
    timeout_seconds: int = 120,
    allow_network: bool = False,
) -> CommandMaterializationPlan:
    data = dump_action_materialization_contract(request)
    commands = data.get("requested_commands") if isinstance(data.get("requested_commands"), list) else []
    required = ["review_command_materialization_plan", "confirm_safeshell_policy"]
    if not commands:
        required.append("define_commands")
    if not _text(cwd):
        required.append("define_command_cwd")
    if any(command.get("dangerous_terms") for command in commands):
        required.append("remove_or_rewrite_dangerous_command")
    safe_timeout = max(1, min(int(timeout_seconds or 120), 900))
    return CommandMaterializationPlan(
        candidate_id=_text(data.get("candidate_id"), limit=240),
        cwd=_text(cwd, limit=500),
        shell=_text(shell, "git-bash", limit=120),
        timeout_seconds=safe_timeout,
        commands=commands,
        allow_network=bool(allow_network),
        required_actions=_dedupe_text(required),
    )


def build_action_materialization_evidence_plan(
    request: ActionMaterializationRequest | dict[str, Any],
    *,
    validation_commands: list[Any] | None = None,
    required_evidence: list[Any] | None = None,
) -> ActionMaterializationEvidencePlan:
    data = dump_action_materialization_contract(request)
    commands = [_normalize_command(item.get("command") if isinstance(item, dict) else item) for item in _as_list(validation_commands)]
    required = ["prepare_materialization_evidence_capture"]
    if not commands:
        required.append("define_validation_commands")
    evidence = _dedupe_text(_as_list(required_evidence or ["diff_summary", "changed_files", "validation_output", "rollback_plan", "ProcessTrace"]))
    return ActionMaterializationEvidencePlan(
        candidate_id=_text(data.get("candidate_id"), limit=240),
        required_evidence=evidence,
        validation_commands=commands,
        required_actions=_dedupe_text(required),
    )


def build_action_rollback_plan(
    request: ActionMaterializationRequest | dict[str, Any],
    *,
    rollback_steps: list[Any] | None = None,
    rollback_commands: list[Any] | None = None,
) -> ActionRollbackPlan:
    data = dump_action_materialization_contract(request)
    steps = _dedupe_text(_as_list(rollback_steps or ["restore_candidate_workspace_snapshot", "revert_patch_candidate"]))
    commands = [_normalize_command(item.get("command") if isinstance(item, dict) else item) for item in _as_list(rollback_commands)]
    required = ["review_action_rollback_plan"]
    if not steps:
        required.append("define_rollback_steps")
    return ActionRollbackPlan(
        candidate_id=_text(data.get("candidate_id"), limit=240),
        rollback_steps=steps,
        rollback_commands=commands,
        rollback_evidence_required=["rollback_output", "workspace_status", "ProcessTrace"],
        required_actions=_dedupe_text(required),
    )


def decide_action_materialization(
    *,
    request: ActionMaterializationRequest | dict[str, Any],
    policy_gate: ActionMaterializationPolicyGate | dict[str, Any] | None = None,
    patch_plan: PatchMaterializationPlan | dict[str, Any] | None = None,
    command_plan: CommandMaterializationPlan | dict[str, Any] | None = None,
    evidence_plan: ActionMaterializationEvidencePlan | dict[str, Any] | None = None,
    rollback_plan: ActionRollbackPlan | dict[str, Any] | None = None,
) -> ActionMaterializationDecision:
    request_data = dump_action_materialization_contract(request)
    gate = dump_action_materialization_contract(policy_gate or build_action_materialization_policy_gate(request_data))
    patch = dump_action_materialization_contract(patch_plan or build_patch_materialization_plan(request_data))
    command = dump_action_materialization_contract(command_plan or build_command_materialization_plan(request_data))
    evidence = dump_action_materialization_contract(evidence_plan or build_action_materialization_evidence_plan(request_data))
    rollback = dump_action_materialization_contract(rollback_plan or build_action_rollback_plan(request_data))

    blockers: list[str] = []
    required: list[str] = []
    for source in [request_data, gate, patch, command, evidence, rollback]:
        required.extend(_as_list(source.get("required_actions")))
    blockers.extend(_as_list(gate.get("blockers")))
    if not evidence.get("validation_commands"):
        blockers.append("missing_validation_commands")
    if not rollback.get("rollback_steps"):
        blockers.append("missing_rollback_plan")

    decision = "blocked" if blockers else "requires_approval"
    return ActionMaterializationDecision(
        decision=decision,
        candidate_id=_text(request_data.get("candidate_id"), limit=240),
        blockers=_dedupe_text(blockers),
        required_actions=_dedupe_text(required),
        request=request_data,
        policy_gate=gate,
        patch_plan=patch,
        command_plan=command,
        evidence_plan=evidence,
        rollback_plan=rollback,
    )


def build_action_materialization_sequence(
    *,
    candidate_id: Any = "",
    source_contract_kind: Any = "",
    requested_operations: list[Any] | None = None,
    requested_commands: list[Any] | None = None,
    validation_commands: list[Any] | None = None,
    workspace_id: Any = "",
    cwd: Any = "",
) -> list[Any]:
    request = build_action_materialization_request(
        candidate_id=candidate_id,
        source_contract_kind=source_contract_kind,
        requested_operations=requested_operations,
        requested_commands=requested_commands,
    )
    gate = build_action_materialization_policy_gate(request, policy_matrix_ref="")
    patch = build_patch_materialization_plan(request, workspace_id=workspace_id)
    command = build_command_materialization_plan(request, cwd=cwd)
    evidence = build_action_materialization_evidence_plan(request, validation_commands=validation_commands)
    rollback = build_action_rollback_plan(request)
    decision = decide_action_materialization(
        request=request,
        policy_gate=gate,
        patch_plan=patch,
        command_plan=command,
        evidence_plan=evidence,
        rollback_plan=rollback,
    )
    return [request, gate, patch, command, evidence, rollback, decision]
