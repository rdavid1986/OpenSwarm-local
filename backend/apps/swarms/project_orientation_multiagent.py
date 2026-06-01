"""Side-effect-free multiagent project orientation contracts.

Contracts in this module classify a project request and prepare orientation
plans before any agent creation, tool execution, terminal use, file writes, or
external provider calls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

ORIENTATION_VERSION = "openswarm.project_orientation_multiagent.v1"
PROJECT_TYPES = {"app", "web", "skill", "automation", "research", "game", "plugin", "mcp", "data_pipeline", "unknown"}
COMPLEXITY_LEVELS = {"low", "medium", "high", "critical", "unknown"}
ARCHITECTURE_PATTERNS = {
    "single_agent",
    "supervisor_workers",
    "dag",
    "sequential_pipeline",
    "parallel_specialists",
    "swarm_collaboration",
    "human_in_the_loop",
    "tool_first_workflow",
    "hybrid",
}
SENSITIVE_MARKERS = {
    "api_key",
    "apikey",
    "authorization",
    "chain_of_thought",
    "cookie",
    "credential",
    "password",
    "private_key",
    "private_reasoning",
    "raw_prompt",
    "secret",
    "token",
}


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


def _contains_sensitive(value: Any) -> bool:
    lowered = _text(value, limit=2000).lower().replace("-", "_")
    return any(marker in lowered for marker in SENSITIVE_MARKERS)


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _safe_metadata(value)
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:50]]
    if isinstance(value, bool) or isinstance(value, int | float) or value is None:
        return value
    text = _text(value, limit=320)
    return "[redacted]" if _contains_sensitive(text) else text


def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, raw in value.items():
        key_text = _text(key, limit=120)
        if _contains_sensitive(key_text):
            safe[key_text] = "[redacted]"
        else:
            safe[key_text] = _safe_value(raw)
    return safe


def dump_project_orientation(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return _safe_metadata(value)
    return {}


def _level(value: Any, allowed: set[str], fallback: str = "unknown") -> str:
    text = _text(value, fallback).lower().replace(" ", "_").replace("-", "_")
    return text if text in allowed else fallback


@dataclass(frozen=True)
class ProjectOrientationClassification:
    source_kind: str = "project_orientation_classification"
    orientation_kind: str = "project_orientation_classification"
    orientation_version: str = ORIENTATION_VERSION
    project_type: str = "unknown"
    complexity: str = "unknown"
    uncertainty: str = "medium"
    sensitive_data_risk: str = "unknown"
    required_tools: list[str] = field(default_factory=list)
    required_outputs: list[str] = field(default_factory=list)
    autonomy_level: str = "review_required"
    single_agent_ok: bool = True
    multiagent_required: bool = False
    workflow_required: bool = False
    human_review_required: bool = True
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectArchitecturePatternDecision:
    source_kind: str = "project_orientation_architecture"
    decision_kind: str = "project_orientation_architecture"
    orientation_version: str = ORIENTATION_VERSION
    selected_pattern: str = "single_agent"
    rejected_patterns: list[str] = field(default_factory=list)
    rationale_summary: str = ""
    risk_level: str = "medium"
    cost_level: str = "low"
    evidence_required: bool = True
    approval_required: bool = True
    can_execute: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectAgentRoleBlueprint:
    role_kind: str = "project_agent_role_blueprint"
    role_id: str = "generalist"
    responsibilities: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    tools_allowed: list[str] = field(default_factory=list)
    memory_access: str = "read_only"
    validation_responsibility: str = "self_check"
    stop_conditions: list[str] = field(default_factory=list)
    can_execute: bool = False


@dataclass(frozen=True)
class ProjectHandoffBlueprint:
    handoff_kind: str = "project_handoff_blueprint"
    from_role: str = ""
    to_role: str = ""
    handoff_payload_schema: dict[str, Any] = field(default_factory=dict)
    shared_context: list[str] = field(default_factory=list)
    private_context_allowed: bool = False
    stop_conditions: list[str] = field(default_factory=list)
    can_execute: bool = False


@dataclass(frozen=True)
class ProjectAgentBlueprintSet:
    source_kind: str = "project_orientation_agent_blueprint"
    blueprint_kind: str = "project_orientation_agent_blueprint"
    orientation_version: str = ORIENTATION_VERSION
    roles: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[dict[str, Any]] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    can_execute: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectPermissionMap:
    source_kind: str = "project_orientation_permission_map"
    permission_kind: str = "project_orientation_permission_map"
    orientation_version: str = ORIENTATION_VERSION
    tools_required: list[str] = field(default_factory=list)
    mcp_required: list[str] = field(default_factory=list)
    terminal_required: bool = False
    safeshell_required: bool = False
    shell_dialect_required: bool = False
    browser_required: bool = False
    web_research_required: bool = False
    file_write_allowed: bool = False
    external_provider_allowed: bool = False
    user_approval_points: list[str] = field(default_factory=list)
    policy_matrix_required: bool = True
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectMemoryContextPlan:
    source_kind: str = "project_orientation_memory_context"
    memory_kind: str = "project_orientation_memory_context"
    orientation_version: str = ORIENTATION_VERSION
    project_instructions_required: bool = True
    relevant_docs: list[str] = field(default_factory=list)
    memory_tiers: list[str] = field(default_factory=list)
    context_budget: dict[str, Any] = field(default_factory=dict)
    freshness_policy: str = "verify_recent_context"
    compaction_policy: str = "preserve_evidence"
    evidence_refs: list[str] = field(default_factory=list)
    allowed_memory_writes: list[str] = field(default_factory=list)
    blocked_memory_writes: list[str] = field(default_factory=list)
    human_review_points: list[str] = field(default_factory=list)
    can_mutate_memory: bool = False
    can_execute: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectOutputValidationPlan:
    source_kind: str = "project_orientation_output_validation"
    validation_kind: str = "project_orientation_output_validation"
    orientation_version: str = ORIENTATION_VERSION
    expected_outputs: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    tests_required: list[str] = field(default_factory=list)
    minimum_evidence: list[str] = field(default_factory=list)
    validation_strategy: list[str] = field(default_factory=list)
    rollback_required: bool = False
    diff_preview_required: bool = True
    acceptance_criteria: list[str] = field(default_factory=list)
    completion_gate: str = "human_review"
    can_write_files: bool = False
    can_execute: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectModelProviderPlan:
    source_kind: str = "project_orientation_model_provider"
    model_provider_kind: str = "project_orientation_model_provider"
    orientation_version: str = ORIENTATION_VERSION
    recommended_local_model: str = "ollama/local"
    model_by_agent: dict[str, str] = field(default_factory=dict)
    context_window_required: int | None = None
    reasoning_level: str = "medium"
    external_fallback_allowed: bool = False
    openrouter_allowed: bool = False
    budget_cap: float | None = None
    latency_expectation: str = "interactive"
    provider_health_required: bool = True
    local_first: bool = True
    can_call_external_provider: bool = False
    can_execute: bool = False
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def classify_project_orientation(
    *,
    project_type: str = "unknown",
    complexity: str = "unknown",
    uncertainty: str = "medium",
    sensitive_data_risk: str = "unknown",
    required_tools: list[Any] | None = None,
    required_outputs: list[Any] | None = None,
    autonomy_level: str = "review_required",
    metadata: dict[str, Any] | None = None,
) -> ProjectOrientationClassification:
    ptype = _level(project_type, PROJECT_TYPES)
    cplx = _level(complexity, COMPLEXITY_LEVELS)
    tools = _dedupe(_as_list(required_tools))
    outputs = _dedupe(_as_list(required_outputs))
    blockers: list[str] = []
    actions = ["review_project_orientation", "do_not_create_agents_yet"]
    multi = cplx in {"high", "critical"} or len(outputs) > 2 or len(tools) > 3
    workflow = multi or ptype in {"automation", "data_pipeline", "mcp"}
    if ptype == "unknown":
        blockers.append("project_type_unknown")
        actions.append("clarify_project_type")
    if cplx == "unknown":
        actions.append("estimate_project_complexity")
    if sensitive_data_risk in {"high", "critical"}:
        actions.append("require_privacy_review")
    return ProjectOrientationClassification(
        project_type=ptype,
        complexity=cplx,
        uncertainty=_level(uncertainty, {"low", "medium", "high", "unknown"}, "medium"),
        sensitive_data_risk=_level(sensitive_data_risk, {"low", "medium", "high", "critical", "unknown"}),
        required_tools=tools,
        required_outputs=outputs,
        autonomy_level=_text(autonomy_level, "review_required"),
        single_agent_ok=not multi,
        multiagent_required=multi,
        workflow_required=workflow,
        human_review_required=True,
        blockers=_dedupe(blockers),
        required_actions=_dedupe(actions),
        metadata=_safe_metadata(metadata),
    )


def select_project_architecture_pattern(classification: ProjectOrientationClassification | dict[str, Any]) -> ProjectArchitecturePatternDecision:
    data = dump_project_orientation(classification)
    multi = bool(data.get("multiagent_required"))
    workflow = bool(data.get("workflow_required"))
    complexity = _text(data.get("complexity"), "unknown")
    if not multi and not workflow:
        selected = "single_agent"
        rationale = "Single agent is sufficient because complexity and workflow requirements are low."
    elif multi and len(data.get("required_outputs") or []) > 2:
        selected = "parallel_specialists"
        rationale = "Multiple outputs and high complexity benefit from specialist roles."
    elif workflow:
        selected = "sequential_pipeline"
        rationale = "Workflow requirement benefits from staged handoffs."
    else:
        selected = "supervisor_workers"
        rationale = "Multiagent coordination requires supervision."
    rejected = sorted(ARCHITECTURE_PATTERNS - {selected})
    return ProjectArchitecturePatternDecision(
        selected_pattern=selected,
        rejected_patterns=rejected,
        rationale_summary=rationale,
        risk_level="high" if complexity in {"high", "critical"} else "medium" if workflow else "low",
        cost_level="high" if multi else "low",
        evidence_required=True,
        approval_required=True,
        metadata={"classification_kind": data.get("orientation_kind")},
    )


def build_project_agent_blueprint_set(
    roles: list[dict[str, Any]] | None = None,
    handoffs: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProjectAgentBlueprintSet:
    if not roles:
        roles = [{"role_id": "generalist", "responsibilities": ["plan", "implement", "validate"]}]
    role_contracts = []
    for role in roles:
        role_contracts.append(asdict(ProjectAgentRoleBlueprint(
            role_id=_text(role.get("role_id"), "generalist"),
            responsibilities=_dedupe(_as_list(role.get("responsibilities"))),
            boundaries=_dedupe(_as_list(role.get("boundaries") or ["no_private_reasoning", "no_unapproved_tools"])),
            inputs=_dedupe(_as_list(role.get("inputs"))),
            outputs=_dedupe(_as_list(role.get("outputs"))),
            tools_allowed=_dedupe(_as_list(role.get("tools_allowed"))),
            memory_access=_text(role.get("memory_access"), "read_only"),
            validation_responsibility=_text(role.get("validation_responsibility"), "self_check"),
            stop_conditions=_dedupe(_as_list(role.get("stop_conditions") or ["blocked_without_user_input", "validation_failed"])),
        )))
    handoff_contracts = []
    for handoff in handoffs or []:
        handoff_contracts.append(asdict(ProjectHandoffBlueprint(
            from_role=_text(handoff.get("from_role")),
            to_role=_text(handoff.get("to_role")),
            handoff_payload_schema=_safe_metadata(handoff.get("handoff_payload_schema") if isinstance(handoff.get("handoff_payload_schema"), dict) else {"summary": "string", "evidence_refs": "list"}),
            shared_context=_dedupe(_as_list(handoff.get("shared_context"))),
            private_context_allowed=False,
            stop_conditions=_dedupe(_as_list(handoff.get("stop_conditions") or ["missing_evidence", "approval_required"])),
        )))
    return ProjectAgentBlueprintSet(
        roles=role_contracts,
        handoffs=handoff_contracts,
        boundaries=["no_tool_execution", "no_terminal_activation", "no_private_reasoning_transfer"],
        metadata=_safe_metadata(metadata),
    )


def build_project_permission_map(
    *,
    tools_required: list[Any] | None = None,
    mcp_required: list[Any] | None = None,
    terminal_required: bool = False,
    browser_required: bool = False,
    web_research_required: bool = False,
    file_write_allowed: bool = False,
    external_provider_allowed: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ProjectPermissionMap:
    actions = ["require_policy_matrix_review"]
    safeshell = bool(terminal_required)
    shell_dialect = bool(terminal_required)
    if terminal_required:
        actions.extend(["require_safeshell_gate", "require_shell_dialect_gate", "block_terminal_until_approved"])
    if file_write_allowed:
        actions.append("require_diff_preview_before_file_write")
    if external_provider_allowed:
        actions.append("require_external_provider_privacy_budget_approval")
    return ProjectPermissionMap(
        tools_required=_dedupe(_as_list(tools_required)),
        mcp_required=_dedupe(_as_list(mcp_required)),
        terminal_required=bool(terminal_required),
        safeshell_required=safeshell,
        shell_dialect_required=shell_dialect,
        browser_required=bool(browser_required),
        web_research_required=bool(web_research_required),
        file_write_allowed=bool(file_write_allowed),
        external_provider_allowed=bool(external_provider_allowed),
        user_approval_points=_dedupe(actions),
        required_actions=_dedupe(actions),
        metadata=_safe_metadata(metadata),
    )


def build_project_memory_context_plan(
    *,
    relevant_docs: list[Any] | None = None,
    evidence_refs: list[Any] | None = None,
    allowed_memory_writes: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProjectMemoryContextPlan:
    allowed = _dedupe(_as_list(allowed_memory_writes))
    return ProjectMemoryContextPlan(
        relevant_docs=_dedupe(_as_list(relevant_docs)),
        memory_tiers=["project_instructions", "recent_memory", "evidence_refs"],
        context_budget={"status": "planned", "can_expand_context": False},
        evidence_refs=_dedupe(_as_list(evidence_refs)),
        allowed_memory_writes=allowed,
        blocked_memory_writes=["raw_prompts", "chain_of_thought", "secrets", "unreviewed_personal_data"],
        human_review_points=["before_persistent_memory_write"],
        metadata=_safe_metadata(metadata),
    )


def build_project_output_validation_plan(
    *,
    expected_outputs: list[Any] | None = None,
    artifacts: list[Any] | None = None,
    tests_required: list[Any] | None = None,
    minimum_evidence: list[Any] | None = None,
    rollback_required: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ProjectOutputValidationPlan:
    evidence = _dedupe(_as_list(minimum_evidence) or ["tests_or_typecheck", "diff_summary", "explicit_acceptance_check"])
    return ProjectOutputValidationPlan(
        expected_outputs=_dedupe(_as_list(expected_outputs)),
        artifacts=_dedupe(_as_list(artifacts)),
        tests_required=_dedupe(_as_list(tests_required)),
        minimum_evidence=evidence,
        validation_strategy=["side_effect_free_plan_review", "run_requested_validations_only", "summarize_evidence"],
        rollback_required=bool(rollback_required),
        diff_preview_required=True,
        acceptance_criteria=["outputs_match_request", "no_unapproved_side_effects", "evidence_attached"],
        completion_gate="evidence_and_human_review",
        metadata=_safe_metadata(metadata),
    )


def build_project_model_provider_plan(
    *,
    recommended_local_model: str = "ollama/local",
    model_by_agent: dict[str, str] | None = None,
    context_window_required: int | None = None,
    reasoning_level: str = "medium",
    external_fallback_allowed: bool = False,
    openrouter_allowed: bool = False,
    budget_cap: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProjectModelProviderPlan:
    actions = ["prefer_local_model", "check_provider_health_before_use"]
    if external_fallback_allowed or openrouter_allowed:
        actions.append("require_external_provider_privacy_budget_approval")
    return ProjectModelProviderPlan(
        recommended_local_model=_text(recommended_local_model, "ollama/local"),
        model_by_agent=_safe_metadata(model_by_agent or {}),
        context_window_required=context_window_required,
        reasoning_level=_text(reasoning_level, "medium"),
        external_fallback_allowed=bool(external_fallback_allowed),
        openrouter_allowed=bool(openrouter_allowed),
        budget_cap=budget_cap,
        provider_health_required=True,
        local_first=True,
        can_call_external_provider=False,
        required_actions=_dedupe(actions),
        metadata=_safe_metadata(metadata),
    )
