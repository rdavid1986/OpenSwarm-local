"""Side-effect-free project rules import contracts.

This module imports external rule/instruction/prompt/workflow sources as
reviewable candidates only. It never injects prompts, writes files, executes
commands, activates tools/MCP, writes memory, or mutates runtime state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any


PROJECT_RULES_IMPORT_VERSION = "openswarm.project_rules_import.v1"

SUPPORTED_RULE_FORMATS = {
    "github_copilot_instructions",
    "github_copilot_prompt_file",
    "cursor_project_rule",
    "cursor_user_rule",
    "cursor_team_rule",
    "cursor_agents_md",
    "windsurf_rule",
    "windsurf_workflow",
    "opencode_agents_md",
    "opencode_custom_command",
    "agents_md",
    "markdown_prompt_pack",
    "generic_markdown_rule",
    "unknown",
}

RULE_CANDIDATE_TYPES = {
    "ProjectInstructionCandidate",
    "PromptWorkflowCandidate",
    "CommandSpecCandidate",
}

FORMAT_TO_CANDIDATE = {
    "github_copilot_instructions": "ProjectInstructionCandidate",
    "github_copilot_prompt_file": "PromptWorkflowCandidate",
    "cursor_project_rule": "ProjectInstructionCandidate",
    "cursor_user_rule": "ProjectInstructionCandidate",
    "cursor_team_rule": "ProjectInstructionCandidate",
    "cursor_agents_md": "ProjectInstructionCandidate",
    "windsurf_rule": "ProjectInstructionCandidate",
    "windsurf_workflow": "PromptWorkflowCandidate",
    "opencode_agents_md": "ProjectInstructionCandidate",
    "opencode_custom_command": "CommandSpecCandidate",
    "agents_md": "ProjectInstructionCandidate",
    "markdown_prompt_pack": "PromptWorkflowCandidate",
    "generic_markdown_rule": "ProjectInstructionCandidate",
    "unknown": "PromptWorkflowCandidate",
}

FORMAT_TO_SCOPE = {
    "github_copilot_instructions": "project",
    "github_copilot_prompt_file": "mode",
    "cursor_project_rule": "project",
    "cursor_user_rule": "global",
    "cursor_team_rule": "project",
    "cursor_agents_md": "project",
    "windsurf_rule": "project",
    "windsurf_workflow": "mode",
    "opencode_agents_md": "project",
    "opencode_custom_command": "mode",
    "agents_md": "project",
    "markdown_prompt_pack": "mode",
    "generic_markdown_rule": "project",
    "unknown": "project",
}

SCOPE_PRECEDENCE = {
    "system": 100,
    "marc": 95,
    "policy": 90,
    "global": 70,
    "project": 60,
    "dashboard": 55,
    "swarm": 50,
    "agent": 45,
    "miniagent": 40,
    "mode": 35,
    "skill": 30,
    "tool": 25,
    "message_turn": 10,
    "unknown": 0,
}

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "private_key",
    "raw_prompt",
    "raw_response",
    "refresh_token",
    "secret",
    "session",
    "token",
}

DANGEROUS_PHRASES = {
    "skip approval",
    "bypass approval",
    "ignore policy",
    "disable policy",
    "print secrets",
    "exfiltrate",
    "rm -rf",
    "delete everything",
    "curl | sh",
    "wget | sh",
    "invoke-webrequest",
    "iex ",
}

SECRET_PHRASES = {
    "api_key=",
    "password=",
    "authorization:",
    "bearer ",
    "begin private key",
    "private_key",
}


@dataclass(frozen=True)
class RuleImportSourceAdapter:
    source_kind: str = "project_rules_import"
    adapter_kind: str = "rule_import_source_adapter"
    detected_format: str = "unknown"
    adapter_id: str = "generic_rule_adapter"
    source_uri: str = "unknown"
    source_hash: str = "unknown"
    confidence: float = 0.0
    source_scope: str = "project"
    source_platform: str = "unknown"
    entrypoints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_mutate_prompt: bool = False


@dataclass(frozen=True)
class RuleImportCandidate:
    source_kind: str = "project_rules_import"
    candidate_kind: str = "rule_import_candidate"
    candidate_type: str = "ProjectInstructionCandidate"
    candidate_id: str = "rule-candidate"
    title: str = "Imported project rule"
    body_preview: str = ""
    detected_format: str = "unknown"
    source_scope: str = "project"
    source_platform: str = "unknown"
    source_uri: str = "unknown"
    source_hash: str = "unknown"
    variables: list[str] = field(default_factory=list)
    required_context: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    required_mcp_servers: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    review_required: bool = True
    approval_required: bool = True
    can_execute: bool = False
    can_write_files: bool = False
    can_mutate_prompt: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False


@dataclass(frozen=True)
class RuleImportDiagnosticReport:
    source_kind: str = "project_rules_import"
    diagnostic_kind: str = "rule_import_diagnostic_report"
    status: str = "needs_review"
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    risk_flags: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_mutate_prompt: bool = False


@dataclass(frozen=True)
class RuleImportConflictReport:
    source_kind: str = "project_rules_import"
    conflict_kind: str = "rule_import_conflict_report"
    status: str = "clear"
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    duplicate_count: int = 0
    conflict_count: int = 0
    required_actions: list[str] = field(default_factory=list)
    can_mutate_prompt: bool = False


@dataclass(frozen=True)
class RuleScopePrecedenceDecision:
    source_kind: str = "project_rules_import"
    precedence_kind: str = "rule_scope_precedence_decision"
    source_scope: str = "project"
    effective_scope: str = "project"
    precedence_rank: int = 60
    marc_overrides_imported_rules: bool = True
    policy_overrides_imported_rules: bool = True
    runtime_injection_allowed: bool = False
    approval_required: bool = True
    required_actions: list[str] = field(default_factory=list)
    can_mutate_prompt: bool = False


@dataclass(frozen=True)
class RuleImportInjectionGate:
    source_kind: str = "project_rules_import"
    gate_kind: str = "rule_import_injection_gate"
    status: str = "blocked"
    injection_allowed: bool = False
    approval_required: bool = True
    approved: bool = False
    reviewer: str = "human_required"
    reason: str = "Rule imports require review before runtime injection."
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_mutate_prompt: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False


@dataclass(frozen=True)
class ProjectRulesImportTraceSource:
    source_kind: str = "project_rules_import"
    import_kind: str = "project_rules_import"
    adapter: dict[str, Any] = field(default_factory=dict)
    candidate: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    conflicts: dict[str, Any] = field(default_factory=dict)
    precedence: dict[str, Any] = field(default_factory=dict)
    injection_gate: dict[str, Any] = field(default_factory=dict)
    status: str = "needs_review"
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_mutate_prompt: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False


def _text(value: Any, fallback: str = "", *, limit: int = 4000) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return text[:limit]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]
    output: list[str] = []
    for item in raw:
        text = _text(item, limit=300)
        if text and text not in output:
            output.append(text)
    return output[:120]


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:120]:
            normalized = str(key or "").lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS or any(token in normalized for token in SENSITIVE_KEYS):
                output[str(key)] = "[redacted]"
            else:
                output[str(key)] = _safe(item)
        if len(value) > 120:
            output["__truncated__"] = f"+{len(value) - 120} more fields"
        return output
    if isinstance(value, list):
        visible = [_safe(item) for item in value[:120]]
        if len(value) > 120:
            visible.append(f"+{len(value) - 120} more")
        return visible
    if isinstance(value, tuple):
        return _safe(list(value))
    if isinstance(value, str):
        return value[:4000].rstrip() + ("..." if len(value) > 4000 else "")
    return value


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dataclass_fields__"):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return _safe(value)
    return {"value": _safe(value)}


def _hash_text(text: str) -> str:
    if not text:
        return "unknown"
    return sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _detect_from_path_and_content(path: str, content: str, explicit_format: str = "") -> tuple[str, str, list[str], float]:
    normalized_path = path.replace("\\", "/").lower()
    lowered = content.lower()
    explicit = explicit_format.lower().replace("-", "_").strip()
    if explicit in SUPPORTED_RULE_FORMATS:
        return explicit, _platform_for_format(explicit), ["explicit_format"], 0.92
    if normalized_path.endswith(".github/copilot-instructions.md") or "copilot-instructions" in normalized_path:
        return "github_copilot_instructions", "github_copilot", ["copilot_instructions"], 0.9
    if ".github/prompts/" in normalized_path or normalized_path.endswith(".prompt.md"):
        return "github_copilot_prompt_file", "github_copilot", ["copilot_prompt_file"], 0.86
    if normalized_path.endswith("agents.md"):
        if "opencode" in lowered:
            return "opencode_agents_md", "opencode", ["agents_md"], 0.82
        if "cursor" in lowered:
            return "cursor_agents_md", "cursor", ["agents_md"], 0.82
        return "agents_md", "generic", ["agents_md"], 0.78
    if ".cursor/rules" in normalized_path or normalized_path.endswith(".cursorrules") or "cursor rule" in lowered:
        return "cursor_project_rule", "cursor", ["cursor_rule"], 0.82
    if ".windsurf" in normalized_path or normalized_path.endswith(".windsurfrules") or "windsurf" in lowered:
        if "workflow" in lowered:
            return "windsurf_workflow", "windsurf", ["windsurf_workflow"], 0.78
        return "windsurf_rule", "windsurf", ["windsurf_rule"], 0.78
    if ".opencode/command" in normalized_path or "opencode command" in lowered or "slash command" in lowered:
        return "opencode_custom_command", "opencode", ["opencode_command"], 0.76
    if "workflow" in lowered or "prompt file" in lowered:
        return "markdown_prompt_pack", "generic", ["prompt_workflow"], 0.58
    if content.strip():
        return "generic_markdown_rule", "generic", ["markdown_rule"], 0.45
    return "unknown", "unknown", [], 0.0


def _platform_for_format(fmt: str) -> str:
    if fmt.startswith("github_copilot"):
        return "github_copilot"
    if fmt.startswith("cursor"):
        return "cursor"
    if fmt.startswith("windsurf"):
        return "windsurf"
    if fmt.startswith("opencode"):
        return "opencode"
    if fmt == "agents_md":
        return "generic"
    return "generic" if fmt != "unknown" else "unknown"


def build_rule_import_source_adapter(input_data: dict[str, Any] | None = None) -> RuleImportSourceAdapter:
    data = dict(input_data or {})
    path = _text(data.get("path") or data.get("source_uri") or data.get("filename"), fallback="unknown", limit=600)
    content = _text(data.get("content") or data.get("raw_text") or data.get("body"), fallback="", limit=40_000)
    detected_format, platform, entrypoints, confidence = _detect_from_path_and_content(path, content, _text(data.get("source_format")))
    source_hash = _text(data.get("source_hash"), fallback="", limit=160) or _hash_text(content)
    scope = _text(data.get("source_scope"), fallback=FORMAT_TO_SCOPE.get(detected_format, "project"))
    warnings: list[str] = []
    actions: list[str] = []

    if detected_format == "unknown":
        warnings.append("unknown_rule_format")
        actions.append("review_unknown_rule_format")
    if not content.strip():
        warnings.append("empty_rule_source")
        actions.append("provide_rule_content")
    if scope not in SCOPE_PRECEDENCE:
        warnings.append("unknown_rule_scope")
        actions.append("confirm_rule_scope")
        scope = "unknown"

    return RuleImportSourceAdapter(
        detected_format=detected_format,
        adapter_id=f"{detected_format}_adapter" if detected_format != "unknown" else "generic_rule_adapter",
        source_uri=path,
        source_hash=source_hash,
        confidence=round(confidence, 3),
        source_scope=scope,
        source_platform=platform,
        entrypoints=entrypoints,
        warnings=warnings,
        required_actions=actions,
    )


def build_rule_import_candidate(input_data: dict[str, Any] | None = None, adapter: RuleImportSourceAdapter | dict[str, Any] | None = None) -> RuleImportCandidate:
    data = dict(input_data or {})
    adapter_data = _dump(adapter) if adapter is not None else _dump(build_rule_import_source_adapter(data))
    content = _text(data.get("content") or data.get("raw_text") or data.get("body"), fallback="", limit=40_000)
    detected_format = _text(adapter_data.get("detected_format"), fallback="unknown")
    candidate_type = FORMAT_TO_CANDIDATE.get(detected_format, "PromptWorkflowCandidate")
    source_uri = _text(adapter_data.get("source_uri"), fallback="unknown", limit=600)
    source_hash = _text(adapter_data.get("source_hash"), fallback="unknown", limit=160)
    title = _text(data.get("title") or data.get("name"), fallback=f"Imported {detected_format}", limit=200)
    warnings = _as_list(adapter_data.get("warnings"))
    actions = _as_list(adapter_data.get("required_actions"))
    required_tools = _as_list(data.get("required_tools"))
    required_mcp = _as_list(data.get("required_mcp_servers"))
    variables = _as_list(data.get("variables"))
    required_context = _as_list(data.get("required_context"))

    if required_tools:
        warnings.append("required_tools_declared")
        actions.append("review_required_tools_policy")
    if required_mcp:
        warnings.append("required_mcp_servers_declared")
        actions.append("review_required_mcp_servers_policy")
    if "secret" in content.lower() or any(phrase in content.lower() for phrase in SECRET_PHRASES):
        warnings.append("possible_secret_material")
        actions.append("remove_or_redact_secret_material")
    if any(phrase in content.lower() for phrase in DANGEROUS_PHRASES):
        warnings.append("dangerous_or_bypass_instruction")
        actions.append("remove_dangerous_or_bypass_instructions")

    provenance = _safe({
        "source_uri": source_uri,
        "source_hash": source_hash,
        "source_platform": adapter_data.get("source_platform") or "unknown",
        "source_format": detected_format,
        "source_scope": adapter_data.get("source_scope") or "project",
        "source_author": data.get("source_author") or "unknown",
        "source_license": data.get("source_license") or "unknown",
    })

    return RuleImportCandidate(
        candidate_type=candidate_type,
        candidate_id=f"rule-import-{source_hash[:16] if source_hash != 'unknown' else 'unknown'}",
        title=title,
        body_preview=content[:1200],
        detected_format=detected_format,
        source_scope=_text(adapter_data.get("source_scope"), fallback="project"),
        source_platform=_text(adapter_data.get("source_platform"), fallback="unknown"),
        source_uri=source_uri,
        source_hash=source_hash,
        variables=variables,
        required_context=required_context,
        required_tools=required_tools,
        required_mcp_servers=required_mcp,
        provenance=provenance,
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(actions or ["review_rule_import_candidate"])),
    )


def build_rule_import_diagnostic_report(candidate: RuleImportCandidate | dict[str, Any]) -> RuleImportDiagnosticReport:
    data = _dump(candidate)
    body = _text(data.get("body_preview"), limit=4000)
    lowered = body.lower()
    diagnostics: list[dict[str, Any]] = []
    actions: list[str] = []
    risk_flags: list[str] = []

    def add(severity: str, code: str, message: str, action: str | None = None) -> None:
        diagnostics.append({"severity": severity, "code": code, "message": message, "field": "body_preview"})
        if severity in {"error", "warning"}:
            risk_flags.append(code)
        if action:
            actions.append(action)

    if any(phrase in lowered for phrase in SECRET_PHRASES):
        add("error", "possible_secret_material", "Rule appears to contain secret-like material.", "remove_or_redact_secret_material")
    if any(phrase in lowered for phrase in DANGEROUS_PHRASES):
        add("error", "dangerous_or_bypass_instruction", "Rule includes dangerous execution or approval bypass instruction.", "remove_dangerous_or_bypass_instructions")
    if len(body) > 3000:
        add("warning", "rule_too_long", "Rule is long and should be split or scoped.", "split_or_scope_rule")
    if data.get("source_scope") in {"", "unknown"}:
        add("warning", "missing_scope", "Rule scope is missing or unknown.", "confirm_rule_scope")
    if data.get("provenance", {}).get("source_license") in {"", "unknown", None}:
        add("warning", "missing_license", "Rule source license is unknown.", "confirm_source_license")
    if data.get("required_tools"):
        add("warning", "required_tools_declared", "Rule declares tools that need policy review.", "review_required_tools_policy")
    if data.get("required_mcp_servers"):
        add("warning", "required_mcp_servers_declared", "Rule declares MCP servers that need policy review.", "review_required_mcp_servers_policy")
    if "validate" not in lowered and "test" not in lowered and "evidence" not in lowered:
        add("info", "missing_validation_instruction", "Rule does not mention validation/evidence.")

    errors = sum(1 for item in diagnostics if item["severity"] == "error")
    warnings = sum(1 for item in diagnostics if item["severity"] == "warning")
    infos = sum(1 for item in diagnostics if item["severity"] == "info")
    status = "blocked" if errors else "needs_review" if warnings or diagnostics else "clear"

    return RuleImportDiagnosticReport(
        status=status,
        diagnostics=diagnostics,
        error_count=errors,
        warning_count=warnings,
        info_count=infos,
        risk_flags=list(dict.fromkeys(risk_flags + _as_list(data.get("warnings")))),
        required_actions=list(dict.fromkeys(actions + _as_list(data.get("required_actions")))),
    )


def build_rule_import_conflict_report(candidate: RuleImportCandidate | dict[str, Any], existing_rules: list[dict[str, Any]] | None = None) -> RuleImportConflictReport:
    data = _dump(candidate)
    conflicts: list[dict[str, Any]] = []
    actions: list[str] = []
    title = _text(data.get("title")).lower()
    body = _text(data.get("body_preview")).lower()
    scope = _text(data.get("source_scope"), fallback="project")
    seen_duplicates = 0

    for rule in existing_rules or []:
        if not isinstance(rule, dict):
            continue
        rule_title = _text(rule.get("title") or rule.get("name")).lower()
        rule_body = _text(rule.get("body") or rule.get("content") or rule.get("body_preview")).lower()
        rule_scope = _text(rule.get("scope") or rule.get("source_scope"), fallback="project")
        if title and rule_title and title == rule_title:
            seen_duplicates += 1
            conflicts.append({"severity": "warning", "code": "duplicate_rule_title", "message": "Candidate title duplicates an existing rule.", "scope": scope})
        if body and rule_body and body[:300] == rule_body[:300]:
            seen_duplicates += 1
            conflicts.append({"severity": "warning", "code": "duplicate_rule_body", "message": "Candidate body duplicates an existing rule.", "scope": scope})
        if scope == rule_scope and ("skip approval" in body or "bypass approval" in body):
            conflicts.append({"severity": "error", "code": "approval_bypass_conflict", "message": "Candidate conflicts with approval policy.", "scope": scope})

    if conflicts:
        actions.append("review_rule_conflicts")

    conflict_count = sum(1 for item in conflicts if item.get("severity") == "error")
    status = "blocked" if conflict_count else "needs_review" if conflicts else "clear"

    return RuleImportConflictReport(
        status=status,
        conflicts=conflicts,
        duplicate_count=seen_duplicates,
        conflict_count=conflict_count,
        required_actions=actions,
    )


def build_rule_scope_precedence_decision(candidate: RuleImportCandidate | dict[str, Any]) -> RuleScopePrecedenceDecision:
    data = _dump(candidate)
    source_scope = _text(data.get("source_scope"), fallback="project")
    effective_scope = source_scope if source_scope in SCOPE_PRECEDENCE else "unknown"
    required = []
    if effective_scope == "unknown":
        required.append("confirm_rule_scope")
    required.append("approve_rule_runtime_injection")

    return RuleScopePrecedenceDecision(
        source_scope=source_scope,
        effective_scope=effective_scope,
        precedence_rank=SCOPE_PRECEDENCE.get(effective_scope, 0),
        required_actions=list(dict.fromkeys(required)),
    )


def build_rule_import_injection_gate(
    candidate: RuleImportCandidate | dict[str, Any],
    diagnostics: RuleImportDiagnosticReport | dict[str, Any] | None = None,
    conflicts: RuleImportConflictReport | dict[str, Any] | None = None,
    precedence: RuleScopePrecedenceDecision | dict[str, Any] | None = None,
    *,
    approved: bool = False,
    reviewer: str | None = None,
) -> RuleImportInjectionGate:
    diag = _dump(diagnostics) if diagnostics is not None else _dump(build_rule_import_diagnostic_report(candidate))
    conflict = _dump(conflicts) if conflicts is not None else _dump(build_rule_import_conflict_report(candidate))
    prec = _dump(precedence) if precedence is not None else _dump(build_rule_scope_precedence_decision(candidate))
    blocked = diag.get("status") == "blocked" or conflict.get("status") == "blocked"
    required = list(dict.fromkeys(_as_list(diag.get("required_actions")) + _as_list(conflict.get("required_actions")) + _as_list(prec.get("required_actions"))))

    if blocked:
        status = "blocked"
        allowed = False
        reason = "Rule import blocked by diagnostics or conflicts."
    elif approved:
        status = "approved"
        allowed = True
        reason = "Rule import approved for runtime injection by human reviewer."
    else:
        status = "review_required"
        allowed = False
        reason = "Rule import requires approval before runtime injection."

    return RuleImportInjectionGate(
        status=status,
        injection_allowed=allowed,
        approved=bool(approved and not blocked),
        reviewer=reviewer or "human_required",
        reason=reason,
        required_actions=[] if approved and not blocked else required or ["review_rule_import_candidate"],
    )


def build_project_rules_import_trace_source(
    input_data: dict[str, Any] | None = None,
    *,
    existing_rules: list[dict[str, Any]] | None = None,
    approved: bool = False,
    reviewer: str | None = None,
) -> ProjectRulesImportTraceSource:
    data = dict(input_data or {})
    adapter = build_rule_import_source_adapter(data)
    candidate = build_rule_import_candidate(data, adapter)
    diagnostics = build_rule_import_diagnostic_report(candidate)
    conflicts = build_rule_import_conflict_report(candidate, existing_rules=existing_rules)
    precedence = build_rule_scope_precedence_decision(candidate)
    gate = build_rule_import_injection_gate(candidate, diagnostics, conflicts, precedence, approved=approved, reviewer=reviewer)

    warnings = list(dict.fromkeys(_as_list(adapter.warnings) + _as_list(candidate.warnings)))
    required = list(dict.fromkeys(_as_list(adapter.required_actions) + _as_list(candidate.required_actions) + _as_list(diagnostics.required_actions) + _as_list(conflicts.required_actions) + _as_list(precedence.required_actions) + _as_list(gate.required_actions)))
    blocked = gate.status == "blocked" or diagnostics.status == "blocked" or conflicts.status == "blocked"
    status = "blocked" if blocked else "approved" if gate.approved else "review_required"

    return ProjectRulesImportTraceSource(
        adapter=_dump(adapter),
        candidate=_dump(candidate),
        diagnostics=_dump(diagnostics),
        conflicts=_dump(conflicts),
        precedence=_dump(precedence),
        injection_gate=_dump(gate),
        status=status,
        warnings=warnings,
        required_actions=list(dict.fromkeys(required)),
    )
