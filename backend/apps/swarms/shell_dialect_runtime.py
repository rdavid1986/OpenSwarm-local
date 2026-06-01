"""Side-effect-free shell dialect runtime contracts for command preflight.

This module detects and describes shell profiles for future command execution
without running commands, spawning subprocesses, mutating files, or granting
execution permission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import os
import platform
import re
from typing import Any

SHELL_DIALECT_RUNTIME_VERSION = "openswarm.shell_dialect_runtime.v1"

SHELL_IDS = {
    "git_bash",
    "powershell_5",
    "powershell_7",
    "cmd",
    "wsl",
    "python_subprocess",
    "unknown",
}
SHELL_FAMILIES = {"posix", "powershell", "cmd", "python", "unknown"}
PATH_STYLES = {"posix", "windows", "mixed", "structured", "unknown"}
QUOTE_STYLES = {"posix_single_double", "powershell", "cmd", "structured_args", "unknown"}
DIALECT_RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}


@dataclass(frozen=True)
class ShellDialectCapability:
    capability_kind: str = "shell_dialect_capability"
    supports_and_operator: bool = False
    supports_semicolon: bool = False
    supports_posix_tools: bool = False
    supports_powershell_cmdlets: bool = False
    supports_cmd_builtins: bool = False
    supports_windows_paths: bool = False
    supports_posix_paths: bool = False
    supports_structured_args: bool = False
    path_style: str = "unknown"
    quoting_style: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ShellProfile:
    profile_kind: str = "shell_profile"
    shell_runtime_version: str = SHELL_DIALECT_RUNTIME_VERSION
    shell_id: str = "unknown"
    shell_name: str = "Unknown"
    shell_family: str = "unknown"
    shell_version: str = ""
    platform_system: str = ""
    platform_release: str = ""
    executable_hint: str = ""
    source: str = "unknown"
    confidence: str = "low"
    capability: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    can_execute: bool = False
    detection_executed_process: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

COMMAND_INTENTS = {
    "inspect",
    "modify",
    "validate",
    "test",
    "build",
    "install",
    "run",
    "commit",
    "unknown",
}


@dataclass(frozen=True)
class StructuredShellCommand:
    command_kind: str = "structured_shell_command"
    shell_runtime_version: str = SHELL_DIALECT_RUNTIME_VERSION
    intent: str = "unknown"
    shell_id: str = "unknown"
    shell_family: str = "unknown"
    command_name: str = ""
    argv: list[str] = field(default_factory=list)
    raw_command: str = ""
    working_directory: str = ""
    environment: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    can_execute: bool = False
    execution_permission_granted: bool = False
    translation_required: bool = True
    preflight_required: bool = True
    shell_profile: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ShellDialectTranslation:
    translation_kind: str = "shell_dialect_translation"
    shell_runtime_version: str = SHELL_DIALECT_RUNTIME_VERSION
    source_shell_id: str = "unknown"
    source_shell_family: str = "unknown"
    target_shell_id: str = "unknown"
    target_shell_family: str = "unknown"
    intent: str = "unknown"
    command_name: str = ""
    source_argv: list[str] = field(default_factory=list)
    translated_argv: list[str] = field(default_factory=list)
    raw_command: str = ""
    working_directory: str = ""
    environment: dict[str, Any] = field(default_factory=dict)
    translation_status: str = "blocked"
    translation_required: bool = True
    translation_executed_process: bool = False
    can_execute: bool = False
    execution_permission_granted: bool = False
    preflight_required: bool = True
    risk_level: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    source_command: dict[str, Any] = field(default_factory=dict)
    target_profile: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ShellDialectPreflightResult:
    preflight_kind: str = "shell_dialect_preflight"
    shell_runtime_version: str = SHELL_DIALECT_RUNTIME_VERSION
    preflight_status: str = "blocked"
    target_shell_id: str = "unknown"
    target_shell_family: str = "unknown"
    command_name: str = ""
    argv: list[str] = field(default_factory=list)
    raw_command: str = ""
    can_execute: bool = False
    execution_permission_granted: bool = False
    required_actions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    source: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ShellDialectErrorClassification:
    error_kind: str = "shell_dialect_error_classification"
    shell_runtime_version: str = SHELL_DIALECT_RUNTIME_VERSION
    classification: str = "unknown"
    target_shell_id: str = "unknown"
    target_shell_family: str = "unknown"
    sanitized_error: str = ""
    can_execute: bool = False
    required_actions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ShellDialectRetryDecision:
    retry_kind: str = "shell_dialect_retry_decision"
    shell_runtime_version: str = SHELL_DIALECT_RUNTIME_VERSION
    retry_status: str = "blocked"
    should_retry: bool = False
    next_required_actions: list[str] = field(default_factory=list)
    reason: str = ""
    risk_level: str = "unknown"
    can_execute: bool = False
    source: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ShellDialectAgentTerminalGate:
    gate_kind: str = "shell_dialect_agent_terminal_gate"
    shell_runtime_version: str = SHELL_DIALECT_RUNTIME_VERSION
    gate_status: str = "blocked"
    can_execute: bool = False
    required_actions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    shell_id: str = "unknown"
    target_shell_id: str = "unknown"
    preflight_status: str = "blocked"
    policy_approval_status: str = "missing"
    safeshell_connected: bool = False
    process_trace_ready: bool = False
    structured_command_ready: bool = False
    translation_ready: bool = False
    risk_level: str = "unknown"
    diagnostics: list[str] = field(default_factory=list)
    shell_profile: dict[str, Any] = field(default_factory=dict)
    structured_command: dict[str, Any] = field(default_factory=dict)
    translation: dict[str, Any] = field(default_factory=dict)
    preflight: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def _text(value: Any, fallback: str = "", limit: int = 600) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text[:limit].rstrip() + ("..." if len(text) > limit else "")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _dedupe(values: list[Any], *, limit: int = 80) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value, limit=240)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, raw in value.items():
        key_text = _text(key, limit=120)
        lowered = key_text.lower()
        if any(token in lowered for token in SENSITIVE_KEYS):
            safe[key_text] = "[redacted]"
        elif isinstance(raw, dict):
            safe[key_text] = _safe_metadata(raw)
        elif isinstance(raw, list):
            safe[key_text] = [_text(item, limit=160) if not isinstance(item, dict) else _safe_metadata(item) for item in raw[:20]]
        else:
            safe[key_text] = _text(raw, limit=240)
    return safe


def dump_shell_dialect(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return _safe_metadata(value)
    return {}


def normalize_shell_id(value: Any) -> str:
    text = _text(value, "unknown").lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "bash": "git_bash",
        "gitbash": "git_bash",
        "git_bash": "git_bash",
        "mingw": "git_bash",
        "msys": "git_bash",
        "windows_powershell": "powershell_5",
        "powershell": "powershell_5",
        "powershell_5_1": "powershell_5",
        "powershell_5": "powershell_5",
        "pwsh": "powershell_7",
        "powershell_7": "powershell_7",
        "powershell_core": "powershell_7",
        "cmd": "cmd",
        "cmd_exe": "cmd",
        "command_prompt": "cmd",
        "wsl": "wsl",
        "ubuntu_wsl": "wsl",
        "python": "python_subprocess",
        "python_subprocess": "python_subprocess",
    }
    return aliases.get(text, text if text in SHELL_IDS else "unknown")


def normalize_command_intent(value: Any) -> str:
    intent = _text(value, "unknown").lower().replace(" ", "_").replace("-", "_")
    return intent if intent in COMMAND_INTENTS else "unknown"


def _safe_command_value(value: Any, *, limit: int = 320) -> str:
    text = _text(value, limit=limit)
    lowered = text.lower()
    if any(token in lowered for token in SENSITIVE_KEYS):
        return "[redacted]"
    return text


def _normalize_command_argv(command_name: Any, args: list[Any] | tuple[Any, ...] | None = None) -> list[str]:
    argv: list[str] = []
    name = _safe_command_value(command_name)
    if name:
        argv.append(name)
    for item in _as_list(args):
        value = _safe_command_value(item)
        if value:
            argv.append(value)
    return argv[:120]


def build_structured_shell_command(
    *,
    intent: str = "unknown",
    command_name: str = "",
    args: list[Any] | tuple[Any, ...] | None = None,
    raw_command: str = "",
    working_directory: str = "",
    shell_profile: ShellProfile | dict[str, Any] | None = None,
    shell_id: str = "unknown",
    environment: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    risk_level: str = "unknown",
) -> StructuredShellCommand:
    profile = shell_profile if shell_profile is not None else build_shell_profile(shell_id=shell_id)
    profile_data = dump_shell_dialect(profile)
    resolved_shell_id = normalize_shell_id(profile_data.get("shell_id") or shell_id)
    shell_family = _text(profile_data.get("shell_family"), "unknown")
    argv = _normalize_command_argv(command_name, args)
    safe_raw = _safe_command_value(raw_command, limit=1200)

    required = [
        "do_not_execute_shell",
        "require_structured_command_review",
        "connect_dialect_preflight_guard_before_execution",
        "require_policy_matrix_approval",
    ]
    notes = ["Structured command contract is declarative and must not execute commands."]

    if not argv:
        required.append("provide_command_name")
        notes.append("Command name is missing.")
    if safe_raw:
        required.append("parse_raw_command_before_execution")
        notes.append("Raw command string must be parsed into argv before execution.")
    if resolved_shell_id == "unknown":
        required.append("select_shell_profile_before_execution")
        notes.append("Shell profile is unknown.")
    if shell_family != "python":
        required.append("translate_structured_command_for_shell")

    requested_risk = _text(risk_level, "unknown").lower()
    if requested_risk not in DIALECT_RISK_LEVELS:
        requested_risk = "unknown"
    resolved_risk = requested_risk
    if resolved_risk == "unknown":
        resolved_risk = "high" if not argv or safe_raw else "medium"

    return StructuredShellCommand(
        intent=normalize_command_intent(intent),
        shell_id=resolved_shell_id,
        shell_family=shell_family,
        command_name=argv[0] if argv else "",
        argv=argv,
        raw_command=safe_raw,
        working_directory=_safe_command_value(working_directory, limit=500),
        environment=_safe_metadata(environment),
        risk_level=resolved_risk,
        required_actions=_dedupe(required),
        risk_notes=_dedupe(notes),
        can_execute=False,
        execution_permission_granted=False,
        translation_required=shell_family != "python",
        preflight_required=True,
        shell_profile=profile_data,
        metadata=_safe_metadata(metadata),
    )



def _coerce_structured_shell_command(value: StructuredShellCommand | dict[str, Any]) -> dict[str, Any]:
    data = dump_shell_dialect(value)
    if not data:
        return dump_shell_dialect(build_structured_shell_command())
    if data.get("command_kind") != "structured_shell_command":
        return dump_shell_dialect(
            build_structured_shell_command(
                intent=data.get("intent", "unknown"),
                command_name=data.get("command_name", ""),
                args=_as_list(data.get("argv"))[1:] if _as_list(data.get("argv")) else [],
                raw_command=data.get("raw_command", ""),
                working_directory=data.get("working_directory", ""),
                shell_id=data.get("shell_id", "unknown"),
                environment=data.get("environment") if isinstance(data.get("environment"), dict) else {},
                metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
                risk_level=data.get("risk_level", "unknown"),
            )
        )
    return data


def _coerce_shell_profile(value: ShellProfile | dict[str, Any] | None, *, shell_id: str = "unknown") -> dict[str, Any]:
    if value is None:
        return dump_shell_dialect(build_shell_profile(shell_id=shell_id))
    data = dump_shell_dialect(value)
    if data.get("profile_kind") != "shell_profile":
        return dump_shell_dialect(build_shell_profile(shell_id=data.get("shell_id") or shell_id))
    return data


def _translation_status_for(required_actions: list[str]) -> str:
    blocking = {
        "provide_command_name",
        "parse_raw_command_before_translation",
        "select_target_shell_profile_before_translation",
        "select_shell_profile_before_execution",
    }
    if any(action in blocking for action in required_actions):
        return "blocked"
    return "translated"


def translate_structured_shell_command(
    command: StructuredShellCommand | dict[str, Any],
    *,
    target_profile: ShellProfile | dict[str, Any] | None = None,
    target_shell_id: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> ShellDialectTranslation:
    source = _coerce_structured_shell_command(command)
    target = _coerce_shell_profile(target_profile, shell_id=target_shell_id or source.get("shell_id", "unknown"))

    source_shell_id = normalize_shell_id(source.get("shell_id"))
    target_shell_id_resolved = normalize_shell_id(target.get("shell_id"))
    source_family = _text(source.get("shell_family"), "unknown")
    target_family = _text(target.get("shell_family"), "unknown")
    source_argv = [_safe_command_value(item) for item in _as_list(source.get("argv")) if _safe_command_value(item)]
    raw_command = _safe_command_value(source.get("raw_command"), limit=1200)

    required = [
        "do_not_execute_shell",
        "require_translation_review",
        "connect_dialect_preflight_guard_before_execution",
        "require_policy_matrix_approval",
    ]
    notes = ["Shell dialect translation is declarative and must not execute commands."]
    translated_argv = list(source_argv)

    if not source_argv:
        required.append("provide_command_name")
        notes.append("Source argv is empty.")
    if raw_command:
        required.append("parse_raw_command_before_translation")
        notes.append("Raw command strings cannot be translated as executable shell strings.")
    if target_shell_id_resolved == "unknown":
        required.append("select_target_shell_profile_before_translation")
        notes.append("Target shell profile is unknown.")
    if source_shell_id == "unknown":
        required.append("select_shell_profile_before_execution")
        notes.append("Source shell profile is unknown.")

    if source_family != target_family and target_family != "python":
        required.append("translate_between_shell_families")
        notes.append(f"Source family {source_family} differs from target family {target_family}.")

    if target_shell_id_resolved == "powershell_5":
        required.append("block_bash_and_operator")
        notes.append("PowerShell 5.1 requires syntax guard before accepting Bash-style operators.")

    if target_family == "powershell":
        translated_argv = [_safe_command_value(item) for item in source_argv]
        required.append("quote_for_powershell_before_execution")
    elif target_family == "cmd":
        translated_argv = [_safe_command_value(item) for item in source_argv]
        required.append("quote_for_cmd_before_execution")
    elif target_family == "posix":
        translated_argv = [_safe_command_value(item) for item in source_argv]
        required.append("quote_for_posix_before_execution")
    elif target_family == "python":
        translated_argv = [_safe_command_value(item) for item in source_argv]
        required.append("keep_as_structured_argv")
    else:
        required.append("select_supported_target_shell_family")

    translation_required = source_shell_id != target_shell_id_resolved or source.get("translation_required") is True
    risk = _text(source.get("risk_level"), "unknown").lower()
    if risk not in DIALECT_RISK_LEVELS:
        risk = "unknown"
    if risk == "unknown":
        risk = "high" if any(action in required for action in ("provide_command_name", "parse_raw_command_before_translation")) else "medium"

    required = _dedupe(required)
    return ShellDialectTranslation(
        source_shell_id=source_shell_id,
        source_shell_family=source_family,
        target_shell_id=target_shell_id_resolved,
        target_shell_family=target_family,
        intent=normalize_command_intent(source.get("intent")),
        command_name=_safe_command_value(source.get("command_name")),
        source_argv=source_argv,
        translated_argv=translated_argv,
        raw_command=raw_command,
        working_directory=_safe_command_value(source.get("working_directory"), limit=500),
        environment=_safe_metadata(source.get("environment") if isinstance(source.get("environment"), dict) else {}),
        translation_status=_translation_status_for(required),
        translation_required=translation_required,
        translation_executed_process=False,
        can_execute=False,
        execution_permission_granted=False,
        preflight_required=True,
        risk_level=risk,
        required_actions=required,
        risk_notes=_dedupe(notes + _as_list(source.get("risk_notes")) + _as_list(target.get("risk_notes"))),
        source_command=source,
        target_profile=target,
        metadata=_safe_metadata(metadata),
    )


def _source_for_preflight(value: StructuredShellCommand | ShellDialectTranslation | dict[str, Any]) -> dict[str, Any]:
    data = dump_shell_dialect(value)
    if data.get("translation_kind") == "shell_dialect_translation":
        return data
    if data.get("command_kind") == "structured_shell_command":
        return data
    if data.get("preflight_kind") == "shell_dialect_preflight":
        return data
    return _coerce_structured_shell_command(data)


def _preflight_shell_parts(data: dict[str, Any]) -> tuple[str, str, list[str], str, str]:
    if data.get("translation_kind") == "shell_dialect_translation":
        shell_id = normalize_shell_id(data.get("target_shell_id"))
        shell_family = _text(data.get("target_shell_family"), "unknown")
        argv = [_safe_command_value(item) for item in _as_list(data.get("translated_argv")) if _safe_command_value(item)]
    else:
        shell_id = normalize_shell_id(data.get("target_shell_id") or data.get("shell_id"))
        shell_family = _text(data.get("target_shell_family") or data.get("shell_family"), "unknown")
        argv = [_safe_command_value(item) for item in _as_list(data.get("argv")) if _safe_command_value(item)]
    command_name = _safe_command_value(data.get("command_name") or (argv[0] if argv else ""))
    raw_command = _safe_command_value(data.get("raw_command"), limit=1200)
    return shell_id, shell_family, argv, command_name, raw_command


def _contains_shell_operator(argv: list[str], operators: tuple[str, ...]) -> bool:
    return any(any(operator in arg for operator in operators) for arg in argv)


def preflight_shell_dialect_command(
    command: StructuredShellCommand | ShellDialectTranslation | dict[str, Any],
    *,
    policy_matrix_approved: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ShellDialectPreflightResult:
    source = _source_for_preflight(command)
    target_shell_id, target_shell_family, argv, command_name, raw_command = _preflight_shell_parts(source)
    policy_approved = bool(
        policy_matrix_approved
        or source.get("policy_matrix_approved")
        or source.get("execution_permission_granted")
        or (isinstance(source.get("metadata"), dict) and source["metadata"].get("policy_matrix_approved") is True)
    )

    required: list[str] = ["do_not_execute_shell", "require_policy_matrix_approval"]
    notes: list[str] = ["Shell dialect preflight is declarative and must not execute commands."]
    diagnostics: list[str] = []

    if target_shell_id == "unknown" or target_shell_family == "unknown":
        required.append("select_supported_shell_profile_before_execution")
        diagnostics.append("unknown_shell")
        notes.append("Target shell is unknown.")
    if not argv:
        required.append("provide_structured_argv_before_execution")
        diagnostics.append("empty_argv")
        notes.append("Structured argv is empty.")
    if raw_command:
        required.append("parse_raw_command_before_execution")
        diagnostics.append("raw_command_present")
        notes.append("Raw command strings are blocked until parsed into argv.")

    if target_shell_id == "powershell_5" and _contains_shell_operator(argv, ("&&",)):
        required.append("block_bash_and_operator_for_powershell_5")
        diagnostics.append("powershell_5_invalid_and_operator")
        notes.append("PowerShell 5.1 does not support Bash-style &&.")
    if target_shell_id == "cmd" and _contains_shell_operator(argv, (";",)):
        required.append("review_cmd_semicolon_shell_syntax")
        diagnostics.append("cmd_semicolon_requires_review")
        notes.append("Semicolon in cmd argv may indicate unsafe raw shell syntax.")
    if _contains_shell_operator(argv, ("|", ">", "<", "2>", "1>")):
        required.append("parse_shell_pipes_or_redirections_before_execution")
        diagnostics.append("raw_shell_pipe_or_redirection")
        notes.append("Pipes and redirections must not be passed as raw shell syntax.")
    if not policy_approved:
        required.append("obtain_policy_matrix_approval_before_execution")
        diagnostics.append("policy_matrix_approval_missing")
        notes.append("PolicyMatrix approval is required before any execution boundary.")

    inherited_actions = _as_list(source.get("required_actions"))
    inherited_notes = _as_list(source.get("risk_notes"))
    inherited_risk = _text(source.get("risk_level"), "unknown").lower()
    if inherited_risk not in DIALECT_RISK_LEVELS:
        inherited_risk = "unknown"

    blocking_diagnostics = {
        "unknown_shell",
        "empty_argv",
        "raw_command_present",
        "powershell_5_invalid_and_operator",
        "raw_shell_pipe_or_redirection",
        "policy_matrix_approval_missing",
    }
    if any(item in blocking_diagnostics for item in diagnostics):
        status = "blocked"
    elif diagnostics:
        status = "warning"
    else:
        status = "passed"

    risk = "high" if status == "blocked" else "medium" if status == "warning" else inherited_risk
    if risk == "unknown":
        risk = "low"

    return ShellDialectPreflightResult(
        preflight_status=status,
        target_shell_id=target_shell_id,
        target_shell_family=target_shell_family,
        command_name=command_name,
        argv=argv,
        raw_command=raw_command,
        can_execute=False,
        execution_permission_granted=False,
        required_actions=_dedupe(required + inherited_actions),
        risk_notes=_dedupe(notes + inherited_notes),
        diagnostics=_dedupe(diagnostics),
        risk_level=risk,
        source=source,
        metadata=_safe_metadata(metadata),
    )


def classify_shell_dialect_error(
    error: str | dict[str, Any] | Exception,
    *,
    shell_id: str = "unknown",
    shell_family: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> ShellDialectErrorClassification:
    if isinstance(error, dict):
        raw_error_text = _text(error.get("error") or error.get("stderr") or error.get("message"), limit=1600)
        error_text = _safe_command_value(raw_error_text, limit=1600)
        shell_id = error.get("shell_id", shell_id)
        shell_family = error.get("shell_family", shell_family)
    else:
        raw_error_text = _text(error, limit=1600)
        error_text = _safe_command_value(raw_error_text, limit=1600)
    target_shell_id = normalize_shell_id(shell_id)
    target_shell_family = _text(shell_family, "unknown")
    lowered = raw_error_text.lower()

    classification = "unknown"
    diagnostics: list[str] = []
    required = ["do_not_execute_shell", "review_shell_dialect_error"]
    notes = ["Shell dialect error classification is side-effect-free."]

    if "&&" in raw_error_text and ("not a valid statement separator" in lowered or "invalid end of line" in lowered):
        classification = "powershell_invalid_and_operator"
        required.append("translate_bash_and_operator_for_powershell")
    elif "not recognized" in lowered or "command not found" in lowered or "is not recognized as" in lowered:
        classification = "command_not_found"
        required.append("verify_command_availability")
    elif "no such file or directory" in lowered or "path not found" in lowered or "cannot find path" in lowered:
        classification = "path_not_found"
        required.append("verify_path_for_target_shell")
    elif "permission denied" in lowered or "access is denied" in lowered:
        classification = "permission_denied"
        required.append("review_permissions_before_retry")
    elif "executionpolicy" in lowered or "running scripts is disabled" in lowered:
        classification = "execution_policy_blocked"
        required.append("review_execution_policy")
    elif "parse" in lowered or "quot" in lowered or "unexpected token" in lowered or "unterminated" in lowered:
        classification = "quoting_or_parsing_error"
        required.append("review_shell_quoting")
    elif "timeout" in lowered or "timed out" in lowered:
        classification = "timeout"
        required.append("review_timeout_before_retry")

    diagnostics.append(classification)
    risk = "high" if classification in {"permission_denied", "execution_policy_blocked", "timeout", "unknown"} else "medium"
    return ShellDialectErrorClassification(
        classification=classification,
        target_shell_id=target_shell_id,
        target_shell_family=target_shell_family,
        sanitized_error=error_text,
        can_execute=False,
        required_actions=_dedupe(required),
        risk_notes=_dedupe(notes),
        diagnostics=_dedupe(diagnostics),
        risk_level=risk,
        metadata=_safe_metadata(metadata),
    )


def decide_shell_dialect_retry(
    source: ShellDialectPreflightResult | ShellDialectErrorClassification | dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> ShellDialectRetryDecision:
    data = dump_shell_dialect(source)
    classification = _text(data.get("classification"), "unknown")
    preflight_status = _text(data.get("preflight_status"), "")
    required = ["do_not_execute_shell", "do_not_retry_automatically", "require_human_review_before_retry"]
    reason = "Retry requires human review because shell dialect contracts never execute automatically."
    retry_status = "needs_human_review"
    risk = _text(data.get("risk_level"), "unknown").lower()

    if preflight_status == "blocked":
        retry_status = "blocked"
        reason = "Preflight is blocked; retry is not allowed without resolving required actions."
        required.append("resolve_preflight_blockers")
    elif classification in {"permission_denied", "execution_policy_blocked", "timeout", "unknown"}:
        retry_status = "blocked"
        reason = f"Retry blocked for {classification}."
        required.append("escalate_shell_error_before_retry")
    elif classification in {"command_not_found", "path_not_found", "quoting_or_parsing_error", "powershell_invalid_and_operator"}:
        retry_status = "needs_human_review"
        reason = f"Retry may be planned only after human review for {classification}."
        required.append("prepare_corrected_structured_command")
    elif preflight_status == "passed":
        retry_status = "allowed"
        reason = "Retry planning is allowed, but execution remains disabled until an external executor obtains approval."
        required.append("obtain_policy_matrix_approval_before_execution")

    if risk not in DIALECT_RISK_LEVELS:
        risk = "medium" if retry_status == "needs_human_review" else "high" if retry_status == "blocked" else "low"

    return ShellDialectRetryDecision(
        retry_status=retry_status,
        should_retry=False,
        next_required_actions=_dedupe(required + _as_list(data.get("required_actions"))),
        reason=reason,
        risk_level=risk,
        can_execute=False,
        source=data,
        metadata=_safe_metadata(metadata),
    )


def build_agent_terminal_shell_gate(
    *,
    shell_profile: ShellProfile | dict[str, Any] | None = None,
    structured_command: StructuredShellCommand | dict[str, Any] | None = None,
    translation: ShellDialectTranslation | dict[str, Any] | None = None,
    preflight: ShellDialectPreflightResult | dict[str, Any] | None = None,
    policy_approval_status: str = "missing",
    safeshell_connected: bool = False,
    process_trace_ready: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ShellDialectAgentTerminalGate:
    profile_data = dump_shell_dialect(shell_profile) if shell_profile is not None else {}
    command_data = dump_shell_dialect(structured_command) if structured_command is not None else {}
    translation_data = dump_shell_dialect(translation) if translation is not None else {}
    preflight_data = dump_shell_dialect(preflight) if preflight is not None else {}

    shell_id = normalize_shell_id(profile_data.get("shell_id") or command_data.get("shell_id") or translation_data.get("source_shell_id"))
    target_shell_id = normalize_shell_id(
        preflight_data.get("target_shell_id")
        or translation_data.get("target_shell_id")
        or command_data.get("target_shell_id")
        or command_data.get("shell_id")
    )
    preflight_status = _text(preflight_data.get("preflight_status"), "missing").lower()
    policy_status = _text(policy_approval_status, "missing").lower().replace(" ", "_")
    structured_ready = command_data.get("command_kind") == "structured_shell_command" and bool(_as_list(command_data.get("argv")))
    translation_ready = translation_data.get("translation_kind") == "shell_dialect_translation" and translation_data.get("translation_status") == "translated"
    preflight_ready = preflight_status in {"passed", "warning"}
    policy_ready = policy_status in {"approved", "granted", "allowed"}

    required = ["do_not_execute_shell", "keep_agent_terminal_disabled", "do_not_unblock_opencode_commands_parity_14"]
    notes = ["Agent Terminal integration gate is declarative and does not execute commands."]
    diagnostics: list[str] = []

    if shell_id == "unknown":
        required.append("provide_valid_shell_profile")
        diagnostics.append("missing_shell_profile")
    if not structured_ready:
        required.append("provide_structured_shell_command")
        diagnostics.append("missing_structured_command")
    if not translation_ready:
        required.append("provide_shell_dialect_translation")
        diagnostics.append("missing_shell_dialect_translation")
    if not preflight_ready:
        required.append("pass_shell_dialect_preflight")
        diagnostics.append("preflight_not_ready")
    if not policy_ready:
        required.append("obtain_policy_matrix_approval")
        diagnostics.append("policy_matrix_approval_missing")
    if not safeshell_connected:
        required.append("connect_safeshell_runtime")
        diagnostics.append("safeshell_not_connected")
    if not process_trace_ready:
        required.append("attach_process_trace_evidence")
        diagnostics.append("process_trace_not_ready")

    gate_ready = (
        shell_id != "unknown"
        and structured_ready
        and translation_ready
        and preflight_ready
        and policy_ready
        and safeshell_connected
        and process_trace_ready
    )
    gate_status = "ready" if gate_ready else "needs_review" if preflight_ready and policy_ready else "blocked"
    risk = "low" if gate_ready else "medium" if gate_status == "needs_review" else "high"

    return ShellDialectAgentTerminalGate(
        gate_status=gate_status,
        can_execute=False,
        required_actions=_dedupe(required),
        risk_notes=_dedupe(notes + _as_list(preflight_data.get("risk_notes")) + _as_list(translation_data.get("risk_notes"))),
        shell_id=shell_id,
        target_shell_id=target_shell_id,
        preflight_status=preflight_status,
        policy_approval_status=policy_status,
        safeshell_connected=bool(safeshell_connected),
        process_trace_ready=bool(process_trace_ready),
        structured_command_ready=bool(structured_ready),
        translation_ready=bool(translation_ready),
        risk_level=risk,
        diagnostics=_dedupe(diagnostics),
        shell_profile=profile_data,
        structured_command=command_data,
        translation=translation_data,
        preflight=preflight_data,
        metadata=_safe_metadata(metadata),
    )


def _version_major(version: str) -> int | None:
    match = re.search(r"(\d+)", version or "")
    return int(match.group(1)) if match else None


def infer_shell_id(*, executable_hint: str = "", shell_name: str = "", shell_version: str = "", env: dict[str, Any] | None = None) -> str:
    env_data = env if isinstance(env, dict) else {}
    hint = " ".join(
        _text(part).lower()
        for part in [
            executable_hint,
            shell_name,
            env_data.get("SHELL"),
            env_data.get("ComSpec"),
            env_data.get("COMSPEC"),
            env_data.get("MSYSTEM"),
            env_data.get("WT_SESSION"),
            env_data.get("TERM_PROGRAM"),
        ]
        if _text(part)
    )

    if "python_subprocess" in hint:
        return "python_subprocess"
    if "pwsh" in hint:
        return "powershell_7"
    if "powershell" in hint:
        major = _version_major(shell_version)
        return "powershell_7" if major and major >= 7 else "powershell_5"
    if "cmd.exe" in hint or "\\cmd" in hint or "/cmd" in hint:
        return "cmd"
    if "wsl" in hint or bool(_text(env_data.get("WSL_DISTRO_NAME"))) or "microsoft" in _text(env_data.get("WSL_INTEROP")).lower():
        return "wsl"
    if "mingw" in hint or "msys" in hint or "git" in hint and "bash" in hint or hint.endswith("bash"):
        return "git_bash"
    return "unknown"


def build_shell_dialect_capability(shell_id: str) -> ShellDialectCapability:
    sid = normalize_shell_id(shell_id)
    actions: list[str] = ["do_not_execute_shell"]
    notes: list[str] = []

    if sid == "git_bash":
        return ShellDialectCapability(
            supports_and_operator=True,
            supports_semicolon=True,
            supports_posix_tools=True,
            supports_powershell_cmdlets=False,
            supports_cmd_builtins=False,
            supports_windows_paths=True,
            supports_posix_paths=True,
            supports_structured_args=False,
            path_style="mixed",
            quoting_style="posix_single_double",
            required_actions=actions,
            risk_notes=["PowerShell cmdlets require translation before Git Bash execution."],
        )
    if sid == "powershell_5":
        return ShellDialectCapability(
            supports_and_operator=False,
            supports_semicolon=True,
            supports_posix_tools=False,
            supports_powershell_cmdlets=True,
            supports_cmd_builtins=False,
            supports_windows_paths=True,
            supports_posix_paths=False,
            supports_structured_args=False,
            path_style="windows",
            quoting_style="powershell",
            required_actions=actions + ["block_bash_and_operator", "translate_posix_tools_or_check_availability"],
            risk_notes=["PowerShell 5.1 does not support Bash-style && command chaining."],
        )
    if sid == "powershell_7":
        return ShellDialectCapability(
            supports_and_operator=True,
            supports_semicolon=True,
            supports_posix_tools=False,
            supports_powershell_cmdlets=True,
            supports_cmd_builtins=False,
            supports_windows_paths=True,
            supports_posix_paths=False,
            supports_structured_args=False,
            path_style="windows",
            quoting_style="powershell",
            required_actions=actions + ["translate_posix_tools_or_check_availability"],
            risk_notes=["POSIX tools require availability checks before PowerShell execution."],
        )
    if sid == "cmd":
        return ShellDialectCapability(
            supports_and_operator=True,
            supports_semicolon=False,
            supports_posix_tools=False,
            supports_powershell_cmdlets=False,
            supports_cmd_builtins=True,
            supports_windows_paths=True,
            supports_posix_paths=False,
            supports_structured_args=False,
            path_style="windows",
            quoting_style="cmd",
            required_actions=actions + ["translate_powershell_cmdlets", "translate_posix_tools_or_check_availability"],
            risk_notes=["CMD has different quoting and environment expansion semantics."],
        )
    if sid == "wsl":
        return ShellDialectCapability(
            supports_and_operator=True,
            supports_semicolon=True,
            supports_posix_tools=True,
            supports_powershell_cmdlets=False,
            supports_cmd_builtins=False,
            supports_windows_paths=False,
            supports_posix_paths=True,
            supports_structured_args=False,
            path_style="posix",
            quoting_style="posix_single_double",
            required_actions=actions + ["translate_windows_paths_for_wsl"],
            risk_notes=["Windows paths require WSL path translation before execution."],
        )
    if sid == "python_subprocess":
        return ShellDialectCapability(
            supports_and_operator=False,
            supports_semicolon=False,
            supports_posix_tools=False,
            supports_powershell_cmdlets=False,
            supports_cmd_builtins=False,
            supports_windows_paths=True,
            supports_posix_paths=True,
            supports_structured_args=True,
            path_style="structured",
            quoting_style="structured_args",
            required_actions=actions + ["represent_command_as_argv"],
            risk_notes=["Structured subprocess mode must not pass free shell strings."],
        )
    return ShellDialectCapability(
        required_actions=actions + ["select_shell_profile_before_execution"],
        risk_notes=["Shell dialect is unknown; command execution must stay blocked."],
    )


def build_shell_profile(
    *,
    shell_id: str = "unknown",
    shell_name: str = "",
    shell_version: str = "",
    executable_hint: str = "",
    platform_system: str = "",
    platform_release: str = "",
    source: str = "manual",
    env: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ShellProfile:
    inferred_id = normalize_shell_id(shell_id)
    if inferred_id == "unknown":
        inferred_id = infer_shell_id(
            executable_hint=executable_hint,
            shell_name=shell_name,
            shell_version=shell_version,
            env=env,
        )
    capability = build_shell_dialect_capability(inferred_id)
    required = _dedupe(capability.required_actions + ["connect_dialect_preflight_guard_before_execution"])
    risk = "medium" if inferred_id in {"git_bash", "powershell_5", "powershell_7", "cmd", "wsl", "python_subprocess"} else "high"
    confidence = "high" if normalize_shell_id(shell_id) != "unknown" else "medium" if inferred_id != "unknown" else "low"
    default_names = {
        "git_bash": "Git Bash",
        "powershell_5": "Windows PowerShell 5.1",
        "powershell_7": "PowerShell 7+",
        "cmd": "Windows Command Prompt",
        "wsl": "Windows Subsystem for Linux",
        "python_subprocess": "Python subprocess structured mode",
        "unknown": "Unknown",
    }
    return ShellProfile(
        shell_id=inferred_id,
        shell_name=_text(shell_name, default_names.get(inferred_id, "Unknown")),
        shell_family={
            "git_bash": "posix",
            "wsl": "posix",
            "powershell_5": "powershell",
            "powershell_7": "powershell",
            "cmd": "cmd",
            "python_subprocess": "python",
        }.get(inferred_id, "unknown"),
        shell_version=_text(shell_version),
        platform_system=_text(platform_system or platform.system(), "unknown"),
        platform_release=_text(platform_release or platform.release(), "unknown"),
        executable_hint=_text(executable_hint, limit=300),
        source=_text(source, "manual"),
        confidence=confidence,
        capability=dump_shell_dialect(capability),
        risk_level=risk,
        required_actions=required,
        risk_notes=_dedupe(capability.risk_notes),
        can_execute=False,
        detection_executed_process=False,
        metadata=_safe_metadata(metadata),
    )


def detect_shell_profile_from_environment(env: dict[str, Any] | None = None) -> ShellProfile:
    env_data = dict(env or os.environ)
    executable_hint = _text(env_data.get("SHELL") or env_data.get("ComSpec") or env_data.get("COMSPEC"))
    shell_name = _text(env_data.get("MSYSTEM") or env_data.get("TERM_PROGRAM") or env_data.get("PSModulePath"))
    return build_shell_profile(
        executable_hint=executable_hint,
        shell_name=shell_name,
        source="environment",
        env=env_data,
        metadata={
            "detected_env_keys": sorted(k for k in env_data if k in {"SHELL", "ComSpec", "COMSPEC", "MSYSTEM", "TERM_PROGRAM", "WSL_DISTRO_NAME", "PSModulePath"}),
        },
    )


def build_shell_profile_trace_source(profile: ShellProfile | dict[str, Any]) -> dict[str, Any]:
    data = dump_shell_dialect(profile)
    return {
        "source_kind": "shell_dialect_runtime",
        "trace_source_kind": "shell_dialect_runtime",
        "profile_kind": data.get("profile_kind", "shell_profile"),
        "shell_id": data.get("shell_id", "unknown"),
        "shell_name": data.get("shell_name", "Unknown"),
        "shell_family": data.get("shell_family", "unknown"),
        "risk_level": data.get("risk_level", "unknown"),
        "required_actions": _dedupe(_as_list(data.get("required_actions"))),
        "capability": data.get("capability") if isinstance(data.get("capability"), dict) else {},
        "can_execute": False,
        "detection_executed_process": False,
        "metadata": _safe_metadata(data.get("metadata") if isinstance(data.get("metadata"), dict) else {}),
    }
