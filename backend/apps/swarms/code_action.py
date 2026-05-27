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
