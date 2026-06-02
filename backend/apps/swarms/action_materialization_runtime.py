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


def _content_text(value: Any, *, limit: int = 20000) -> str:
    """Preserve file content exactly for approval resume matching."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:limit]
    return str(value)[:limit]


def _normalize_operation(operation: Any) -> dict[str, Any]:
    """Normalize rollback/materialization file operations for ToolRuntime."""
    if not isinstance(operation, dict):
        return {
            "path": "",
            "operation": "patch",
            "content": "",
            "old_text": "",
            "new_text": "",
            "proposed_content": "",
            "replace_all": False,
            "requires_approval": True,
            "can_write": False,
        }

    raw = operation or {}
    op = _slug(raw.get("operation") or raw.get("type") or "patch")
    if op not in WRITE_OPERATIONS and op not in {"diff"}:
        op = "patch"

    content = _content_text(raw.get("content"), limit=20000)
    old_text = _content_text(raw.get("old_text"), limit=20000)
    new_text = _content_text(raw.get("new_text"), limit=20000)
    proposed_content = _content_text(
        raw.get("proposed_content") if raw.get("proposed_content") is not None else raw.get("content"),
        limit=20000,
    )

    return {
        "path": _text(raw.get("path") or raw.get("file") or raw.get("target_path"), limit=600),
        "operation": op,
        "content": content,
        "old_text": old_text,
        "new_text": new_text,
        "proposed_content": proposed_content,
        "replace_all": bool(raw.get("replace_all", False)),
        "diff_summary": _text(raw.get("diff_summary") or raw.get("summary"), limit=1000),
        "requires_approval": op in WRITE_OPERATIONS,
        "can_write": False,
    }


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
        "content": _content_text(raw.get("content"), limit=20000),
        "old_text": _content_text(raw.get("old_text"), limit=20000),
        "new_text": _content_text(raw.get("new_text"), limit=20000),
        "proposed_content": _content_text(raw.get("proposed_content") if raw.get("proposed_content") is not None else raw.get("content"), limit=20000),
        "replace_all": bool(raw.get("replace_all", False)),
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



@dataclass(frozen=True)
class ActionMaterializationExecutionRequest:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_execution_request"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    workspace_path: str = ""
    approval_id: str = ""
    policy_matrix_ref: str = ""
    operations: list[dict[str, Any]] = field(default_factory=list)
    commands: list[dict[str, Any]] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionMaterializationExecutionResult:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_execution_result"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    execution_status: str = "blocked"
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    command_outputs: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    rollback_plan: dict[str, Any] = field(default_factory=dict)
    can_mark_executed: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


def build_action_materialization_execution_request(
    decision: ActionMaterializationDecision | dict[str, Any],
    *,
    workspace_path: Any = "",
    approval_id: Any = "",
    policy_matrix_ref: Any = "",
) -> ActionMaterializationExecutionRequest:
    data = dump_action_materialization_contract(decision)
    request = data.get("request") if isinstance(data.get("request"), dict) else {}
    patch_plan = data.get("patch_plan") if isinstance(data.get("patch_plan"), dict) else {}
    command_plan = data.get("command_plan") if isinstance(data.get("command_plan"), dict) else {}

    operations = patch_plan.get("file_operations") if isinstance(patch_plan.get("file_operations"), list) else request.get("requested_operations", [])
    commands = command_plan.get("commands") if isinstance(command_plan.get("commands"), list) else request.get("requested_commands", [])

    required = ["review_action_materialization_execution_request"]
    if not _text(workspace_path):
        required.append("define_workspace_path")
    if not _text(approval_id):
        required.append("attach_approved_runtime_approval_id")
    if not _text(policy_matrix_ref):
        required.append("attach_policy_matrix_decision")
    if data.get("decision") == "blocked":
        required.append("resolve_materialization_blockers_before_execution")
    if not operations and not commands:
        required.append("define_operations_or_commands")

    return ActionMaterializationExecutionRequest(
        candidate_id=_text(data.get("candidate_id") or request.get("candidate_id"), limit=240),
        workspace_path=_text(workspace_path, limit=1000),
        approval_id=_text(approval_id, limit=240),
        policy_matrix_ref=_text(policy_matrix_ref, limit=240),
        operations=operations if isinstance(operations, list) else [],
        commands=commands if isinstance(commands, list) else [],
        required_actions=_dedupe_text(required),
    )


def _tool_input_for_operation(operation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    op = _slug(operation.get("operation") or "patch")
    path = _text(operation.get("path"), limit=600)
    if op in {"write", "create"}:
        content = _content_text(operation.get("content") if operation.get("content") is not None else operation.get("proposed_content"), limit=20000)
        return "Write", {"path": path, "content": content}
    if op in {"edit", "patch"}:
        old_text = _content_text(operation.get("old_text"), limit=20000)
        new_text = _content_text(operation.get("new_text"), limit=20000)
        if not old_text:
            proposed = _content_text(operation.get("proposed_content") if operation.get("proposed_content") is not None else operation.get("content"), limit=20000)
            return "Diff", {"path": path, "proposed_content": proposed}
        return "Edit", {"path": path, "old_text": old_text, "new_text": new_text, "replace_all": bool(operation.get("replace_all", False))}
    if op == "diff":
        proposed = _content_text(operation.get("proposed_content") if operation.get("proposed_content") is not None else operation.get("content"), limit=20000)
        return "Diff", {"path": path, "proposed_content": proposed}
    proposed = _content_text(operation.get("proposed_content") if operation.get("proposed_content") is not None else operation.get("content"), limit=20000)
    return "Diff", {"path": path, "proposed_content": proposed}


def _history_result_summary(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "tool": item.get("tool"),
            "status": item.get("status"),
            "ok": item.get("ok"),
            "result": _safe(item.get("result") or {}),
            "error": _text(item.get("error"), limit=1200),
        }
        for item in history
    ]


def execute_action_materialization_runtime(
    decision: ActionMaterializationDecision | dict[str, Any],
    *,
    workspace_path: Any = "",
    approval_id: Any = "",
    policy_matrix_ref: Any = "",
    swarm_id: Any = "",
    agent_id: Any = "",
    task_id: Any = "",
    allowed_tools: list[Any] | None = None,
) -> ActionMaterializationExecutionResult:
    from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, tool_runtime

    request = build_action_materialization_execution_request(
        decision,
        workspace_path=workspace_path,
        approval_id=approval_id,
        policy_matrix_ref=policy_matrix_ref,
    )

    hard_required = [
        action for action in request.required_actions
        if action not in {"review_action_materialization_execution_request"}
    ]
    if hard_required:
        return ActionMaterializationExecutionResult(
            candidate_id=request.candidate_id,
            execution_status="blocked",
            blockers=hard_required,
            required_actions=request.required_actions,
            rollback_plan=dump_action_materialization_contract(decision).get("rollback_plan", {}),
        )

    tool_names = [str(item) for item in (allowed_tools or ["Write", "Edit", "Diff", "SafeShell"])]
    history: list[dict[str, Any]] = []
    changed_files: list[str] = []
    command_outputs: list[dict[str, Any]] = []
    blockers: list[str] = []
    required: list[str] = ["review_action_materialization_execution_result"]

    def run_tool(tool_name: str, tool_input: dict[str, Any]) -> None:
        nonlocal history
        result = tool_runtime.execute_tool(
            ToolCall(name=tool_name, input=tool_input, raw_name=tool_name),
            ToolExecutionContext(
                workspace_path=request.workspace_path,
                session_id="action-materialization-runtime",
                swarm_id=_text(swarm_id, "action-materialization", limit=240),
                agent_id=_text(agent_id, "action-materializer", limit=240),
                task_id=_text(task_id, request.candidate_id or "action-materialization", limit=240),
                allowed_tools=tool_names,
                require_human_approval=True,
                metadata={
                    "task_type": "action_materialization_runtime",
                    "policy_resume_approved": True,
                    "approval_id": request.approval_id,
                    "resume_tool_input": tool_input,
                    "policy_matrix_ref": request.policy_matrix_ref,
                    "candidate_id": request.candidate_id,
                },
            ),
            history=history,
        )
        if not result.ok:
            blockers.append(f"{tool_name.lower()}_failed_or_not_approved")
            required.append("review_failed_materialization_tool_result")

    for operation in request.operations:
        tool_name, tool_input = _tool_input_for_operation(operation if isinstance(operation, dict) else {})
        run_tool(tool_name, tool_input)
        path = _text(tool_input.get("path"), limit=600)
        if path and tool_name in {"Write", "Edit"}:
            changed_files.append(path)

    for command in request.commands:
        command_text = _text(command.get("command") if isinstance(command, dict) else command, limit=1000)
        if not command_text:
            continue
        tool_input = {"command": command_text}
        before = len(history)
        run_tool("SafeShell", tool_input)
        for item in history[before:]:
            if item.get("tool") == "SafeShell":
                command_outputs.append(_safe(item.get("result") or {}))

    tool_results = _history_result_summary(history)
    any_failed = any(not item.get("ok") for item in tool_results)
    executed_any = bool(tool_results)
    status = "executed" if executed_any and not any_failed and not blockers else "blocked"

    return ActionMaterializationExecutionResult(
        candidate_id=request.candidate_id,
        execution_status=status,
        tool_results=tool_results,
        changed_files=_dedupe_text(changed_files),
        command_outputs=command_outputs,
        evidence_refs=["tool_runtime_evidence", "ProcessTrace"] if status == "executed" else [],
        blockers=_dedupe_text(blockers),
        required_actions=_dedupe_text(required),
        rollback_plan=dump_action_materialization_contract(decision).get("rollback_plan", {}),
        can_mark_executed=status == "executed",
    )


@dataclass(frozen=True)
class ActionMaterializationPostValidationRequest:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_post_validation_request"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    workspace_path: str = ""
    approval_id: str = ""
    policy_matrix_ref: str = ""
    validation_commands: list[dict[str, Any]] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionMaterializationPostValidationResult:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_post_validation_result"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    validation_status: str = "blocked"
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_mark_validated: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionMaterializationRollbackRequest:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_rollback_request"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    workspace_path: str = ""
    approval_id: str = ""
    policy_matrix_ref: str = ""
    rollback_operations: list[dict[str, Any]] = field(default_factory=list)
    rollback_commands: list[dict[str, Any]] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionMaterializationRollbackResult:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_rollback_result"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    rollback_status: str = "blocked"
    rollback_results: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_mark_rolled_back: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class ActionMaterializationPostValidationGate:
    source_kind: str = "action_materialization_runtime"
    materialization_kind: str = "action_materialization_post_validation_gate"
    materialization_version: str = ACTION_MATERIALIZATION_VERSION
    candidate_id: str = ""
    gate_status: str = "blocked"
    execution_status: str = "missing"
    post_validation_status: str = "missing"
    rollback_status: str = "missing"
    rollback_ready: bool = False
    completion_conditions: dict[str, bool] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_mark_materialization_safe: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


def _materialization_contract_dict(value: Any) -> dict[str, Any]:
    dumped = dump_action_materialization_contract(value)
    return dumped if isinstance(dumped, dict) else {}


def build_action_materialization_post_validation_request(
    execution_result: Any,
    *,
    validation_commands: list[Any] | None = None,
    workspace_path: Any = "",
    approval_id: Any = "",
    policy_matrix_ref: Any = "",
) -> ActionMaterializationPostValidationRequest:
    execution = _materialization_contract_dict(execution_result)
    raw_commands = validation_commands if validation_commands is not None else execution.get("validation_commands", [])
    commands = [_normalize_command(command) for command in (raw_commands or [])]

    required = ["review_action_materialization_post_validation_request"]
    if execution.get("execution_status") != "executed" or execution.get("can_mark_executed") is not True:
        required.append("execute_materialization_before_post_validation")
    if not _text(workspace_path):
        required.append("define_workspace_path")
    if not _text(approval_id):
        required.append("attach_approved_runtime_approval_id")
    if not _text(policy_matrix_ref):
        required.append("attach_policy_matrix_decision")
    if not commands:
        required.append("define_post_validation_commands")

    return ActionMaterializationPostValidationRequest(
        candidate_id=_text(execution.get("candidate_id"), limit=240),
        workspace_path=_text(workspace_path, limit=1000),
        approval_id=_text(approval_id, limit=240),
        policy_matrix_ref=_text(policy_matrix_ref, limit=240),
        validation_commands=commands,
        required_actions=_dedupe_text(required),
    )


def execute_action_materialization_post_validation(
    execution_result: Any,
    *,
    validation_commands: list[Any] | None = None,
    workspace_path: Any = "",
    approval_id: Any = "",
    policy_matrix_ref: Any = "",
    swarm_id: Any = "",
    agent_id: Any = "",
    task_id: Any = "",
) -> ActionMaterializationPostValidationResult:
    from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, tool_runtime

    request = build_action_materialization_post_validation_request(
        execution_result,
        validation_commands=validation_commands,
        workspace_path=workspace_path,
        approval_id=approval_id,
        policy_matrix_ref=policy_matrix_ref,
    )
    hard_required = [
        action for action in request.required_actions
        if action not in {"review_action_materialization_post_validation_request"}
    ]
    if hard_required:
        return ActionMaterializationPostValidationResult(
            candidate_id=request.candidate_id,
            validation_status="blocked",
            blockers=hard_required,
            required_actions=request.required_actions,
        )

    history: list[dict[str, Any]] = []
    blockers: list[str] = []
    required = ["review_action_materialization_post_validation_result"]

    for command in request.validation_commands:
        command_text = _text(command.get("command"), limit=1000)
        if not command_text:
            blockers.append("empty_validation_command")
            continue
        result = tool_runtime.execute_tool(
            ToolCall(name="SafeShell", input={"command": command_text}, raw_name="SafeShell"),
            ToolExecutionContext(
                workspace_path=request.workspace_path,
                session_id="action-materialization-post-validation",
                swarm_id=_text(swarm_id, "action-materialization", limit=240),
                agent_id=_text(agent_id, "action-validator", limit=240),
                task_id=_text(task_id, request.candidate_id or "action-materialization-validation", limit=240),
                allowed_tools=["SafeShell"],
                require_human_approval=True,
                metadata={
                    "task_type": "action_materialization_post_validation",
                    "policy_resume_approved": True,
                    "approval_id": request.approval_id,
                    "resume_tool_input": {"command": command_text},
                    "policy_matrix_ref": request.policy_matrix_ref,
                    "candidate_id": request.candidate_id,
                },
            ),
            history=history,
        )
        if not result.ok:
            blockers.append("post_validation_command_failed_or_not_approved")
            required.append("review_failed_post_validation_command")

    validation_results = _history_result_summary(history)
    passed = bool(validation_results) and all(item.get("ok") is True for item in validation_results) and not blockers

    return ActionMaterializationPostValidationResult(
        candidate_id=request.candidate_id,
        validation_status="passed" if passed else "failed" if validation_results else "blocked",
        validation_results=validation_results,
        evidence_refs=["post_validation_evidence", "ProcessTrace"] if passed else [],
        blockers=_dedupe_text(blockers),
        required_actions=_dedupe_text(required),
        can_mark_validated=passed,
    )


def build_action_materialization_rollback_request(
    execution_result: Any,
    *,
    rollback_operations: list[Any] | None = None,
    rollback_commands: list[Any] | None = None,
    workspace_path: Any = "",
    approval_id: Any = "",
    policy_matrix_ref: Any = "",
) -> ActionMaterializationRollbackRequest:
    execution = _materialization_contract_dict(execution_result)
    rollback_plan = execution.get("rollback_plan") if isinstance(execution.get("rollback_plan"), dict) else {}
    raw_operations = rollback_operations if rollback_operations is not None else rollback_plan.get("rollback_operations", [])
    raw_commands = rollback_commands if rollback_commands is not None else rollback_plan.get("rollback_commands", [])

    operations = [_normalize_operation(operation) for operation in (raw_operations or [])]
    commands = [_normalize_command(command) for command in (raw_commands or [])]

    required = ["review_action_materialization_rollback_request"]
    if not _text(workspace_path):
        required.append("define_workspace_path")
    if not _text(approval_id):
        required.append("attach_approved_runtime_approval_id")
    if not _text(policy_matrix_ref):
        required.append("attach_policy_matrix_decision")
    if not operations and not commands:
        required.append("define_rollback_operations_or_commands")

    return ActionMaterializationRollbackRequest(
        candidate_id=_text(execution.get("candidate_id"), limit=240),
        workspace_path=_text(workspace_path, limit=1000),
        approval_id=_text(approval_id, limit=240),
        policy_matrix_ref=_text(policy_matrix_ref, limit=240),
        rollback_operations=operations,
        rollback_commands=commands,
        required_actions=_dedupe_text(required),
    )


def execute_action_materialization_rollback_runtime(
    execution_result: Any,
    *,
    rollback_operations: list[Any] | None = None,
    rollback_commands: list[Any] | None = None,
    workspace_path: Any = "",
    approval_id: Any = "",
    policy_matrix_ref: Any = "",
    swarm_id: Any = "",
    agent_id: Any = "",
    task_id: Any = "",
) -> ActionMaterializationRollbackResult:
    from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, tool_runtime

    request = build_action_materialization_rollback_request(
        execution_result,
        rollback_operations=rollback_operations,
        rollback_commands=rollback_commands,
        workspace_path=workspace_path,
        approval_id=approval_id,
        policy_matrix_ref=policy_matrix_ref,
    )
    hard_required = [
        action for action in request.required_actions
        if action not in {"review_action_materialization_rollback_request"}
    ]
    if hard_required:
        return ActionMaterializationRollbackResult(
            candidate_id=request.candidate_id,
            rollback_status="blocked",
            blockers=hard_required,
            required_actions=request.required_actions,
        )

    history: list[dict[str, Any]] = []
    blockers: list[str] = []
    required = ["review_action_materialization_rollback_result"]

    def run_tool(tool_name: str, tool_input: dict[str, Any]) -> None:
        result = tool_runtime.execute_tool(
            ToolCall(name=tool_name, input=tool_input, raw_name=tool_name),
            ToolExecutionContext(
                workspace_path=request.workspace_path,
                session_id="action-materialization-rollback",
                swarm_id=_text(swarm_id, "action-materialization", limit=240),
                agent_id=_text(agent_id, "action-rollback", limit=240),
                task_id=_text(task_id, request.candidate_id or "action-materialization-rollback", limit=240),
                allowed_tools=["Write", "Edit", "Diff", "SafeShell"],
                require_human_approval=True,
                metadata={
                    "task_type": "action_materialization_rollback",
                    "policy_resume_approved": True,
                    "approval_id": request.approval_id,
                    "resume_tool_input": tool_input,
                    "policy_matrix_ref": request.policy_matrix_ref,
                    "candidate_id": request.candidate_id,
                },
            ),
            history=history,
        )
        if not result.ok:
            blockers.append(f"{tool_name.lower()}_rollback_failed_or_not_approved")
            required.append("review_failed_rollback_tool_result")

    for operation in request.rollback_operations:
        tool_name, tool_input = _tool_input_for_operation(operation)
        run_tool(tool_name, tool_input)

    for command in request.rollback_commands:
        command_text = _text(command.get("command"), limit=1000)
        if not command_text:
            continue
        run_tool("SafeShell", {"command": command_text})

    rollback_results = _history_result_summary(history)
    rolled_back = bool(rollback_results) and all(item.get("ok") is True for item in rollback_results) and not blockers

    return ActionMaterializationRollbackResult(
        candidate_id=request.candidate_id,
        rollback_status="rolled_back" if rolled_back else "failed" if rollback_results else "blocked",
        rollback_results=rollback_results,
        evidence_refs=["rollback_evidence", "ProcessTrace"] if rolled_back else [],
        blockers=_dedupe_text(blockers),
        required_actions=_dedupe_text(required),
        can_mark_rolled_back=rolled_back,
    )


def build_action_materialization_post_validation_gate(
    *,
    execution_result: Any,
    post_validation_result: Any = None,
    rollback_request: Any = None,
    rollback_result: Any = None,
    rollback_required: bool = True,
) -> ActionMaterializationPostValidationGate:
    execution = _materialization_contract_dict(execution_result)
    post_validation = _materialization_contract_dict(post_validation_result) if post_validation_result is not None else {}
    rollback_request_data = _materialization_contract_dict(rollback_request) if rollback_request is not None else {}
    rollback_result_data = _materialization_contract_dict(rollback_result) if rollback_result is not None else {}

    rollback_plan = execution.get("rollback_plan") if isinstance(execution.get("rollback_plan"), dict) else {}
    execution_ok = execution.get("execution_status") == "executed" and execution.get("can_mark_executed") is True
    validation_ok = post_validation.get("validation_status") == "passed" and post_validation.get("can_mark_validated") is True
    rollback_executed = rollback_result_data.get("rollback_status") == "rolled_back" and rollback_result_data.get("can_mark_rolled_back") is True
    rollback_available = bool(
        rollback_plan
        or rollback_request_data.get("rollback_operations")
        or rollback_request_data.get("rollback_commands")
        or rollback_executed
    )
    rollback_ready = bool(not rollback_required or rollback_available or rollback_executed)

    conditions = {
        "execution_ok": execution_ok,
        "post_validation_ok": validation_ok,
        "rollback_ready": rollback_ready,
    }

    blockers: list[str] = []
    required: list[str] = ["review_action_materialization_post_validation_gate"]

    if not execution_ok:
        blockers.append("materialization_execution_not_confirmed")
        required.append("execute_action_materialization_runtime")
    if not validation_ok:
        blockers.append("post_validation_not_confirmed")
        required.append("run_post_materialization_validation")
    if not rollback_ready:
        blockers.append("rollback_not_ready")
        required.append("define_or_execute_controlled_rollback")

    safe = all(conditions.values()) and not blockers
    evidence_refs = []
    evidence_refs.extend(_as_list(execution.get("evidence_refs")))
    evidence_refs.extend(_as_list(post_validation.get("evidence_refs")))
    evidence_refs.extend(_as_list(rollback_result_data.get("evidence_refs")))

    return ActionMaterializationPostValidationGate(
        candidate_id=_text(execution.get("candidate_id") or post_validation.get("candidate_id") or rollback_result_data.get("candidate_id"), limit=240),
        gate_status="completed" if safe else "blocked",
        execution_status=_text(execution.get("execution_status"), "missing", limit=120),
        post_validation_status=_text(post_validation.get("validation_status"), "missing", limit=120),
        rollback_status=_text(rollback_result_data.get("rollback_status"), "ready" if rollback_ready else "missing", limit=120),
        rollback_ready=rollback_ready,
        completion_conditions=conditions,
        evidence_refs=_dedupe_text(evidence_refs),
        blockers=_dedupe_text(blockers),
        required_actions=_dedupe_text(required),
        can_mark_materialization_safe=safe,
    )

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
