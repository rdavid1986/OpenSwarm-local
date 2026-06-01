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
