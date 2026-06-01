"""Universal import compatibility contracts for safe external resource ingestion.

This module is side-effect-free. It only detects, normalizes, scores and gates
external import sources as reviewable candidates. It never installs, executes,
activates MCP, creates agents, writes memory, calls providers or mutates user files.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from hashlib import sha256
from typing import Any


IMPORT_COMPATIBILITY_RUNTIME_VERSION = "openswarm.import_compatibility_runtime.v1"

IMPORT_FORMATS = {
    "skill",
    "skill_set",
    "tool",
    "mcp_server",
    "agent",
    "subagent",
    "prompt_workflow",
    "command",
    "project_instruction",
    "memory_signal",
    "api_tool",
    "unknown",
}

CANDIDATE_TYPES = {
    "SkillSpecCandidate",
    "SkillSetCandidate",
    "ToolSpecCandidate",
    "MCPServerCandidate",
    "AgentSpecCandidate",
    "SubagentBlueprintCandidate",
    "PromptWorkflowCandidate",
    "CommandSpecCandidate",
    "ProjectInstructionCandidate",
    "MemorySignalCandidate",
    "ApiToolCandidate",
}

FORMAT_TO_CANDIDATE = {
    "skill": "SkillSpecCandidate",
    "skill_set": "SkillSetCandidate",
    "tool": "ToolSpecCandidate",
    "mcp_server": "MCPServerCandidate",
    "agent": "AgentSpecCandidate",
    "subagent": "SubagentBlueprintCandidate",
    "prompt_workflow": "PromptWorkflowCandidate",
    "command": "CommandSpecCandidate",
    "project_instruction": "ProjectInstructionCandidate",
    "memory_signal": "MemorySignalCandidate",
    "api_tool": "ApiToolCandidate",
    "unknown": "PromptWorkflowCandidate",
}

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "private_key",
    "authorization",
    "cookie",
    "env",
}

DANGEROUS_HINTS = {
    "rm -rf",
    "curl | sh",
    "wget | sh",
    "Invoke-WebRequest",
    "iex",
    "bypass approval",
    "skip approval",
    "disable policy",
    "print secrets",
    "exfiltrate",
}

SECRET_HINTS = {
    "api_key=",
    "password=",
    "private_key",
    "BEGIN PRIVATE KEY",
    "authorization:",
    "bearer ",
}


@dataclass(frozen=True)
class ImportSourceDetection:
    source_kind: str = "import_compatibility_runtime"
    detection_kind: str = "import_source_detection"
    detected_format: str = "unknown"
    source_uri: str = "unknown"
    source_hash: str = "unknown"
    confidence: float = 0.0
    files_seen: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    unknown_fields: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_install: bool = False
    can_activate_mcp: bool = False


@dataclass(frozen=True)
class ImportCandidateEnvelope:
    source_kind: str = "import_compatibility_runtime"
    candidate_kind: str = "import_candidate_envelope"
    normalized_type: str = "PromptWorkflowCandidate"
    normalized_candidate: dict[str, Any] = field(default_factory=dict)
    source_detection: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    source_uri: str = "unknown"
    source_hash: str = "unknown"
    source_author: str = "unknown"
    source_license: str = "unknown"
    detected_format: str = "unknown"
    confidence: float = 0.0
    unknown_fields: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_install: bool = False
    can_activate_mcp: bool = False
    can_create_agent: bool = False
    can_write_memory: bool = False


@dataclass(frozen=True)
class ImportCompatibilityReport:
    source_kind: str = "import_compatibility_runtime"
    score_kind: str = "import_compatibility_score"
    overall_score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    format_validity: float = 0.0
    metadata_quality: float = 0.0
    provenance_quality: float = 0.0
    permission_clarity: float = 0.0
    validation_quality: float = 0.0
    evidence_quality: float = 0.0
    safety_quality: float = 0.0
    compatibility_level: str = "unsupported"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_install: bool = False


@dataclass(frozen=True)
class ImportPolicyBridgeDecision:
    source_kind: str = "import_compatibility_runtime"
    decision_kind: str = "import_policy_bridge_decision"
    decision: str = "needs_review"
    policy_matrix_required: bool = True
    skill_harness_required: bool = False
    shell_dialect_required: bool = False
    safeshell_required: bool = False
    secret_visibility_required: bool = True
    mcp_activation_guard_required: bool = False
    external_provider_gate_required: bool = False
    memory_write_gate_required: bool = False
    risk_level: str = "medium"
    risk_flags: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_install: bool = False
    can_activate_mcp: bool = False
    can_create_agent: bool = False
    can_write_memory: bool = False


def dump_import_compatibility(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dataclass_fields__"):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return _safe(dict(value))
    return {"source_kind": "import_compatibility_runtime", "value": _text(value, limit=200)}


def _text(value: Any, fallback: str = "", *, limit: int = 800) -> str:
    if value is None:
        return fallback
    result = str(value).strip()
    if not result:
        return fallback
    return result[:limit]


def _as_list(value: Any, *, limit: int = 80) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]
    result: list[str] = []
    for item in raw:
        text = _text(item, limit=240)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _safe(value: Any) -> Any:
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
        return [_safe(item) for item in value[:80]]
    if isinstance(value, tuple):
        return [_safe(item) for item in list(value)[:80]]
    if isinstance(value, str):
        lowered = value.lower()
        if any(hint.lower() in lowered for hint in SECRET_HINTS):
            return "[redacted]"
        return value[:2000]
    return value


def _hash_text(text: str) -> str:
    if not text:
        return "unknown"
    return sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _collect_files(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        return []
    files: list[dict[str, Any]] = []
    for item in raw_files[:200]:
        if isinstance(item, dict):
            name = _text(item.get("path") or item.get("name"), limit=240)
            content = _text(item.get("content"), limit=4000)
            files.append({"name": name, "content": content})
        else:
            files.append({"name": _text(item, limit=240), "content": ""})
    return files


def _joined_payload_text(payload: dict[str, Any], files: list[dict[str, Any]]) -> str:
    parts = [
        _text(payload.get("raw_text"), limit=8000),
        _text(payload.get("content"), limit=8000),
        _text(payload.get("description"), limit=2000),
        _text(payload.get("source_format"), limit=200),
        _text(payload.get("detected_format"), limit=200),
    ]
    for file in files:
        parts.append(_text(file.get("name"), limit=240))
        parts.append(_text(file.get("content"), limit=4000))
    return "\n".join(part for part in parts if part)


def _risk_flags_from_text(text: str, payload: dict[str, Any]) -> list[str]:
    lowered = text.lower()
    risks: list[str] = []
    if any(hint.lower() in lowered for hint in DANGEROUS_HINTS):
        risks.append("dangerous_execution_or_bypass_instruction")
    if any(hint.lower() in lowered for hint in SECRET_HINTS):
        risks.append("possible_secret_material")
    if payload.get("required_tools"):
        risks.append("required_tools_declared")
    if payload.get("required_mcp_servers") or "mcpserver" in lowered or "mcp server" in lowered:
        risks.append("required_mcp_servers_declared")
    if "script" in lowered or "shell" in lowered or "bash" in lowered or "powershell" in lowered:
        risks.append("executable_hint_present")
    return list(dict.fromkeys(risks))


def _detect_format(payload: dict[str, Any], files: list[dict[str, Any]], text: str) -> tuple[str, float, list[str]]:
    explicit = _text(payload.get("detected_format") or payload.get("source_format") or payload.get("format"), limit=200).lower().replace("-", "_")
    if explicit in IMPORT_FORMATS:
        return explicit, 0.9, ["explicit_format"]

    names = [str(file.get("name") or "").replace("\\", "/").lower() for file in files]
    lowered = text.lower()

    if any(name.endswith("skill.md") for name in names) or "skill.md" in lowered or "claude skill" in lowered:
        return "skill", 0.86, ["skill_entrypoint"]
    if any(name.endswith("agents.md") for name in names) or "agents.md" in lowered:
        return "project_instruction", 0.82, ["agents_md"]
    if any(name.endswith(".github/copilot-instructions.md") for name in names) or "copilot-instructions" in lowered:
        return "project_instruction", 0.82, ["copilot_instructions"]
    if "windsurf" in lowered or "cursor rule" in lowered or ".windsurfrules" in lowered or ".cursorrules" in lowered:
        return "project_instruction", 0.74, ["editor_rule"]
    if "mcpservers" in lowered or "mcp server" in lowered or '"mcp"' in lowered or "required_mcp_servers" in lowered:
        return "mcp_server", 0.78, ["mcp_config_like"]
    if "openapi" in lowered or "swagger" in lowered or "api docs" in lowered:
        return "api_tool", 0.72, ["api_docs_like"]
    if "agent spec" in lowered or '"agent"' in lowered or "handoff" in lowered:
        return "agent", 0.68, ["agent_spec_like"]
    if "subagent" in lowered or "specialist" in lowered:
        return "subagent", 0.66, ["subagent_like"]
    if "slash command" in lowered or "opencode command" in lowered or "/init" in lowered:
        return "command", 0.66, ["command_like"]
    if "prompt" in lowered or "workflow" in lowered:
        return "prompt_workflow", 0.52, ["prompt_workflow_like"]
    return "unknown", 0.12, []


def detect_import_source(payload: dict[str, Any] | None = None, **kwargs: Any) -> ImportSourceDetection:
    data = dict(payload or {})
    data.update({key: value for key, value in kwargs.items() if value is not None})
    files = _collect_files(data)
    text = _joined_payload_text(data, files)
    detected_format, confidence, entrypoints = _detect_format(data, files, text)
    risk_flags = _risk_flags_from_text(text, data)
    required_actions: list[str] = []
    if detected_format == "unknown":
        required_actions.append("review_unknown_import_format")
    if "possible_secret_material" in risk_flags:
        required_actions.append("remove_or_redact_secret_material")
    if "dangerous_execution_or_bypass_instruction" in risk_flags:
        required_actions.append("remove_dangerous_or_bypass_instructions")
    if "required_tools_declared" in risk_flags:
        required_actions.append("review_required_tools_policy")
    if "required_mcp_servers_declared" in risk_flags:
        required_actions.append("review_required_mcp_servers_policy")

    source_uri = _text(data.get("source_uri") or data.get("source_url"), fallback="unknown", limit=500)
    source_hash = _text(data.get("source_hash"), fallback="", limit=160) or _hash_text(text)

    known = {
        "files", "raw_text", "content", "description", "source_format", "detected_format", "format",
        "source_uri", "source_url", "source_hash", "source_author", "source_license",
        "required_tools", "required_mcp_servers", "metadata", "provenance", "name",
    }
    unknown_fields = sorted(str(key) for key in data.keys() if key not in known)[:80]

    return ImportSourceDetection(
        detected_format=detected_format,
        source_uri=source_uri,
        source_hash=source_hash,
        confidence=round(max(0.0, min(1.0, confidence)), 3),
        files_seen=[str(file.get("name") or "") for file in files if file.get("name")][:80],
        entrypoints=entrypoints,
        unknown_fields=unknown_fields,
        risk_flags=risk_flags,
        required_actions=required_actions,
    )


def _candidate_type_for_format(detected_format: str) -> str:
    return FORMAT_TO_CANDIDATE.get(detected_format, "PromptWorkflowCandidate")


def normalize_import_candidate(payload: dict[str, Any] | None = None, *, detection: ImportSourceDetection | dict[str, Any] | None = None, **kwargs: Any) -> ImportCandidateEnvelope:
    data = dict(payload or {})
    data.update({key: value for key, value in kwargs.items() if value is not None})

    if detection is None:
        detection_obj = detect_import_source(data)
        detection_data = asdict(detection_obj)
    elif hasattr(detection, "__dataclass_fields__"):
        detection_data = asdict(detection)  # type: ignore[arg-type]
    else:
        detection_data = dict(detection or {})

    detected_format = _text(detection_data.get("detected_format"), fallback="unknown")
    normalized_type = _candidate_type_for_format(detected_format)
    source_uri = _text(detection_data.get("source_uri") or data.get("source_uri"), fallback="unknown", limit=500)
    source_hash = _text(detection_data.get("source_hash") or data.get("source_hash"), fallback="unknown", limit=160)
    provenance_input = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
    source_author = _text(data.get("source_author") or provenance_input.get("source_author") or provenance_input.get("author"), fallback="unknown", limit=240)
    source_license = _text(data.get("source_license") or provenance_input.get("source_license") or provenance_input.get("license"), fallback="unknown", limit=120)

    risk_flags = list(dict.fromkeys(_as_list(detection_data.get("risk_flags")) + _as_list(data.get("risk_flags"))))
    required_actions = list(dict.fromkeys(_as_list(detection_data.get("required_actions")) + _as_list(data.get("required_actions"))))

    provenance = _safe({
        **provenance_input,
        "source_uri": source_uri,
        "source_hash": source_hash,
        "source_author": source_author,
        "source_license": source_license,
        "detected_format": detected_format,
        "confidence": detection_data.get("confidence", 0.0),
    })

    normalized_candidate = _safe({
        "candidate_type": normalized_type,
        "name": _text(data.get("name"), fallback=f"Imported {detected_format}", limit=180),
        "detected_format": detected_format,
        "summary": _text(data.get("description") or data.get("summary"), fallback="External import candidate pending review.", limit=500),
        "required_tools": _as_list(data.get("required_tools")),
        "required_mcp_servers": _as_list(data.get("required_mcp_servers")),
        "provenance": provenance,
    })

    return ImportCandidateEnvelope(
        normalized_type=normalized_type,
        normalized_candidate=normalized_candidate,
        source_detection=_safe(detection_data),
        provenance=provenance,
        source_uri=source_uri,
        source_hash=source_hash,
        source_author=source_author,
        source_license=source_license,
        detected_format=detected_format,
        confidence=float(detection_data.get("confidence") or 0.0),
        unknown_fields=_as_list(detection_data.get("unknown_fields")),
        risk_flags=risk_flags,
        required_actions=required_actions,
    )


def _score(value: bool) -> float:
    return 1.0 if value else 0.0


def build_import_compatibility_report(envelope: ImportCandidateEnvelope | dict[str, Any]) -> ImportCompatibilityReport:
    data = asdict(envelope) if hasattr(envelope, "__dataclass_fields__") else dict(envelope or {})
    detected_format = _text(data.get("detected_format"), fallback="unknown")
    risk_flags = _as_list(data.get("risk_flags"))
    required_actions = _as_list(data.get("required_actions"))

    source_author = _text(data.get("source_author"), fallback="unknown")
    source_license = _text(data.get("source_license"), fallback="unknown")
    source_uri = _text(data.get("source_uri"), fallback="unknown")
    source_hash = _text(data.get("source_hash"), fallback="unknown")

    format_validity = _score(detected_format in IMPORT_FORMATS and detected_format != "unknown")
    provenance_quality = (
        _score(source_author != "unknown")
        + _score(source_license != "unknown")
        + _score(source_uri != "unknown")
        + _score(source_hash != "unknown")
    ) / 4.0
    metadata_quality = (_score(bool(data.get("normalized_candidate"))) + _score(bool(data.get("normalized_type")))) / 2.0
    permission_clarity = 0.4 if any(flag in risk_flags for flag in {"required_tools_declared", "required_mcp_servers_declared"}) else 1.0
    validation_quality = 0.5 if "missing_validation_plan" in risk_flags else 0.75
    evidence_quality = 0.5 if "missing_evidence_contract" in risk_flags else 0.75
    safety_quality = 0.0 if any(flag in risk_flags for flag in {"possible_secret_material", "dangerous_execution_or_bypass_instruction"}) else 0.65 if "executable_hint_present" in risk_flags else 1.0

    components = {
        "format_validity": round(format_validity, 3),
        "metadata_quality": round(metadata_quality, 3),
        "provenance_quality": round(provenance_quality, 3),
        "permission_clarity": round(permission_clarity, 3),
        "validation_quality": round(validation_quality, 3),
        "evidence_quality": round(evidence_quality, 3),
        "safety_quality": round(safety_quality, 3),
    }
    overall = round(sum(components.values()) / len(components), 3)

    # Missing provenance is a review blocker for imports even when the format is
    # recognizable. Keep the score conservative so unknown author/license/source
    # metadata cannot look production-ready.
    missing_provenance_fields = [
        source_author == "unknown",
        source_license == "unknown",
        source_uri == "unknown",
        source_hash == "unknown",
    ]
    if any(missing_provenance_fields):
        overall = min(overall, 0.79)

    blockers: list[str] = []
    warnings: list[str] = []
    if detected_format == "unknown":
        warnings.append("unknown_source_format")
        required_actions.append("review_unknown_import_format")
    if source_author == "unknown":
        warnings.append("source_author_unknown")
        required_actions.append("confirm_source_author")
    if source_license == "unknown":
        warnings.append("source_license_unknown")
        required_actions.append("confirm_source_license")
    if source_hash == "unknown":
        warnings.append("source_hash_unknown")
        required_actions.append("confirm_source_hash")
    if "required_tools_declared" in risk_flags:
        warnings.append("required_tools_need_policy_review")
        required_actions.append("review_required_tools_policy")
    if "required_mcp_servers_declared" in risk_flags:
        warnings.append("required_mcp_servers_need_policy_review")
        required_actions.append("review_required_mcp_servers_policy")
    if "possible_secret_material" in risk_flags:
        blockers.append("possible_secret_material")
        required_actions.append("remove_or_redact_secret_material")
    if "dangerous_execution_or_bypass_instruction" in risk_flags:
        blockers.append("dangerous_execution_or_bypass_instruction")
        required_actions.append("remove_dangerous_or_bypass_instructions")

    if blockers:
        level = "blocked"
    elif detected_format == "unknown" or warnings or overall < 0.7:
        level = "needs_review"
    else:
        level = "compatible"

    return ImportCompatibilityReport(
        overall_score=overall,
        components=components,
        format_validity=components["format_validity"],
        metadata_quality=components["metadata_quality"],
        provenance_quality=components["provenance_quality"],
        permission_clarity=components["permission_clarity"],
        validation_quality=components["validation_quality"],
        evidence_quality=components["evidence_quality"],
        safety_quality=components["safety_quality"],
        compatibility_level=level,
        blockers=list(dict.fromkeys(blockers)),
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(required_actions)),
    )


def evaluate_import_policy_bridge(
    envelope: ImportCandidateEnvelope | dict[str, Any],
    compatibility: ImportCompatibilityReport | dict[str, Any] | None = None,
) -> ImportPolicyBridgeDecision:
    data = asdict(envelope) if hasattr(envelope, "__dataclass_fields__") else dict(envelope or {})
    report = (
        asdict(compatibility)
        if hasattr(compatibility, "__dataclass_fields__")
        else dict(compatibility or asdict(build_import_compatibility_report(data)))
    )

    detected_format = _text(data.get("detected_format"), fallback="unknown")
    normalized_type = _text(data.get("normalized_type"), fallback="PromptWorkflowCandidate")
    risk_flags = list(dict.fromkeys(_as_list(data.get("risk_flags")) + _as_list(report.get("blockers"))))
    blockers = _as_list(report.get("blockers"))
    required_actions = list(dict.fromkeys(_as_list(data.get("required_actions")) + _as_list(report.get("required_actions"))))

    shell_required = detected_format in {"command", "tool"} or "executable_hint_present" in risk_flags
    mcp_required = detected_format == "mcp_server" or "required_mcp_servers_declared" in risk_flags
    memory_required = detected_format == "memory_signal"
    agent_required = detected_format in {"agent", "subagent"}

    if blockers:
        decision = "blocked"
        risk_level = "critical"
    elif detected_format == "unknown":
        decision = "unsupported"
        risk_level = "medium"
        required_actions.append("select_supported_import_adapter")
    elif detected_format in {"tool", "mcp_server", "agent", "subagent", "command", "api_tool"}:
        decision = "needs_review"
        risk_level = "high"
        required_actions.append("request_import_review")
    elif report.get("compatibility_level") == "compatible":
        decision = "safe_to_preview"
        risk_level = "low"
    else:
        decision = "needs_review"
        risk_level = "medium"
        required_actions.append("request_import_review")

    if normalized_type == "SkillSpecCandidate":
        skill_harness_required = True
    else:
        skill_harness_required = False

    return ImportPolicyBridgeDecision(
        decision=decision,
        skill_harness_required=skill_harness_required,
        shell_dialect_required=shell_required,
        safeshell_required=shell_required,
        secret_visibility_required=True,
        mcp_activation_guard_required=mcp_required,
        external_provider_gate_required=detected_format == "api_tool",
        memory_write_gate_required=memory_required,
        risk_level=risk_level,
        risk_flags=risk_flags,
        blockers=blockers,
        required_actions=list(dict.fromkeys(required_actions)),
    )
