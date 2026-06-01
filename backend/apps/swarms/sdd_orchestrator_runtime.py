"""Spec-Driven Development orchestrator contracts.

Side-effect-free SDD contracts for the OpenSwarm multi-agent flow:
Explorer -> Proposer -> SpecWriter -> Designer -> TaskPlanner ->
RiskPolicyReviewer -> TestStrategist.

This module never writes files, executes commands, creates AgentContracts,
creates MiniAgents, executes handoffs, activates tools/MCP, or writes memory.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from hashlib import sha256
import re
from typing import Any


SDD_ORCHESTRATOR_VERSION = "openswarm.sdd_orchestrator.v1"

EXCLUDED_PATH_PARTS = {
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
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
    "chain_of_thought",
}


def _text(value: Any, fallback: str = "", *, limit: int = 1000) -> str:
    if value is None:
        return fallback
    result = str(value).strip()
    if not result:
        return fallback
    return result[:limit]


def _as_list(value: Any, *, limit: int = 120) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    for item in raw:
        text = _text(item, limit=400)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _dedupe(values: list[Any], *, limit: int = 120) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value, limit=400)
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
        if any(hint in lowered for hint in {"api_key=", "password=", "bearer ", "begin private key"}):
            return "[redacted]"
        return value[:3000]
    return value


def _slug(value: Any, fallback: str = "item") -> str:
    text = _text(value, fallback, limit=160).lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _hash_payload(value: Any) -> str:
    raw = repr(_safe(value))
    return sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _path_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    return not any(part in EXCLUDED_PATH_PARTS for part in parts)


def _base_required_actions(*values: list[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        items.extend(_as_list(value))
    return _dedupe(items)


@dataclass(frozen=True)
class SddRoleManifest:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_role_manifest"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    role_order: list[str] = field(default_factory=list)
    roles: list[dict[str, Any]] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    policy_matrix_required: bool = True
    can_execute: bool = False
    can_write_files: bool = False
    can_create_agent: bool = False
    can_create_miniagent: bool = False
    can_activate_tools: bool = False
    can_execute_handoffs: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddExplorerContext:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_explorer_context"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    files_considered: list[str] = field(default_factory=list)
    excluded_files: list[str] = field(default_factory=list)
    symbols_considered: list[str] = field(default_factory=list)
    architecture_refs: list[str] = field(default_factory=list)
    current_behavior_summary: str = ""
    uncertainty: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    context_budget_required: bool = True
    can_execute: bool = False
    can_write_files: bool = False
    can_activate_tools: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddProposal:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_proposal"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    proposed_change: str = ""
    user_value: str = ""
    technical_value: str = ""
    scope: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    approval_required: bool = True
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_activate_tools: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddSpecContract:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_spec_contract"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    spec_id: str = "sdd-spec"
    spec_hash: str = "unknown"
    requirements: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    non_functional_requirements: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    spec_version: str = "draft"
    required_actions: list[str] = field(default_factory=list)
    verifiable: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddDesignContract:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_design_contract"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    affected_subsystems: list[str] = field(default_factory=list)
    new_contracts: list[str] = field(default_factory=list)
    data_flow: list[str] = field(default_factory=list)
    policy_gates: list[str] = field(default_factory=list)
    rollback_plan: list[str] = field(default_factory=list)
    compatibility_notes: list[str] = field(default_factory=list)
    process_trace_requirements: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    approval_required: bool = True
    can_execute: bool = False
    can_write_files: bool = False
    can_activate_tools: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddTaskDagContract:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_task_dag_contract"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    task_nodes: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    assigned_roles: dict[str, str] = field(default_factory=dict)
    required_tools: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    validation_plan: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    dag_ready: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_activate_tools: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddPolicyReviewContract:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_policy_review_contract"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    risk_level: str = "medium"
    policy_matrix_refs: list[str] = field(default_factory=list)
    required_approvals: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    secret_visibility_check: str = "required"
    scope_guard: dict[str, Any] = field(default_factory=dict)
    decision: str = "requires_approval"
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddTestStrategyContract:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_test_strategy_contract"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    test_strategy: str = "review_required"
    test_list: list[str] = field(default_factory=list)
    regression_scope: list[str] = field(default_factory=list)
    red_phase_candidates: list[str] = field(default_factory=list)
    hidden_or_reserved_checks: list[str] = field(default_factory=list)
    mutation_review_candidates: list[str] = field(default_factory=list)
    tdd_bridge_required: bool = True
    required_actions: list[str] = field(default_factory=list)
    can_execute_tests: bool = False
    can_write_tests: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    contains_private_reasoning: bool = False


def dump_sdd_orchestrator_contract(value: Any) -> dict[str, Any]:
    return _safe(value)


def build_sdd_role_manifest() -> SddRoleManifest:
    role_order = [
        "explorer",
        "proposer",
        "spec_writer",
        "designer",
        "task_planner",
        "risk_policy_reviewer",
        "test_strategist",
        "implementer",
        "verifier",
        "evidence_recorder",
        "human_approval_gate",
    ]
    role_specs = [
        ("explorer", "ExplorerAgent", ["context_reading", "symbol_review"], ["SddExplorerContext"]),
        ("proposer", "ProposerAgent", ["proposal_review", "scope_definition"], ["SddProposal"]),
        ("spec_writer", "SpecWriterAgent", ["requirements", "acceptance_criteria"], ["SddSpecContract"]),
        ("designer", "DesignerAgent", ["architecture", "contracts"], ["SddDesignContract"]),
        ("task_planner", "TaskPlannerAgent", ["dag_planning", "validation_planning"], ["SddTaskDagContract"]),
        ("risk_policy_reviewer", "RiskPolicyReviewerAgent", ["policy_matrix", "scope_guard"], ["SddPolicyReviewContract"]),
        ("test_strategist", "TestStrategistAgent", ["tdd_bridge", "regression_strategy"], ["SddTestStrategyContract"]),
        ("implementer", "ImplementerAgent", ["patch_candidates"], ["SddImplementationCandidate"]),
        ("verifier", "VerifierAgent", ["verification", "spec_compliance"], ["SddVerificationReport"]),
        ("evidence_recorder", "EvidenceRecorderAgent", ["evidence", "process_trace"], ["SddEvidenceTrace"]),
        ("human_approval_gate", "HumanApprovalGateAgent", ["approval_gate"], ["SddApprovalDecision"]),
    ]
    roles: list[dict[str, Any]] = []
    for role_id, role_name, capabilities, outputs in role_specs:
        roles.append(_safe({
            "role_id": role_id,
            "role": role_name,
            "aliases": [f"@{role_id.replace('_', '-')}"],
            "capabilities": capabilities,
            "outputs": outputs,
            "can_execute": False,
            "can_write_files": False,
            "can_create_agent": False,
            "can_activate_tools": False,
            "can_write_memory": False,
        }))
    return SddRoleManifest(
        role_order=role_order,
        roles=roles,
        required_actions=["review_sdd_role_manifest_before_runtime"],
    )


def build_sdd_explorer_context(
    *,
    files_considered: list[Any] | None = None,
    symbols_considered: list[Any] | None = None,
    architecture_refs: list[Any] | None = None,
    current_behavior_summary: Any = "",
    uncertainty: list[Any] | None = None,
    missing_context: list[Any] | None = None,
    evidence_refs: list[Any] | None = None,
) -> SddExplorerContext:
    raw_files = _as_list(files_considered)
    allowed_files = [path for path in raw_files if _path_allowed(path)]
    excluded_files = [path for path in raw_files if not _path_allowed(path)]
    required = []
    if missing_context:
        required.append("resolve_missing_context_before_design")
    if not allowed_files and not symbols_considered and not architecture_refs:
        required.append("provide_context_or_scope")
    return SddExplorerContext(
        files_considered=allowed_files,
        excluded_files=excluded_files,
        symbols_considered=_dedupe(_as_list(symbols_considered)),
        architecture_refs=_dedupe(_as_list(architecture_refs)),
        current_behavior_summary=_text(current_behavior_summary, limit=1200),
        uncertainty=_dedupe(_as_list(uncertainty)),
        missing_context=_dedupe(_as_list(missing_context)),
        evidence_refs=_dedupe(_as_list(evidence_refs)),
        required_actions=required,
    )


def build_sdd_proposal(
    *,
    proposed_change: Any = "",
    user_value: Any = "",
    technical_value: Any = "",
    scope: list[Any] | None = None,
    non_goals: list[Any] | None = None,
    alternatives: list[Any] | None = None,
    risks: list[Any] | None = None,
) -> SddProposal:
    blockers: list[str] = []
    required: list[str] = ["review_sdd_proposal"]
    if not _text(proposed_change):
        blockers.append("missing_proposed_change")
        required.append("define_proposed_change")
    if not _text(user_value) and not _text(technical_value):
        required.append("define_value_before_spec")
    return SddProposal(
        proposed_change=_text(proposed_change, limit=1400),
        user_value=_text(user_value, limit=800),
        technical_value=_text(technical_value, limit=800),
        scope=_dedupe(_as_list(scope)),
        non_goals=_dedupe(_as_list(non_goals)),
        alternatives=_dedupe(_as_list(alternatives)),
        risks=_dedupe(_as_list(risks)),
        blockers=blockers,
        required_actions=_dedupe(required),
    )


def build_sdd_spec_contract(
    *,
    requirements: list[Any] | None = None,
    acceptance_criteria: list[Any] | None = None,
    scenarios: list[Any] | None = None,
    edge_cases: list[Any] | None = None,
    invariants: list[Any] | None = None,
    non_functional_requirements: list[Any] | None = None,
    open_questions: list[Any] | None = None,
    spec_version: Any = "draft",
) -> SddSpecContract:
    reqs = _dedupe(_as_list(requirements))
    criteria = _dedupe(_as_list(acceptance_criteria))
    questions = _dedupe(_as_list(open_questions))
    required: list[str] = ["review_sdd_spec_contract"]
    if not reqs:
        required.append("define_requirements")
    if not criteria:
        required.append("define_acceptance_criteria")
    if questions:
        required.append("resolve_open_spec_questions")
    payload = {"requirements": reqs, "acceptance_criteria": criteria, "scenarios": scenarios or [], "invariants": invariants or []}
    return SddSpecContract(
        spec_id=f"sdd-spec-{_hash_payload(payload)[:10]}",
        spec_hash=_hash_payload(payload),
        requirements=reqs,
        acceptance_criteria=criteria,
        scenarios=_dedupe(_as_list(scenarios)),
        edge_cases=_dedupe(_as_list(edge_cases)),
        invariants=_dedupe(_as_list(invariants)),
        non_functional_requirements=_dedupe(_as_list(non_functional_requirements)),
        open_questions=questions,
        spec_version=_text(spec_version, "draft", limit=80),
        required_actions=_dedupe(required),
        verifiable=bool(reqs and criteria and not questions),
    )


def build_sdd_design_contract(
    *,
    affected_subsystems: list[Any] | None = None,
    new_contracts: list[Any] | None = None,
    data_flow: list[Any] | None = None,
    policy_gates: list[Any] | None = None,
    rollback_plan: list[Any] | None = None,
    compatibility_notes: list[Any] | None = None,
    process_trace_requirements: list[Any] | None = None,
) -> SddDesignContract:
    required = ["review_sdd_design_contract"]
    if not affected_subsystems:
        required.append("define_affected_subsystems")
    if not process_trace_requirements:
        required.append("define_process_trace_requirements")
    return SddDesignContract(
        affected_subsystems=_dedupe(_as_list(affected_subsystems)),
        new_contracts=_dedupe(_as_list(new_contracts)),
        data_flow=_dedupe(_as_list(data_flow)),
        policy_gates=_dedupe(_as_list(policy_gates or ["PolicyMatrix", "HumanApprovalGate"])),
        rollback_plan=_dedupe(_as_list(rollback_plan)),
        compatibility_notes=_dedupe(_as_list(compatibility_notes)),
        process_trace_requirements=_dedupe(_as_list(process_trace_requirements)),
        required_actions=_dedupe(required),
    )


def build_sdd_task_dag_contract(
    *,
    task_nodes: list[dict[str, Any]] | None = None,
    dependencies: list[dict[str, Any]] | None = None,
    assigned_roles: dict[str, str] | None = None,
    required_tools: list[Any] | None = None,
    expected_outputs: list[Any] | None = None,
    validation_plan: list[Any] | None = None,
    evidence_required: list[Any] | None = None,
) -> SddTaskDagContract:
    nodes = [_safe(node) for node in (task_nodes or []) if isinstance(node, dict)]
    deps = [_safe(dep) for dep in (dependencies or []) if isinstance(dep, dict)]
    required = ["review_sdd_task_dag"]
    if not nodes:
        required.append("define_task_nodes")
    if not validation_plan:
        required.append("define_validation_plan")
    return SddTaskDagContract(
        task_nodes=nodes,
        dependencies=deps,
        assigned_roles=_safe(assigned_roles or {}),
        required_tools=_dedupe(_as_list(required_tools)),
        expected_outputs=_dedupe(_as_list(expected_outputs)),
        validation_plan=_dedupe(_as_list(validation_plan)),
        evidence_required=_dedupe(_as_list(evidence_required or ["ProcessTrace", "validation_output"])),
        required_actions=_dedupe(required),
        dag_ready=bool(nodes and validation_plan),
    )


def build_sdd_policy_review_contract(
    *,
    risk_level: Any = "medium",
    policy_matrix_refs: list[Any] | None = None,
    required_approvals: list[Any] | None = None,
    blocked_actions: list[Any] | None = None,
    allowed_actions: list[Any] | None = None,
    secret_visibility_check: Any = "required",
    scope_guard: dict[str, Any] | None = None,
) -> SddPolicyReviewContract:
    risk = _text(risk_level, "medium", limit=80).lower()
    blocked = _dedupe(_as_list(blocked_actions))
    approvals = _dedupe(_as_list(required_approvals or ["human_review_before_materialization"]))
    required = ["review_sdd_policy_matrix"]
    decision = "blocked" if risk in {"critical", "blocked"} or blocked else "requires_approval"
    if blocked:
        required.append("remove_or_approve_blocked_actions")
    if not policy_matrix_refs:
        required.append("attach_policy_matrix_refs")
    return SddPolicyReviewContract(
        risk_level=risk,
        policy_matrix_refs=_dedupe(_as_list(policy_matrix_refs)),
        required_approvals=approvals,
        blocked_actions=blocked,
        allowed_actions=_dedupe(_as_list(allowed_actions)),
        secret_visibility_check=_text(secret_visibility_check, "required", limit=120),
        scope_guard=_safe(scope_guard or {"scope_review_required": True}),
        decision=decision,
        required_actions=_dedupe(required),
    )


def build_sdd_test_strategy_contract(
    *,
    test_strategy: Any = "review_required",
    test_list: list[Any] | None = None,
    regression_scope: list[Any] | None = None,
    red_phase_candidates: list[Any] | None = None,
    hidden_or_reserved_checks: list[Any] | None = None,
    mutation_review_candidates: list[Any] | None = None,
) -> SddTestStrategyContract:
    tests = _dedupe(_as_list(test_list))
    regression = _dedupe(_as_list(regression_scope))
    required = ["review_sdd_test_strategy"]
    if not tests:
        required.append("define_test_list")
    if not regression:
        required.append("define_regression_scope")
    return SddTestStrategyContract(
        test_strategy=_text(test_strategy, "review_required", limit=500),
        test_list=tests,
        regression_scope=regression,
        red_phase_candidates=_dedupe(_as_list(red_phase_candidates)),
        hidden_or_reserved_checks=_dedupe(_as_list(hidden_or_reserved_checks)),
        mutation_review_candidates=_dedupe(_as_list(mutation_review_candidates)),
        required_actions=_dedupe(required),
    )


def build_sdd_contract_sequence(
    *,
    objective: Any = "",
    files_considered: list[Any] | None = None,
    requirements: list[Any] | None = None,
    acceptance_criteria: list[Any] | None = None,
    task_nodes: list[dict[str, Any]] | None = None,
) -> list[Any]:
    """Build the initial SDD contracts in the correct side-effect-free order."""
    proposal = build_sdd_proposal(
        proposed_change=objective,
        user_value="Pending review.",
        technical_value="Pending review.",
        scope=["sdd_contracts"],
    )
    return [
        build_sdd_role_manifest(),
        build_sdd_explorer_context(files_considered=files_considered),
        proposal,
        build_sdd_spec_contract(requirements=requirements, acceptance_criteria=acceptance_criteria),
        build_sdd_design_contract(
            affected_subsystems=["SwarmCore", "ProcessTrace", "PolicyMatrix"],
            process_trace_requirements=["show_sdd_contract_outputs", "no_private_reasoning"],
        ),
        build_sdd_task_dag_contract(task_nodes=task_nodes, validation_plan=["py_compile", "targeted_pytest"]),
        build_sdd_policy_review_contract(policy_matrix_refs=["policy_matrix_runtime"]),
        build_sdd_test_strategy_contract(test_list=["contract tests"], regression_scope=["process trace"]),
    ]
