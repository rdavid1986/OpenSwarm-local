"""Side-effect-free code action contract helpers.

ACI-CODE.1 defines a normalized representation for code-related actions before
anything is executed. These helpers do not write files, run commands, mutate
state, call models, or authorize execution.
"""

from __future__ import annotations

from typing import Any


MISSING = "missing"
UNKNOWN = "unknown"
MAX_TEXT = 600
MAX_LIST_ITEMS = 40
MAX_DICT_ITEMS = 80

VALID_CODE_ACTION_TYPES = {
    "inspect",
    "edit_file",
    "create_file",
    "delete_file",
    "move_file",
    "copy_file",
    "run_command",
    "apply_patch",
    "validate",
    "review_diff",
}

VALID_CODE_ACTION_STATUS = {
    "draft",
    "pending_approval",
    "approved",
    "blocked",
    "executed",
    "failed",
    "cancelled",
}

VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}


def _as_text(value: Any, *, max_chars: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:max_chars]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _bounded_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _as_text(value)
    if isinstance(value, list | tuple | set):
        return [_bounded_value(item) for item in list(value)[:MAX_LIST_ITEMS]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, key in enumerate(sorted(value.keys(), key=lambda item: str(item))):
            if index >= MAX_DICT_ITEMS:
                result["__truncated__"] = True
                break
            result[str(key)[:120]] = _bounded_value(value.get(key))
        return result
    return _as_text(value)


def normalize_code_action_file(value: Any) -> dict[str, Any]:
    """Normalize one affected file descriptor."""

    raw = _as_dict(value)
    path = _as_text(raw.get("path") or raw.get("file") or raw.get("source_path"))
    operation = _as_text(raw.get("operation") or raw.get("action")) or "inspect"
    if operation not in {"inspect", "read", "write", "create", "delete", "move", "copy", "patch", "validate"}:
        operation = UNKNOWN

    return _bounded_value(
        {
            "path": path or None,
            "operation": operation,
            "required": bool(raw.get("required", True)),
            "allowed": bool(raw.get("allowed", False)),
            "reason": _as_text(raw.get("reason") or raw.get("selection_reason")) or "code_action_file",
            "metadata": _bounded_value(raw.get("metadata") or {}),
        }
    )


def normalize_code_action_command(value: Any) -> dict[str, Any]:
    """Normalize one suggested command without running it."""

    raw = _as_dict(value)
    command = _as_text(raw.get("command"), max_chars=1000)
    return _bounded_value(
        {
            "command": command or None,
            "cwd": _as_text(raw.get("cwd")) or ".",
            "timeout_seconds": int(raw.get("timeout_seconds") or 30)
            if str(raw.get("timeout_seconds") or "").isdigit()
            else 30,
            "max_output_chars": int(raw.get("max_output_chars") or 12000)
            if str(raw.get("max_output_chars") or "").isdigit()
            else 12000,
            "purpose": _as_text(raw.get("purpose") or raw.get("description")) or "validate_code_action",
            "requires_approval": bool(raw.get("requires_approval", True)),
            "executed": False,
        }
    )


def infer_code_action_risk(action_type: str, files: list[Any], commands: list[Any]) -> str:
    """Infer conservative risk from normalized action data."""

    normalized_type = _as_text(action_type)
    normalized_files = [normalize_code_action_file(item) for item in files]
    normalized_commands = [normalize_code_action_command(item) for item in commands]

    if normalized_type in {"delete_file", "move_file"}:
        return "high"
    if normalized_type == "run_command":
        return "medium"
    if normalized_type in {"edit_file", "create_file", "apply_patch"}:
        return "medium"

    for file_item in normalized_files:
        if file_item.get("operation") in {"delete", "move"}:
            return "high"
        if file_item.get("operation") in {"write", "create", "patch"}:
            return "medium"

    for command_item in normalized_commands:
        command = _as_text(command_item.get("command")).lower()
        if any(term in command for term in {"rm -rf", "git push", "delete", "format", "del /s"}):
            return "critical"
        if command:
            return "medium"

    return "low"


def build_code_action_contract(
    *,
    action_id: str | None = None,
    action_type: str | None = None,
    title: str | None = None,
    description: str | None = None,
    affected_files: list[Any] | None = None,
    suggested_commands: list[Any] | None = None,
    expected_evidence: list[Any] | None = None,
    required_permissions: list[Any] | None = None,
    status: str | None = None,
    risk_level: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized code action contract without executing anything."""

    resolved_type = _as_text(action_type)
    if resolved_type not in VALID_CODE_ACTION_TYPES:
        resolved_type = UNKNOWN if resolved_type else MISSING

    resolved_status = _as_text(status) or "draft"
    if resolved_status not in VALID_CODE_ACTION_STATUS:
        resolved_status = "draft"

    files = [normalize_code_action_file(item) for item in _as_list(affected_files)]
    commands = [normalize_code_action_command(item) for item in _as_list(suggested_commands)]
    inferred_risk = infer_code_action_risk(resolved_type, files, commands)

    resolved_risk = _as_text(risk_level) or inferred_risk
    if resolved_risk not in VALID_RISK_LEVELS:
        resolved_risk = inferred_risk

    permissions = [_as_text(item) for item in _as_list(required_permissions) if _as_text(item)]
    if resolved_type in {"edit_file", "create_file", "delete_file", "move_file", "copy_file", "apply_patch"}:
        if "filesystem_write" not in permissions:
            permissions.append("filesystem_write")
    if resolved_type == "run_command" and "command_execution" not in permissions:
        permissions.append("command_execution")

    return _bounded_value(
        {
            "action_id": _as_text(action_id) or None,
            "action_type": resolved_type,
            "title": _as_text(title) or None,
            "description": _as_text(description) or None,
            "status": resolved_status,
            "risk_level": resolved_risk,
            "requires_approval": resolved_risk in {"medium", "high", "critical"} or bool(commands),
            "affected_files": files,
            "suggested_commands": commands,
            "expected_evidence": _bounded_value(_as_list(expected_evidence)),
            "required_permissions": permissions,
            "source": _as_text(source) or "code_action_contract",
            "executed": False,
            "execution_result": None,
            "metadata": _bounded_value(metadata or {}),
        }
    )


DANGEROUS_COMMAND_TERMS = {
    "rm -rf",
    "git push",
    "git push --force",
    "format",
    "del /s",
    "rmdir /s",
    "shutdown",
    "curl ",
    "wget ",
    "powershell -enc",
    "invoke-webrequest",
    "invoke-expression",
}

WRITE_OPERATIONS = {"write", "create", "delete", "move", "copy", "patch"}
WRITE_ACTION_TYPES = {"edit_file", "create_file", "delete_file", "move_file", "copy_file", "apply_patch"}


def _normalize_path(value: Any) -> str:
    return _as_text(value).replace("\\", "/").strip()


def _path_has_traversal(path: str) -> bool:
    normalized = _normalize_path(path)
    parts = [part for part in normalized.split("/") if part]
    return ".." in parts or normalized.startswith("/") or ":" in normalized.split("/")[0]


def _path_matches(path: str, patterns: list[Any]) -> bool:
    normalized_path = _normalize_path(path)
    for raw_pattern in patterns:
        pattern = _normalize_path(raw_pattern)
        if not pattern:
            continue
        if normalized_path == pattern or normalized_path.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def _command_has_dangerous_term(command: str) -> list[str]:
    lowered = _as_text(command, max_chars=1000).lower()
    return sorted(term for term in DANGEROUS_COMMAND_TERMS if term in lowered)


def _guard_risk_level(reasons: list[dict[str, Any]], fallback: str) -> str:
    if any(reason.get("severity") == "critical" for reason in reasons):
        return "critical"
    if any(reason.get("severity") == "high" for reason in reasons):
        return "high"
    if any(reason.get("severity") == "medium" for reason in reasons):
        return "medium"
    return fallback if fallback in VALID_RISK_LEVELS else "low"


def normalize_code_action_contract(value: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize an existing or partial code action contract."""

    raw = _as_dict(value)
    return build_code_action_contract(
        action_id=raw.get("action_id"),
        action_type=raw.get("action_type"),
        title=raw.get("title"),
        description=raw.get("description"),
        affected_files=_as_list(raw.get("affected_files")),
        suggested_commands=_as_list(raw.get("suggested_commands")),
        expected_evidence=_as_list(raw.get("expected_evidence")),
        required_permissions=_as_list(raw.get("required_permissions")),
        status=raw.get("status"),
        risk_level=raw.get("risk_level"),
        source=raw.get("source"),
        metadata=_as_dict(raw.get("metadata")),
    )


def evaluate_code_action_guard(
    action: dict[str, Any] | None,
    *,
    allowed_files: list[Any] | None = None,
    forbidden_files: list[Any] | None = None,
    granted_permissions: list[Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a code action contract without executing it."""

    normalized = normalize_code_action_contract(_as_dict(action))
    allowed = _as_list(allowed_files)
    forbidden = _as_list(forbidden_files)
    granted = {_as_text(item) for item in _as_list(granted_permissions) if _as_text(item)}
    required = {_as_text(item) for item in _as_list(normalized.get("required_permissions")) if _as_text(item)}

    reasons: list[dict[str, Any]] = []

    def add_reason(code: str, message: str, *, severity: str = "medium", source: Any | None = None) -> None:
        reasons.append(
            _bounded_value(
                {
                    "code": code,
                    "message": message,
                    "severity": severity,
                    "source": source,
                }
            )
        )

    missing_permissions = sorted(permission for permission in required if permission not in granted)
    for permission in missing_permissions:
        add_reason(
            "permission_missing",
            "Required permission is not granted.",
            severity="high",
            source={"permission": permission},
        )

    for file_item in _as_list(normalized.get("affected_files")):
        file_dict = _as_dict(file_item)
        path = _normalize_path(file_dict.get("path"))
        operation = _as_text(file_dict.get("operation"))
        if not path and operation in WRITE_OPERATIONS:
            add_reason("file_path_missing", "Writable code action file is missing a path.", severity="high", source=file_dict)
            continue

        if path and _path_has_traversal(path):
            add_reason("path_traversal_not_allowed", "Affected file path is outside the allowed relative path shape.", severity="critical", source=file_dict)

        if path and forbidden and _path_matches(path, forbidden):
            add_reason("file_forbidden", "Affected file overlaps forbidden files.", severity="high", source=file_dict)

        if path and allowed and operation in WRITE_OPERATIONS and not _path_matches(path, allowed):
            add_reason("file_not_allowed", "Writable affected file is not in allowed files.", severity="high", source=file_dict)

    for command_item in _as_list(normalized.get("suggested_commands")):
        command_dict = _as_dict(command_item)
        command = _as_text(command_dict.get("command"), max_chars=1000)
        dangerous_terms = _command_has_dangerous_term(command)
        if dangerous_terms:
            add_reason(
                "dangerous_command",
                "Suggested command contains dangerous terms.",
                severity="critical",
                source={"command": command, "terms": dangerous_terms},
            )

    if normalized.get("risk_level") == "critical":
        add_reason(
            "critical_risk_requires_block",
            "Critical code action risk is blocked before execution.",
            severity="critical",
            source={"risk_level": normalized.get("risk_level")},
        )

    guard_status = "blocked" if any(reason.get("severity") in {"high", "critical"} for reason in reasons) else "pending_approval"
    return _bounded_value(
        {
            "guard_status": guard_status,
            "allowed": guard_status != "blocked",
            "risk_level": _guard_risk_level(reasons, _as_text(normalized.get("risk_level"))),
            "reasons": reasons,
            "reason_count": len(reasons),
            "missing_permissions": missing_permissions,
            "execution_allowed": False,
            "execution_performed": False,
            "next_status": "blocked" if guard_status == "blocked" else "pending_approval",
        }
    )


def apply_code_action_guard(
    action: dict[str, Any] | None,
    *,
    allowed_files: list[Any] | None = None,
    forbidden_files: list[Any] | None = None,
    granted_permissions: list[Any] | None = None,
) -> dict[str, Any]:
    """Attach guard result and advance only to pending_approval or blocked."""

    normalized = normalize_code_action_contract(_as_dict(action))
    guard = evaluate_code_action_guard(
        normalized,
        allowed_files=allowed_files,
        forbidden_files=forbidden_files,
        granted_permissions=granted_permissions,
    )
    merged = dict(normalized)
    merged["guard"] = guard
    merged["status"] = guard["next_status"]
    merged["executed"] = False
    merged["execution_result"] = None
    return _bounded_value(merged)


VALID_CODE_ACTION_EVIDENCE_STATUS = {
    "missing",
    "partial",
    "failed",
    "passed",
    "unknown",
}


def normalize_code_action_command_evidence(value: Any) -> dict[str, Any]:
    """Normalize command execution evidence without executing commands."""

    raw = _as_dict(value)
    exit_code_raw = raw.get("exit_code")
    try:
        exit_code = int(exit_code_raw)
    except Exception:
        exit_code = None

    stdout = _as_text(raw.get("stdout"), max_chars=2000)
    stderr = _as_text(raw.get("stderr"), max_chars=2000)

    if exit_code == 0:
        status = "passed"
    elif exit_code is None:
        status = "unknown"
    else:
        status = "failed"

    return _bounded_value(
        {
            "command": _as_text(raw.get("command"), max_chars=1000) or None,
            "cwd": _as_text(raw.get("cwd")) or ".",
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "status": status,
            "has_output": bool(stdout or stderr),
        }
    )


def build_code_action_evidence_contract(
    action: dict[str, Any] | None,
    *,
    diff_summary: dict[str, Any] | None = None,
    files_changed: list[Any] | None = None,
    validation_commands: list[Any] | None = None,
    errors: list[Any] | None = None,
    evidence_refs: list[Any] | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build post-action evidence contract without claiming execution."""

    normalized_action = normalize_code_action_contract(_as_dict(action))
    normalized_commands = [normalize_code_action_command_evidence(item) for item in _as_list(validation_commands)]
    normalized_errors = [_bounded_value(item) for item in _as_list(errors)]
    normalized_files_changed = [_as_text(item) for item in _as_list(files_changed) if _as_text(item)]
    normalized_diff = _bounded_value(diff_summary or {})

    has_diff = bool(normalized_diff)
    has_changed_files = bool(normalized_files_changed)
    has_validation = bool(normalized_commands)
    has_failed_command = any(command.get("status") == "failed" for command in normalized_commands)
    has_errors = bool(normalized_errors)

    resolved_status = _as_text(status)
    if resolved_status not in VALID_CODE_ACTION_EVIDENCE_STATUS:
        if has_errors or has_failed_command:
            resolved_status = "failed"
        elif has_diff and has_changed_files and has_validation:
            resolved_status = "passed"
        elif has_diff or has_changed_files or has_validation or evidence_refs:
            resolved_status = "partial"
        else:
            resolved_status = "missing"

    return _bounded_value(
        {
            "action_id": normalized_action.get("action_id"),
            "action_type": normalized_action.get("action_type"),
            "status": resolved_status,
            "ok": resolved_status == "passed",
            "diff_summary": normalized_diff,
            "files_changed": normalized_files_changed,
            "validation_commands": normalized_commands,
            "errors": normalized_errors,
            "evidence_refs": _bounded_value(_as_list(evidence_refs)),
            "has_diff": has_diff,
            "has_changed_files": has_changed_files,
            "has_validation": has_validation,
            "execution_claim_allowed": resolved_status == "passed",
            "metadata": _bounded_value(metadata or {}),
        }
    )


def evaluate_code_action_evidence(
    evidence: dict[str, Any] | None,
    *,
    require_diff: bool = True,
    require_changed_files: bool = True,
    require_validation: bool = True,
) -> dict[str, Any]:
    """Evaluate whether code action evidence is sufficient."""

    normalized = _as_dict(evidence or {})
    reasons: list[dict[str, Any]] = []

    def add_reason(code: str, message: str, severity: str = "medium") -> None:
        reasons.append({"code": code, "message": message, "severity": severity})

    if require_diff and not normalized.get("has_diff"):
        add_reason("diff_missing", "Code action evidence is missing a diff summary.", "high")

    if require_changed_files and not normalized.get("has_changed_files"):
        add_reason("changed_files_missing", "Code action evidence is missing changed files.", "high")

    if require_validation and not normalized.get("has_validation"):
        add_reason("validation_missing", "Code action evidence is missing validation command evidence.", "medium")

    for command in _as_list(normalized.get("validation_commands")):
        command_dict = _as_dict(command)
        if command_dict.get("status") == "failed":
            add_reason("validation_failed", "A validation command failed.", "high")

    if _as_list(normalized.get("errors")):
        add_reason("execution_errors_present", "Code action evidence contains errors.", "high")

    status = "passed" if not reasons else "failed"
    return _bounded_value(
        {
            "status": status,
            "ok": status == "passed",
            "reasons": reasons,
            "reason_count": len(reasons),
            "execution_claim_allowed": status == "passed",
        }
    )


def apply_code_action_evidence(
    action: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach evidence to a code action without executing anything."""

    normalized = normalize_code_action_contract(_as_dict(action))
    evidence_contract = build_code_action_evidence_contract(normalized, **_as_dict(evidence))
    evidence_gate = evaluate_code_action_evidence(evidence_contract)

    merged = dict(normalized)
    merged["evidence"] = evidence_contract
    merged["evidence_gate"] = evidence_gate
    merged["executed"] = evidence_gate["ok"]
    merged["status"] = "executed" if evidence_gate["ok"] else "failed"
    merged["execution_result"] = evidence_contract if evidence_gate["ok"] else None
    return _bounded_value(merged)


def build_code_action_pending_action(
    action: dict[str, Any] | None,
    *,
    pending_action_id: str | None = None,
    user_message: str | None = None,
    allowed_files: list[Any] | None = None,
    forbidden_files: list[Any] | None = None,
    granted_permissions: list[Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Build a reviewable pending action from a code action contract.

    This bridge does not execute tools, write files, run commands, approve the
    action, or claim evidence. It only prepares a structured pending action that
    another guarded runtime can review later.
    """

    guarded_action = apply_code_action_guard(
        action,
        allowed_files=allowed_files,
        forbidden_files=forbidden_files,
        granted_permissions=granted_permissions,
    )
    guard = _as_dict(guarded_action.get("guard"))
    pending_status = "blocked" if guard.get("guard_status") == "blocked" else "pending_approval"

    return _bounded_value(
        {
            "pending_action_id": _as_text(pending_action_id) or guarded_action.get("action_id"),
            "pending_action_type": "code_action",
            "status": pending_status,
            "source": _as_text(source) or "code_action_pending_bridge",
            "user_message": _as_text(user_message),
            "code_action": guarded_action,
            "guard": guard,
            "requires_approval": bool(guarded_action.get("requires_approval", True)),
            "expected_evidence": guarded_action.get("expected_evidence") or [],
            "allowed_files": _bounded_value(_as_list(allowed_files)),
            "forbidden_files": _bounded_value(_as_list(forbidden_files)),
            "granted_permissions": _bounded_value(_as_list(granted_permissions)),
            "execution_allowed": False,
            "execution_performed": False,
            "executed": False,
            "execution_result": None,
            "next_action": "review_code_action" if pending_status == "pending_approval" else "explain_blocked_code_action",
        }
    )


def prepare_code_action_pending_action(
    action: dict[str, Any] | None,
    *,
    user_message: str | None = None,
    allowed_files: list[Any] | None = None,
    forbidden_files: list[Any] | None = None,
    granted_permissions: list[Any] | None = None,
) -> dict[str, Any]:
    """Prepare a pending code action payload for state_context or UI review."""

    pending = build_code_action_pending_action(
        action,
        user_message=user_message,
        allowed_files=allowed_files,
        forbidden_files=forbidden_files,
        granted_permissions=granted_permissions,
    )

    return _bounded_value(
        {
            "ok": pending.get("status") == "pending_approval",
            "status": pending.get("status"),
            "pending_action": pending,
            "pending_action_type": "code_action",
            "safe_to_prepare": pending.get("status") == "pending_approval",
            "safe_to_execute": False,
            "reason": "Code action prepared for review." if pending.get("status") == "pending_approval" else "Code action blocked by guard.",
        }
    )


def summarize_code_action_contract(action: dict[str, Any] | None) -> str:
    """Return compact summary for logs/UI/prompts."""

    normalized = _as_dict(action or {})
    files = len(_as_list(normalized.get("affected_files")))
    commands = len(_as_list(normalized.get("suggested_commands")))
    return (
        "Code Action: "
        f"type={normalized.get('action_type') or MISSING}; "
        f"status={normalized.get('status') or MISSING}; "
        f"risk={normalized.get('risk_level') or MISSING}; "
        f"files={files}; commands={commands}; "
        f"executed={bool(normalized.get('executed'))}"
    )
