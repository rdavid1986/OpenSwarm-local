"""Side-effect-free OpenCode command parity contracts.

This module describes OpenCode-like slash/custom commands for OpenSwarm without
executing commands, reading referenced files, activating MCP, calling models, or
mutating user files. It prepares safe audit, discovery, interpolation guard,
argument expansion, file-reference and routing contracts only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
import re
from typing import Any

MAX_TEXT = 1200
MAX_BODY = 4000
MAX_REFS = 80
SOURCE_KINDS = {"built_in", "custom_markdown", "json_config", "runtime_request", "unknown"}
RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}
COMPATIBILITY = {"supported_contract", "needs_review", "blocked", "unsupported", "unknown"}
TARGET_KINDS = {"swarm", "agent", "miniagent", "model", "tool", "terminal", "preview", "qa", "unknown"}
GUARD_DECISIONS = {"allow_text_only", "requires_preview", "requires_approval", "blocked"}
SENSITIVE_KEY_TOKENS = (
    "secret", "token", "password", "credential", "authorization", "cookie", "api_key",
    "private_key", "raw_prompt", "raw_response", "chain_of_thought", "hidden_reasoning",
)
DANGEROUS_PERMISSION_TOKENS = (
    "dangerously_skip_permissions", "dangerously-skip-permissions", "skip_permissions",
    "disable_sandbox", "no_sandbox", "allow_all", "full_access", "sudo", "root",
)
SHELL_PATTERNS = (
    ("command_substitution", re.compile(r"\$\([^)]*\)")),
    ("backticks", re.compile(r"`[^`]+`")),
    ("redirection", re.compile(r"(^|\s)(?:>|>>|<|2>|2>>|&>)")),
    ("sensitive_env", re.compile(r"\$(?:[A-Z_]*(?:TOKEN|SECRET|PASSWORD|KEY|CREDENTIAL|AUTH)[A-Z_]*)")),
)
FILE_REF_RE = re.compile(r"(?<![\w/.-])[@#]([A-Za-z]:[A-Za-z0-9_.\\/: -]+\.[A-Za-z0-9_]{1,12}|[A-Za-z0-9_.\\/: -]+\.[A-Za-z0-9_]{1,12})")
MD_LINK_RE = re.compile(r"\[[^\]]{1,120}\]\(([^)]+\.[A-Za-z0-9_]{1,12})\)")
PLACEHOLDER_RE = re.compile(r"\$(ARGUMENTS|\d+|[A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class OpenCodeCommandAudit:
    audit_kind: str = "opencode_command_audit"
    source_kind: str = "unknown"
    command_name: str = ""
    command_origin: str = ""
    command_family: str = "unknown"
    compatibility_status: str = "unknown"
    risk_level: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    unsupported_reason: str = ""
    safe_equivalent: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)


@dataclass
class SlashCommandDefinition:
    definition_kind: str = "slash_command_definition"
    name: str = ""
    family: str = "unknown"
    origin: str = "built_in_registry"
    description: str = ""
    compatibility_status: str = "supported_contract"
    risk_level: str = "low"
    recommended_route: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)
    can_execute: bool = False


@dataclass
class BuiltInSlashCommandRegistry:
    registry_kind: str = "opencode_builtin_slash_command_registry"
    commands: list[dict[str, Any]] = field(default_factory=list)
    future_families: list[str] = field(default_factory=list)
    can_execute: bool = False


@dataclass
class CustomCommandFileCandidate:
    candidate_kind: str = "custom_command_file_candidate"
    source_kind: str = "custom_markdown"
    command_name: str = ""
    command_origin: str = ""
    title: str = ""
    description: str = ""
    body_preview: str = ""
    placeholders: list[str] = field(default_factory=list)
    file_references: list[str] = field(default_factory=list)
    shell_interpolation_detected: bool = False
    risk_level: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    can_execute: bool = False


@dataclass
class JsonConfigCommandCandidate:
    candidate_kind: str = "json_config_command_candidate"
    source_kind: str = "json_config"
    command_name: str = ""
    description: str = ""
    prompt_template_preview: str = ""
    requested_agent: str = ""
    requested_model: str = ""
    requested_tools: list[str] = field(default_factory=list)
    requested_permissions: list[str] = field(default_factory=list)
    blocked_keys: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    can_execute: bool = False


@dataclass
class CommandArgumentExpansion:
    expansion_kind: str = "command_argument_expansion"
    template_preview: str = ""
    expanded_preview: str = ""
    placeholders: list[str] = field(default_factory=list)
    missing_args: list[str] = field(default_factory=list)
    unused_args: list[str] = field(default_factory=list)
    named_args_used: list[str] = field(default_factory=list)
    shell_executed: bool = False
    can_execute: bool = False


@dataclass
class ShellInterpolationGuardDecision:
    guard_kind: str = "shell_interpolation_guard_decision"
    decision: str = "allow_text_only"
    detected_patterns: list[str] = field(default_factory=list)
    risk_level: str = "low"
    required_actions: list[str] = field(default_factory=list)
    shell_interpolation_executed: bool = False
    can_execute: bool = False


@dataclass
class FileReferenceExpansion:
    expansion_kind: str = "file_reference_expansion"
    workspace_root: str = ""
    requested_refs: list[str] = field(default_factory=list)
    normalized_refs: list[str] = field(default_factory=list)
    missing_refs: list[str] = field(default_factory=list)
    out_of_workspace_refs: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    files_read: bool = False
    can_execute: bool = False


@dataclass
class CommandRoutingDecision:
    routing_kind: str = "command_routing_decision"
    target_kind: str = "unknown"
    target_id: str = ""
    requested_model: str = ""
    requested_agent: str = ""
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)
    can_execute: bool = False
    requires_user_approval: bool = False


@dataclass
class OpenCodeCommandTraceSource:
    source_kind: str = "opencode_command"
    trace_source_kind: str = "opencode_command"
    command_name: str = ""
    origin: str = ""
    command_family: str = "unknown"
    compatibility_status: str = "unknown"
    risk_level: str = "unknown"
    safe_equivalent: dict[str, Any] = field(default_factory=dict)
    terminal_boundary: dict[str, Any] = field(default_factory=dict)
    preview_report: dict[str, Any] = field(default_factory=dict)
    routing: dict[str, Any] = field(default_factory=dict)
    required_actions: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    dry_run_only: bool = True
    can_execute: bool = False
    shell_interpolation_executed: bool = False
    files_read: bool = False
    tools_called: bool = False
    mcp_activated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandFamilyParityDefinition:
    family_kind: str = "opencode_command_family_parity"
    family_id: str = "unknown"
    display_name: str = "Unknown"
    opencode_pattern: str = ""
    openswarm_equivalent: str = ""
    support_status: str = "planned"
    risk_level: str = "unknown"
    requires_preview: bool = True
    requires_approval: bool = True
    can_execute_now: bool = False
    unsupported_reason: str = ""
    required_actions: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)


@dataclass
class CommandFamilyParityRegistry:
    registry_kind: str = "opencode_command_family_parity_registry"
    families: list[dict[str, Any]] = field(default_factory=list)
    can_execute_now: bool = False


@dataclass
class SafeCommandEquivalent:
    equivalent_kind: str = "opencode_safe_command_equivalent"
    command_name: str = ""
    command_family: str = "unknown"
    safe_equivalent_id: str = ""
    action_kind: str = "preview_only"
    preview_required: bool = True
    approval_required: bool = True
    execution_supported: bool = False
    blocked_reason: str = ""
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)


@dataclass
class TerminalBoundaryDecision:
    boundary_kind: str = "terminal_boundary_decision"
    terminal_kind: str = "unknown"
    request_id: str = ""
    command_preview: str = ""
    user_executes_manually: bool = False
    agent_controlled: bool = False
    requires_safeshell: bool = False
    requires_policy_matrix: bool = False
    requires_approval: bool = True
    requires_sandbox: bool = True
    requires_timeout: bool = True
    requires_redaction: bool = True
    requires_evidence: bool = True
    can_execute: bool = False
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)


@dataclass
class UserTerminalRequest:
    request_kind: str = "user_terminal_request"
    request_id: str = ""
    command_preview: str = ""
    context_help: str = ""
    user_executes_manually: bool = True
    can_execute: bool = False
    required_actions: list[str] = field(default_factory=list)


@dataclass
class AgentTerminalRequest:
    request_kind: str = "agent_terminal_request"
    request_id: str = ""
    command_preview: str = ""
    requires_safeshell: bool = True
    requires_policy_matrix: bool = True
    requires_approval: bool = True
    requires_sandbox: bool = True
    requires_timeout: bool = True
    requires_redaction: bool = True
    requires_evidence: bool = True
    can_execute: bool = False
    required_actions: list[str] = field(default_factory=list)


@dataclass
class TerminalRiskDecision:
    decision_kind: str = "terminal_risk_decision"
    terminal_kind: str = "unknown"
    risk_level: str = "high"
    decision: str = "requires_approval"
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False


@dataclass
class CommandPreviewReport:
    report_kind: str = "opencode_command_preview_report"
    command_name: str = ""
    command_family: str = "unknown"
    parsed_args: dict[str, Any] = field(default_factory=dict)
    file_refs: dict[str, Any] = field(default_factory=dict)
    shell_interpolation_decision: dict[str, Any] = field(default_factory=dict)
    safe_equivalent: dict[str, Any] = field(default_factory=dict)
    terminal_boundary: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "unknown"
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    dry_run_only: bool = True
    tools_called: bool = False
    files_read: bool = False
    shell_executed: bool = False
    mcp_activated: bool = False


def _text(value: Any, fallback: str = "", limit: int = MAX_TEXT) -> str:
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


def _dedupe(values: list[Any], *, limit: int = MAX_REFS) -> list[str]:
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


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").lower().replace("-", "_")
    return any(token in normalized for token in SENSITIVE_KEY_TOKENS)


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:120]:
            if _is_sensitive_key(key):
                continue
            out[str(key)] = _safe(item)
        if len(value) > 120:
            out["__truncated__"] = True
        return out
    if isinstance(value, list):
        return [_safe(item) for item in value[:120]]
    if isinstance(value, tuple | set):
        return [_safe(item) for item in list(value)[:120]]
    if isinstance(value, str):
        return _text(value, limit=MAX_BODY)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _text(value)


def _normalize_command_name(value: Any) -> str:
    name = _text(value).replace("\\", "/").split("/")[-1]
    if name.endswith(".md"):
        name = name[:-3]
    if name and not name.startswith("/"):
        name = f"/{name}"
    cleaned = re.sub(r"[^A-Za-z0-9_./:-]", "_", name)[:120]
    return cleaned or "/unknown"


def _normalize_risk(value: Any) -> str:
    text = _text(value, "unknown").lower()
    return text if text in RISK_LEVELS else "unknown"


def _risk_from_guard(guard: ShellInterpolationGuardDecision) -> str:
    if guard.decision == "blocked":
        return "critical"
    if guard.decision == "requires_approval":
        return "high"
    if guard.decision == "requires_preview":
        return "medium"
    return "low"


def _compat_for_risk(risk: str) -> str:
    return "blocked" if risk == "critical" else "needs_review" if risk in {"medium", "high"} else "supported_contract"


def _audit(**kwargs: Any) -> OpenCodeCommandAudit:
    risk = _normalize_risk(kwargs.get("risk_level"))
    status = _text(kwargs.get("compatibility_status"), _compat_for_risk(risk))
    if status not in COMPATIBILITY:
        status = _compat_for_risk(risk)
    return OpenCodeCommandAudit(
        source_kind=_text(kwargs.get("source_kind"), "unknown") if _text(kwargs.get("source_kind"), "unknown") in SOURCE_KINDS else "unknown",
        command_name=_normalize_command_name(kwargs.get("command_name")),
        command_origin=_text(kwargs.get("command_origin")),
        command_family=_text(kwargs.get("command_family"), "unknown"),
        compatibility_status=status,
        risk_level=risk,
        required_actions=_dedupe(_as_list(kwargs.get("required_actions"))),
        unsupported_reason=_text(kwargs.get("unsupported_reason")),
        safe_equivalent=_text(kwargs.get("safe_equivalent"), "OpenSwarm command preview/approval contract"),
        evidence_refs=_dedupe(_as_list(kwargs.get("evidence_refs"))),
        policy_notes=_dedupe(_as_list(kwargs.get("policy_notes"))),
    )


def dump_opencode_command(value: Any) -> dict[str, Any]:
    return _safe(value)


def build_opencode_command_audit(**kwargs: Any) -> OpenCodeCommandAudit:
    return _audit(**kwargs)


_BUILT_INS: list[tuple[str, str, str, str, str]] = [
    ("/init", "project", "Initialize local project guidance", "swarm", "low"),
    ("/undo", "session", "Plan reversal of latest safe action", "swarm", "medium"),
    ("/redo", "session", "Plan redo of latest safe action", "swarm", "medium"),
    ("/share", "session", "Sharing is disabled; offer local export only", "unknown", "high"),
    ("/help", "debug", "Show local help for commands", "swarm", "low"),
]
_FUTURE_FAMILIES = ["/model", "/agent", "/session", "/project", "/config", "/tools", "/mcp", "/skill", "/terminal", "/preview", "/debug", "/qa"]


def build_builtin_slash_command_registry() -> BuiltInSlashCommandRegistry:
    commands: list[dict[str, Any]] = []
    for name, family, description, route, risk in _BUILT_INS:
        required = ["local_preview_only"]
        notes = ["Registry describes command parity only; no command is executed."]
        status = _compat_for_risk(risk)
        if name == "/share":
            required.extend(["keep_community_sharing_disabled", "offer_local_export_only"])
            status = "needs_review"
        commands.append(dump_opencode_command(SlashCommandDefinition(
            name=name,
            family=family,
            description=description,
            compatibility_status=status,
            risk_level=risk,
            recommended_route=route,
            required_actions=required,
            policy_notes=notes,
        )))
    for family in _FUTURE_FAMILIES:
        commands.append(dump_opencode_command(SlashCommandDefinition(
            name=family,
            family=family.strip("/"),
            description="Reserved OpenCode parity family; contract-only route pending implementation.",
            compatibility_status="needs_review",
            risk_level="medium" if family in {"/tools", "/mcp", "/terminal", "/model"} else "low",
            recommended_route="terminal" if family == "/terminal" else "tool" if family in {"/tools", "/mcp"} else family.strip("/"),
            required_actions=["implement_family_router_before_execution"],
            policy_notes=["Future family is intentionally non-executable in this contract block."],
        )))
    return BuiltInSlashCommandRegistry(commands=commands, future_families=_FUTURE_FAMILIES)


def detect_argument_placeholders(template: str) -> list[str]:
    return _dedupe([match.group(0) for match in PLACEHOLDER_RE.finditer(template or "")])


def guard_shell_interpolation(text: str) -> ShellInterpolationGuardDecision:
    body = text or ""
    detected = [name for name, pattern in SHELL_PATTERNS if pattern.search(body)]
    if "command_substitution" in detected:
        interpolation_bodies = " ".join(re.findall(r"\$\(([^)]*)\)", body))
        if re.search(r"\b(rm|curl|wget|sudo|powershell|pwsh|ssh|scp|chmod|chown)\b|[|;&]", interpolation_bodies):
            decision = "blocked"
        elif re.search(r">|<|\b(cat|type|Get-Content)\b", interpolation_bodies):
            decision = "requires_approval"
        else:
            decision = "requires_preview"
    elif "backticks" in detected or "sensitive_env" in detected:
        decision = "requires_approval"
    elif "redirection" in detected:
        decision = "requires_preview"
    else:
        decision = "allow_text_only"
    actions = []
    if decision == "blocked":
        actions = ["remove_shell_interpolation", "rewrite_as_safe_open_swarm_action"]
    elif decision == "requires_approval":
        actions = ["show_preview", "request_user_approval", "do_not_execute_shell"]
    elif decision == "requires_preview":
        actions = ["show_preview", "do_not_execute_shell"]
    return ShellInterpolationGuardDecision(
        decision=decision,
        detected_patterns=_dedupe(detected),
        risk_level={"allow_text_only": "low", "requires_preview": "medium", "requires_approval": "high", "blocked": "critical"}[decision],
        required_actions=actions,
    )


def detect_file_references(text: str) -> list[str]:
    refs = [m.group(1) for m in FILE_REF_RE.finditer(text or "")]
    refs.extend(m.group(1) for m in MD_LINK_RE.finditer(text or ""))
    return _dedupe(refs)


def expand_file_references(text: str, *, workspace_root: str | Path | None = None) -> FileReferenceExpansion:
    requested = detect_file_references(text)
    root = Path(workspace_root or ".").resolve()
    normalized: list[str] = []
    missing: list[str] = []
    out_of_workspace: list[str] = []
    actions: list[str] = []
    for ref in requested:
        ref_text = ref.strip().strip("<>")
        candidate = Path(ref_text)
        resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        try:
            resolved.relative_to(root)
            in_workspace = True
        except ValueError:
            in_workspace = False
        if not in_workspace:
            out_of_workspace.append(ref_text)
            actions.append("review_out_of_workspace_reference")
            continue
        normalized.append(resolved.relative_to(root).as_posix())
        if not resolved.exists():
            missing.append(resolved.relative_to(root).as_posix())
            actions.append("review_missing_file_reference")
    return FileReferenceExpansion(
        workspace_root=root.as_posix(),
        requested_refs=requested,
        normalized_refs=_dedupe(normalized),
        missing_refs=_dedupe(missing),
        out_of_workspace_refs=_dedupe(out_of_workspace),
        required_actions=_dedupe(actions),
    )


def expand_command_arguments(template: str, *, arguments: list[Any] | None = None, named_args: dict[str, Any] | None = None) -> CommandArgumentExpansion:
    args = [_text(v, limit=600) for v in (arguments or [])]
    named = {str(k): _text(v, limit=600) for k, v in (named_args or {}).items() if not _is_sensitive_key(k)}
    placeholders = detect_argument_placeholders(template)
    missing: list[str] = []
    used_positions: set[int] = set()
    used_named: set[str] = set()

    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if token == "ARGUMENTS":
            used_positions.update(range(len(args)))
            return " ".join(args)
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(args):
                used_positions.add(index)
                return args[index]
            missing.append(f"${token}")
            return ""
        if token in named:
            used_named.add(token)
            return named[token]
        missing.append(f"${token}")
        return ""

    expanded = PLACEHOLDER_RE.sub(repl, template or "")
    unused = [f"${i + 1}" for i in range(len(args)) if i not in used_positions]
    unused.extend(f"${key}" for key in named if key not in used_named)
    return CommandArgumentExpansion(
        template_preview=_text(template, limit=MAX_BODY),
        expanded_preview=_text(expanded, limit=MAX_BODY),
        placeholders=placeholders,
        missing_args=_dedupe(missing),
        unused_args=_dedupe(unused),
        named_args_used=_dedupe(list(used_named)),
    )


def _extract_markdown_title_description(body: str) -> tuple[str, str]:
    title = ""
    description = ""
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") and not title:
            title = stripped.lstrip("#").strip()
        elif not description and not stripped.startswith("---"):
            description = stripped[:MAX_TEXT]
        if title and description:
            break
    return title, description


def load_custom_command_file_candidate(path: str | Path, *, workspace_root: str | Path | None = None, max_chars: int = MAX_BODY) -> CustomCommandFileCandidate:
    root = Path(workspace_root or ".").resolve()
    candidate_path = Path(path)
    resolved = (root / candidate_path).resolve() if not candidate_path.is_absolute() else candidate_path.resolve()
    required: list[str] = []
    body = ""
    origin = ""
    try:
        resolved.relative_to(root)
        in_workspace = True
    except ValueError:
        in_workspace = False
    if not in_workspace:
        required.append("reject_out_of_workspace_command_file")
        risk = "critical"
        status = "blocked"
    elif not resolved.exists() or not resolved.is_file():
        required.append("review_missing_command_file")
        risk = "medium"
        status = "needs_review"
    else:
        body = resolved.read_text(encoding="utf-8", errors="replace")[:max_chars]
        origin = resolved.relative_to(root).as_posix()
        guard = guard_shell_interpolation(body)
        risk = _risk_from_guard(guard)
        status = _compat_for_risk(risk)
        required.extend(guard.required_actions)
    title, description = _extract_markdown_title_description(body)
    guard = guard_shell_interpolation(body)
    files = detect_file_references(body)
    placeholders = detect_argument_placeholders(body)
    audit = _audit(
        source_kind="custom_markdown",
        command_name=resolved.stem,
        command_origin=origin or str(candidate_path),
        command_family="custom",
        compatibility_status=status,
        risk_level=risk,
        required_actions=required,
        unsupported_reason="out_of_workspace" if not in_workspace else "",
        policy_notes=["Markdown command was inspected as bounded text only; content was not executed."],
    )
    return CustomCommandFileCandidate(
        command_name=_normalize_command_name(resolved.stem),
        command_origin=origin or str(candidate_path),
        title=title,
        description=description,
        body_preview=_text(body, limit=max_chars),
        placeholders=placeholders,
        file_references=files,
        shell_interpolation_detected=bool(guard.detected_patterns),
        risk_level=risk,
        required_actions=_dedupe(required),
        audit=dump_opencode_command(audit),
    )


def _command_from_config_entry(entry: dict[str, Any], fallback: str = "") -> str:
    return _normalize_command_name(entry.get("name") or entry.get("id") or entry.get("command") or fallback)


def load_json_config_command_candidate(config: dict[str, Any] | list[Any], *, command_key: str | None = None) -> JsonConfigCommandCandidate:
    if isinstance(config, list):
        entry = next((item for item in config if isinstance(item, dict)), {})
    elif isinstance(config, dict) and command_key and isinstance(config.get(command_key), dict):
        entry = {"name": command_key, **config[command_key]}
    elif isinstance(config, dict) and isinstance(config.get("commands"), dict):
        key = command_key or next(iter(config["commands"]), "")
        item = config["commands"].get(key) if key else {}
        entry = {"name": key, **item} if isinstance(item, dict) else {"name": key, "template": item}
    elif isinstance(config, dict) and isinstance(config.get("commands"), list):
        entry = next((item for item in config["commands"] if isinstance(item, dict)), {})
    elif isinstance(config, dict):
        entry = config
    else:
        entry = {}
    blocked = [str(k) for k in entry if _is_sensitive_key(k) or any(tok in str(k).lower().replace("-", "_") for tok in DANGEROUS_PERMISSION_TOKENS)]
    permissions = _dedupe(_as_list(entry.get("permissions") or entry.get("permission") or entry.get("allowed_permissions")))
    tools = _dedupe(_as_list(entry.get("tools") or entry.get("allowed_tools") or entry.get("required_tools")))
    dangerous_values = [p for p in permissions + tools if any(tok in p.lower().replace("-", "_") for tok in DANGEROUS_PERMISSION_TOKENS)]
    template = _text(entry.get("template") or entry.get("prompt") or entry.get("body") or entry.get("description"), limit=MAX_BODY)
    guard = guard_shell_interpolation(template)
    risk = _risk_from_guard(guard)
    required = list(guard.required_actions)
    if blocked or dangerous_values:
        risk = "critical"
        required.extend(["remove_dangerous_permission_or_config", "manual_security_review"])
    if entry.get("agent") or entry.get("model") or tools:
        required.append("review_command_routing")
    audit = _audit(
        source_kind="json_config",
        command_name=_command_from_config_entry(entry, command_key or "unknown"),
        command_origin="opencode.jsonc:commands",
        command_family="custom",
        compatibility_status=_compat_for_risk(risk),
        risk_level=risk,
        required_actions=required,
        unsupported_reason="dangerous_permission_or_config" if risk == "critical" else "",
        policy_notes=["JSON/JSONC command config is normalized from caller-provided data only; no parser or execution is invoked."],
    )
    return JsonConfigCommandCandidate(
        command_name=_command_from_config_entry(entry, command_key or "unknown"),
        description=_text(entry.get("description") or entry.get("title")),
        prompt_template_preview=template,
        requested_agent=_text(entry.get("agent") or entry.get("requested_agent")),
        requested_model=_text(entry.get("model") or entry.get("requested_model")),
        requested_tools=tools,
        requested_permissions=permissions,
        blocked_keys=_dedupe(blocked + dangerous_values),
        risk_level=risk,
        required_actions=_dedupe(required),
        audit=dump_opencode_command(audit),
    )


def route_command(command_name: str = "", *, requested_agent: str | None = None, requested_model: str | None = None, requested_tool: str | None = None, requested_target: str | None = None) -> CommandRoutingDecision:
    name = _normalize_command_name(command_name)
    target = _text(requested_target).lower()
    if not target:
        if requested_tool:
            target = "tool"
        elif requested_agent:
            target = "agent"
        elif requested_model:
            target = "model"
        elif name in {"/preview"}:
            target = "preview"
        elif name in {"/qa"}:
            target = "qa"
        elif name in {"/terminal"}:
            target = "terminal"
        else:
            target = "swarm"
    if target not in TARGET_KINDS:
        target = "unknown"
    required = ["preview_routing_decision"]
    notes = ["Routing contract is non-executable by default."]
    requires_approval = target in {"tool", "terminal", "model"} or bool(requested_agent or requested_model or requested_tool)
    if target == "terminal":
        required.extend(["terminal_integration_not_connected", "request_user_approval"])
    elif target == "tool":
        required.extend(["tool_integration_not_connected", "request_user_approval"])
    elif target == "model":
        required.extend(["model_switch_requires_user_approval"])
    elif requested_agent:
        required.append("agent_routing_requires_review")
    return CommandRoutingDecision(
        target_kind=target,
        target_id=_text(requested_tool or requested_agent or requested_model or name),
        requested_model=_text(requested_model),
        requested_agent=_text(requested_agent),
        required_actions=_dedupe(required),
        policy_notes=notes,
        can_execute=False,
        requires_user_approval=requires_approval,
    )



_FAMILY_DEFINITIONS: list[dict[str, Any]] = [
    {"family_id": "session", "display_name": "Session", "opencode_pattern": "/undo /redo /session", "openswarm_equivalent": "local session state candidate", "support_status": "partial", "risk_level": "medium", "requires_preview": True, "requires_approval": True, "unsupported_reason": "execution runtime not connected", "required_actions": ["preview_reversible_state"]},
    {"family_id": "project", "display_name": "Project", "opencode_pattern": "/init /project", "openswarm_equivalent": "project instructions/bootstrap candidate", "support_status": "partial", "risk_level": "low", "requires_preview": True, "requires_approval": False, "unsupported_reason": "automatic writes disabled", "required_actions": ["preview_project_bootstrap"]},
    {"family_id": "config", "display_name": "Config", "opencode_pattern": "/config", "openswarm_equivalent": "configuration review request", "support_status": "planned", "risk_level": "medium", "requires_preview": True, "requires_approval": True, "unsupported_reason": "config mutation runtime not connected", "required_actions": ["review_configuration_policy"]},
    {"family_id": "model", "display_name": "Model", "opencode_pattern": "/model", "openswarm_equivalent": "model selection request, policy gated", "support_status": "partial", "risk_level": "medium", "requires_preview": True, "requires_approval": True, "unsupported_reason": "model switch requires policy gate", "required_actions": ["review_model_policy"]},
    {"family_id": "agent", "display_name": "Agent", "opencode_pattern": "/agent @agent", "openswarm_equivalent": "agent routing request", "support_status": "partial", "risk_level": "medium", "requires_preview": True, "requires_approval": True, "unsupported_reason": "agent routing execution not connected", "required_actions": ["review_agent_routing"]},
    {"family_id": "tool", "display_name": "Tool", "opencode_pattern": "/tools", "openswarm_equivalent": "tool selection/request preview", "support_status": "planned", "risk_level": "high", "requires_preview": True, "requires_approval": True, "unsupported_reason": "tool execution runtime not connected", "required_actions": ["review_tool_policy"]},
    {"family_id": "mcp", "display_name": "MCP", "opencode_pattern": "/mcp", "openswarm_equivalent": "MCP activation request preview", "support_status": "blocked", "risk_level": "high", "requires_preview": True, "requires_approval": True, "unsupported_reason": "MCP activation disabled in this block", "required_actions": ["keep_mcp_disabled"]},
    {"family_id": "skill", "display_name": "Skill", "opencode_pattern": "/skill", "openswarm_equivalent": "skill discovery/import candidate", "support_status": "partial", "risk_level": "medium", "requires_preview": True, "requires_approval": True, "unsupported_reason": "automatic install disabled", "required_actions": ["preview_skill_candidate"]},
    {"family_id": "terminal", "display_name": "Terminal", "opencode_pattern": "/terminal $(...) `...`", "openswarm_equivalent": "terminal request boundary", "support_status": "blocked", "risk_level": "high", "requires_preview": True, "requires_approval": True, "unsupported_reason": "terminal execution runtime not connected", "required_actions": ["request_user_approval", "require_safeshell_policy_matrix"]},
    {"family_id": "preview", "display_name": "Preview", "opencode_pattern": "/preview", "openswarm_equivalent": "local preview/dry-run report", "support_status": "partial", "risk_level": "low", "requires_preview": True, "requires_approval": False, "unsupported_reason": "preview runtime is report-only", "required_actions": ["show_preview_report"]},
    {"family_id": "debug", "display_name": "Debug", "opencode_pattern": "/debug", "openswarm_equivalent": "local debug context request", "support_status": "planned", "risk_level": "medium", "requires_preview": True, "requires_approval": True, "unsupported_reason": "debug actions not connected", "required_actions": ["review_debug_scope"]},
    {"family_id": "qa", "display_name": "QA", "opencode_pattern": "/qa", "openswarm_equivalent": "local QA plan request", "support_status": "partial", "risk_level": "low", "requires_preview": True, "requires_approval": False, "unsupported_reason": "QA execution not connected", "required_actions": ["build_qa_plan_only"]},
    {"family_id": "help", "display_name": "Help", "opencode_pattern": "/help", "openswarm_equivalent": "local command help/palette", "support_status": "supported", "risk_level": "low", "requires_preview": False, "requires_approval": False, "unsupported_reason": "", "required_actions": []},
    {"family_id": "share", "display_name": "Share / Export", "opencode_pattern": "/share", "openswarm_equivalent": "local export/share snapshot", "support_status": "partial", "risk_level": "high", "requires_preview": True, "requires_approval": True, "unsupported_reason": "external publishing disabled", "required_actions": ["keep_external_sharing_disabled", "preview_local_export"]},
]

_COMMAND_TO_FAMILY: dict[str, str] = {
    "/help": "help", "/init": "project", "/undo": "session", "/redo": "session", "/share": "share",
    "/export": "share", "/model": "model", "/agent": "agent", "/skill": "skill", "/terminal": "terminal", "/qa": "qa",
    "/tools": "tool", "/tool": "tool", "/mcp": "mcp", "/preview": "preview", "/debug": "debug", "/config": "config", "/project": "project", "/session": "session",
}

_SAFE_EQUIVALENTS: dict[str, dict[str, Any]] = {
    "/help": {"safe_equivalent_id": "local_command_help_palette", "action_kind": "show_local_help", "preview_required": False, "approval_required": False, "execution_supported": True, "blocked_reason": "", "required_actions": []},
    "/init": {"safe_equivalent_id": "project_bootstrap_candidate", "action_kind": "preview_project_instructions_bootstrap", "preview_required": True, "approval_required": False, "execution_supported": False, "blocked_reason": "automatic_project_writes_disabled", "required_actions": ["show_preview", "do_not_write_files"]},
    "/undo": {"safe_equivalent_id": "local_undo_candidate", "action_kind": "preview_reversible_undo", "preview_required": True, "approval_required": True, "execution_supported": False, "blocked_reason": "reversible_state_not_verified", "required_actions": ["verify_reversible_state", "request_user_approval"]},
    "/redo": {"safe_equivalent_id": "local_redo_candidate", "action_kind": "preview_reversible_redo", "preview_required": True, "approval_required": True, "execution_supported": False, "blocked_reason": "reversible_state_not_verified", "required_actions": ["verify_reversible_state", "request_user_approval"]},
    "/share": {"safe_equivalent_id": "local_export_snapshot", "action_kind": "preview_local_export", "preview_required": True, "approval_required": True, "execution_supported": False, "blocked_reason": "external_publication_disabled", "required_actions": ["keep_external_sharing_disabled", "request_user_approval"]},
    "/model": {"safe_equivalent_id": "model_selection_request", "action_kind": "request_model_selection", "preview_required": True, "approval_required": True, "execution_supported": False, "blocked_reason": "policy_gate_required", "required_actions": ["review_model_policy", "request_user_approval"]},
    "/agent": {"safe_equivalent_id": "agent_routing_request", "action_kind": "request_agent_route", "preview_required": True, "approval_required": True, "execution_supported": False, "blocked_reason": "agent_execution_not_connected", "required_actions": ["review_agent_routing"]},
    "/skill": {"safe_equivalent_id": "skill_discovery_import_candidate", "action_kind": "preview_skill_candidate", "preview_required": True, "approval_required": True, "execution_supported": False, "blocked_reason": "automatic_skill_install_disabled", "required_actions": ["review_skill_candidate"]},
    "/terminal": {"safe_equivalent_id": "terminal_boundary_request", "action_kind": "preview_terminal_request", "preview_required": True, "approval_required": True, "execution_supported": False, "blocked_reason": "terminal_runtime_not_connected", "required_actions": ["require_safeshell_policy_matrix", "request_user_approval"]},
    "/qa": {"safe_equivalent_id": "local_qa_plan_request", "action_kind": "build_qa_plan_only", "preview_required": True, "approval_required": False, "execution_supported": False, "blocked_reason": "qa_execution_not_connected", "required_actions": ["dry_run_only"]},
}


def command_family_for_command(command_name: str) -> str:
    return _COMMAND_TO_FAMILY.get(_normalize_command_name(command_name), "unknown")


def build_command_family_parity_registry() -> CommandFamilyParityRegistry:
    families = []
    for raw in _FAMILY_DEFINITIONS:
        item = CommandFamilyParityDefinition(
            **raw,
            can_execute_now=False,
            evidence_refs=_dedupe(_as_list(raw.get("evidence_refs"))),
            policy_notes=_dedupe(_as_list(raw.get("policy_notes") or ["Parity registry is descriptive only; execution stays disabled."])),
        )
        families.append(dump_opencode_command(item))
    return CommandFamilyParityRegistry(families=families, can_execute_now=False)


def build_safe_command_equivalent(command_name: str) -> SafeCommandEquivalent:
    name = _normalize_command_name(command_name)
    family = command_family_for_command(name)
    defaults = {
        "safe_equivalent_id": f"{family}_preview_request" if family != "unknown" else "unknown_preview_request",
        "action_kind": "preview_only",
        "preview_required": True,
        "approval_required": True,
        "execution_supported": False,
        "blocked_reason": "no_safe_equivalent_connected",
        "required_actions": ["show_preview", "request_user_approval"],
    }
    data = {**defaults, **_SAFE_EQUIVALENTS.get(name, {})}
    return SafeCommandEquivalent(
        command_name=name,
        command_family=family,
        safe_equivalent_id=data["safe_equivalent_id"],
        action_kind=data["action_kind"],
        preview_required=bool(data["preview_required"]),
        approval_required=bool(data["approval_required"]),
        execution_supported=bool(data["execution_supported"]),
        blocked_reason=_text(data.get("blocked_reason")),
        required_actions=_dedupe(_as_list(data.get("required_actions"))),
        policy_notes=["Safe equivalent does not bypass SafeShell or PolicyMatrix."],
    )


def build_terminal_boundary_decision(*, terminal_kind: str = "unknown", command_preview: str = "", request_id: str = "") -> TerminalBoundaryDecision:
    kind = _text(terminal_kind, "unknown").lower()
    if kind in {"user", "manual", "user_terminal"}:
        kind = "user_terminal"
    elif kind in {"agent", "agent_terminal", "controlled"}:
        kind = "agent_terminal"
    else:
        kind = "unknown"
    is_user = kind == "user_terminal"
    is_agent = kind == "agent_terminal"
    actions = ["show_terminal_preview", "do_not_execute_terminal"]
    notes = []
    if is_user:
        actions.append("user_must_execute_manually_outside_openswarm")
        notes.append("OpenSwarm may show help/context only; user owns manual execution.")
    elif is_agent:
        actions.extend(["require_safeshell", "require_policy_matrix", "request_user_approval", "capture_evidence"])
        notes.append("Agent Terminal is future-only and must be gated by SafeShell, PolicyMatrix, approval, sandbox, timeout, redaction and evidence.")
    else:
        actions.append("choose_user_or_agent_terminal_boundary")
    return TerminalBoundaryDecision(
        terminal_kind=kind,
        request_id=_text(request_id),
        command_preview=_text(command_preview, limit=MAX_BODY),
        user_executes_manually=is_user,
        agent_controlled=is_agent,
        requires_safeshell=is_agent,
        requires_policy_matrix=is_agent,
        requires_approval=True,
        requires_sandbox=is_agent,
        requires_timeout=is_agent,
        requires_redaction=True,
        requires_evidence=is_agent,
        can_execute=False,
        required_actions=_dedupe(actions),
        policy_notes=notes,
    )


def build_user_terminal_request(*, command_preview: str = "", request_id: str = "", context_help: str = "") -> UserTerminalRequest:
    return UserTerminalRequest(request_id=_text(request_id), command_preview=_text(command_preview, limit=MAX_BODY), context_help=_text(context_help), required_actions=["show_context_help", "user_executes_manually"])


def build_agent_terminal_request(*, command_preview: str = "", request_id: str = "") -> AgentTerminalRequest:
    return AgentTerminalRequest(request_id=_text(request_id), command_preview=_text(command_preview, limit=MAX_BODY), required_actions=["require_safeshell", "require_policy_matrix", "request_user_approval", "require_sandbox", "require_timeout", "redact_output", "capture_evidence"])


def build_terminal_risk_decision(*, terminal_kind: str = "unknown", command_preview: str = "") -> TerminalRiskDecision:
    boundary = build_terminal_boundary_decision(terminal_kind=terminal_kind, command_preview=command_preview)
    risk = "high" if boundary.agent_controlled else "medium" if boundary.user_executes_manually else "unknown"
    return TerminalRiskDecision(terminal_kind=boundary.terminal_kind, risk_level=risk, decision="requires_approval", required_actions=boundary.required_actions, can_execute=False)


def build_command_preview_report(command_text: str, *, workspace_root: str | Path | None = None, arguments: list[Any] | None = None, named_args: dict[str, Any] | None = None, terminal_kind: str = "unknown") -> CommandPreviewReport:
    text = _text(command_text, limit=MAX_BODY)
    parts = text.split()
    command_name = _normalize_command_name(parts[0] if parts else "/unknown")
    arg_text = text[len(parts[0]):].strip() if parts else ""
    arg_expansion = expand_command_arguments(arg_text, arguments=arguments, named_args=named_args)
    file_refs = expand_file_references(text, workspace_root=workspace_root)
    guard = guard_shell_interpolation(text)
    safe = build_safe_command_equivalent(command_name)
    family = safe.command_family
    terminal_boundary = build_terminal_boundary_decision(terminal_kind=(terminal_kind if command_name == "/terminal" or guard.detected_patterns else "unknown"), command_preview=text)
    risks = [safe.command_family and safe.approval_required and "medium", guard.risk_level]
    if command_name == "/terminal" or terminal_boundary.agent_controlled:
        risks.append("high")
    if file_refs.out_of_workspace_refs:
        risks.append("high")
    if guard.decision == "blocked":
        risk = "critical"
    elif "high" in risks:
        risk = "high"
    elif "medium" in risks:
        risk = "medium"
    else:
        risk = "low"
    required = _dedupe(safe.required_actions + guard.required_actions + file_refs.required_actions + terminal_boundary.required_actions + arg_expansion.missing_args)
    return CommandPreviewReport(
        command_name=command_name,
        command_family=family,
        parsed_args=dump_opencode_command(arg_expansion),
        file_refs=dump_opencode_command(file_refs),
        shell_interpolation_decision=dump_opencode_command(guard),
        safe_equivalent=dump_opencode_command(safe),
        terminal_boundary=dump_opencode_command(terminal_boundary),
        risk_level=risk,
        required_actions=required,
        can_execute=False,
        dry_run_only=True,
        tools_called=False,
        files_read=False,
        shell_executed=False,
        mcp_activated=False,
    )

def build_opencode_command_trace_source(
    *,
    command_name: str,
    origin: str = "",
    audit: OpenCodeCommandAudit | dict[str, Any] | None = None,
    routing: CommandRoutingDecision | dict[str, Any] | None = None,
    safe_equivalent: SafeCommandEquivalent | dict[str, Any] | None = None,
    terminal_boundary: TerminalBoundaryDecision | dict[str, Any] | None = None,
    preview_report: CommandPreviewReport | dict[str, Any] | None = None,
    required_actions: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = _normalize_command_name(command_name)
    preview_data = dump_opencode_command(preview_report or {})
    safe_data = dump_opencode_command(safe_equivalent or preview_data.get("safe_equivalent") or build_safe_command_equivalent(name))
    terminal_data = dump_opencode_command(terminal_boundary or preview_data.get("terminal_boundary") or {})
    family = command_family_for_command(name) or safe_data.get("command_family") or preview_data.get("command_family") or "unknown"
    audit_data = dump_opencode_command(audit or _audit(command_name=name, command_origin=origin, command_family=family, risk_level=preview_data.get("risk_level") or safe_data.get("risk_level") or "unknown", safe_equivalent=safe_data.get("safe_equivalent_id")))
    routing_data = dump_opencode_command(routing or route_command(name))
    required = _dedupe(_as_list(required_actions) + _as_list(audit_data.get("required_actions")) + _as_list(routing_data.get("required_actions")) + _as_list(safe_data.get("required_actions")) + _as_list(preview_data.get("required_actions")))
    risk = _normalize_risk(preview_data.get("risk_level") or audit_data.get("risk_level") or "unknown")
    source = OpenCodeCommandTraceSource(
        command_name=name,
        origin=_text(origin),
        command_family=_text(family, "unknown"),
        compatibility_status=_text(audit_data.get("compatibility_status"), "unknown"),
        risk_level=risk,
        safe_equivalent=safe_data,
        terminal_boundary=terminal_data,
        preview_report=preview_data,
        routing=routing_data,
        required_actions=required,
        audit=audit_data,
        dry_run_only=True,
        metadata=_safe(metadata or {}),
    )
    return dump_opencode_command(source)
