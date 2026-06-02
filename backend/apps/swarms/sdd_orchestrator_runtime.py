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



@dataclass(frozen=True)
class SddImplementationCandidate:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_implementation_candidate"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    candidate_id: str = ""
    task_id: str = ""
    target_role: str = "implementer"
    source_contract_kind: str = ""
    patch_candidate: dict[str, Any] = field(default_factory=dict)
    touched_files: list[str] = field(default_factory=list)
    expected_diff_summary: str = ""
    validation_commands: list[str] = field(default_factory=list)
    rollback_plan: list[str] = field(default_factory=list)
    materialization_request: dict[str, Any] = field(default_factory=dict)
    materialization_decision: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    materialization_required: bool = True
    approval_required: bool = True
    policy_matrix_required: bool = True
    evidence_required: bool = True
    rollback_required: bool = True
    can_materialize: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddVerificationReport:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_verification_report"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    candidate_id: str = ""
    spec_compliance: str = "unmeasured"
    acceptance_result: str = "unmeasured"
    test_results: list[dict[str, Any]] = field(default_factory=list)
    regression_result: str = "unmeasured"
    design_compliance: str = "unmeasured"
    evidence_quality: str = "missing"
    remaining_risks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_mark_verified: bool = False
    can_mark_completed: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddEvidenceTrace:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_evidence_trace"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    candidate_id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    validation_refs: list[str] = field(default_factory=list)
    materialization_refs: list[str] = field(default_factory=list)
    process_trace_refs: list[str] = field(default_factory=list)
    diff_summary: str = ""
    changed_files: list[str] = field(default_factory=list)
    evidence_quality: str = "missing"
    required_actions: list[str] = field(default_factory=list)
    can_mark_complete: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddDelegationDecision:
    source_kind: str = "sdd_orchestrator_runtime"
    sdd_contract_kind: str = "sdd_delegation_decision"
    sdd_version: str = SDD_ORCHESTRATOR_VERSION
    delegation_id: str = ""
    current_stage: str = ""
    next_role: str = ""
    input_contract_kind: str = ""
    expected_output_contract_kind: str = ""
    context_packet_refs: list[str] = field(default_factory=list)
    handoff_payload: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    handoff_required: bool = True
    approval_required: bool = True
    policy_matrix_required: bool = True
    process_trace_required: bool = True
    can_delegate: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_execute_handoffs: bool = False
    can_activate_tools: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


def build_sdd_implementation_candidate(
    *,
    candidate_id: Any = "",
    task_id: Any = "",
    source_contract_kind: Any = "sdd_task_dag_contract",
    patch_candidate: dict[str, Any] | None = None,
    touched_files: list[Any] | None = None,
    expected_diff_summary: Any = "",
    validation_commands: list[Any] | None = None,
    rollback_plan: list[Any] | None = None,
    workspace_id: Any = "",
    cwd: Any = "",
    approval_id: Any = "",
    policy_matrix_ref: Any = "",
) -> SddImplementationCandidate:
    from backend.apps.swarms.action_materialization_runtime import (
        build_action_materialization_request,
        build_action_materialization_policy_gate,
        build_patch_materialization_plan,
        build_command_materialization_plan,
        build_action_materialization_evidence_plan,
        build_action_rollback_plan,
        decide_action_materialization,
        dump_action_materialization_contract,
    )

    files = _dedupe(_as_list(touched_files))
    commands = _dedupe(_as_list(validation_commands))
    operations = [{"path": path, "operation": "patch", "diff_summary": _text(expected_diff_summary)} for path in files]

    request = build_action_materialization_request(
        candidate_id=_text(candidate_id, "sdd-candidate", limit=240),
        source_contract_kind=_text(source_contract_kind, "sdd_implementation_candidate", limit=240),
        requested_operations=operations,
        requested_commands=commands,
        approval_id=_text(approval_id, limit=240),
        actor_id="sdd_implementer",
    )
    gate = build_action_materialization_policy_gate(
        request,
        policy_matrix_ref=_text(policy_matrix_ref, limit=240),
        approval_id=_text(approval_id, limit=240),
    )
    patch = build_patch_materialization_plan(
        request,
        workspace_id=_text(workspace_id, limit=500),
        diff_summary=_text(expected_diff_summary, limit=1200),
        rollback_plan=rollback_plan,
    )
    command = build_command_materialization_plan(request, cwd=_text(cwd, limit=500))
    evidence = build_action_materialization_evidence_plan(request, validation_commands=commands)
    rollback = build_action_rollback_plan(request, rollback_steps=rollback_plan)
    decision = decide_action_materialization(
        request=request,
        policy_gate=gate,
        patch_plan=patch,
        command_plan=command,
        evidence_plan=evidence,
        rollback_plan=rollback,
    )
    decision_data = dump_action_materialization_contract(decision)
    required = ["review_sdd_implementation_candidate", "review_action_materialization_before_runtime"]
    required.extend(_as_list(decision_data.get("required_actions")))
    blockers = _dedupe(_as_list(decision_data.get("blockers")))

    if not patch_candidate:
        required.append("define_patch_candidate")
    if not files:
        required.append("define_touched_files")
    if not commands:
        required.append("define_validation_commands")

    return SddImplementationCandidate(
        candidate_id=_text(candidate_id, "sdd-candidate", limit=240),
        task_id=_text(task_id, limit=240),
        source_contract_kind=_text(source_contract_kind, "sdd_task_dag_contract", limit=240),
        patch_candidate=_safe(patch_candidate or {}),
        touched_files=files,
        expected_diff_summary=_text(expected_diff_summary, limit=1200),
        validation_commands=commands,
        rollback_plan=_dedupe(_as_list(rollback_plan or ["revert_sdd_implementation_candidate"])),
        materialization_request=dump_action_materialization_contract(request),
        materialization_decision=decision_data,
        blockers=blockers,
        required_actions=_dedupe(required),
    )


def build_sdd_verification_report(
    *,
    candidate_id: Any = "",
    spec_compliance: Any = "unmeasured",
    acceptance_result: Any = "unmeasured",
    test_results: list[dict[str, Any]] | None = None,
    regression_result: Any = "unmeasured",
    design_compliance: Any = "unmeasured",
    evidence_quality: Any = "missing",
    remaining_risks: list[Any] | None = None,
) -> SddVerificationReport:
    tests = [_safe(item) for item in (test_results or []) if isinstance(item, dict)]
    risks = _dedupe(_as_list(remaining_risks))
    blockers: list[str] = []
    required = ["review_sdd_verification_report"]

    normalized = {
        "spec": _text(spec_compliance, "unmeasured").lower(),
        "acceptance": _text(acceptance_result, "unmeasured").lower(),
        "regression": _text(regression_result, "unmeasured").lower(),
        "design": _text(design_compliance, "unmeasured").lower(),
        "evidence": _text(evidence_quality, "missing").lower(),
    }

    if normalized["spec"] not in {"passed", "pass", "ok"}:
        blockers.append("spec_compliance_not_confirmed")
    if normalized["acceptance"] not in {"passed", "pass", "ok"}:
        blockers.append("acceptance_not_confirmed")
    if normalized["regression"] not in {"passed", "pass", "ok"}:
        blockers.append("regression_not_confirmed")
    if normalized["design"] not in {"passed", "pass", "ok"}:
        blockers.append("design_compliance_not_confirmed")
    if normalized["evidence"] not in {"sufficient", "strong"}:
        blockers.append("evidence_quality_insufficient")
    if not tests:
        required.append("attach_test_results")
    if risks:
        required.append("review_remaining_risks")

    verified = not blockers and bool(tests)

    return SddVerificationReport(
        candidate_id=_text(candidate_id, limit=240),
        spec_compliance=normalized["spec"],
        acceptance_result=normalized["acceptance"],
        test_results=tests,
        regression_result=normalized["regression"],
        design_compliance=normalized["design"],
        evidence_quality=normalized["evidence"],
        remaining_risks=risks,
        blockers=_dedupe(blockers),
        required_actions=_dedupe(required),
        can_mark_verified=verified,
        can_mark_completed=False,
    )


def build_sdd_evidence_trace(
    *,
    candidate_id: Any = "",
    evidence_refs: list[Any] | None = None,
    validation_refs: list[Any] | None = None,
    materialization_refs: list[Any] | None = None,
    process_trace_refs: list[Any] | None = None,
    diff_summary: Any = "",
    changed_files: list[Any] | None = None,
) -> SddEvidenceTrace:
    evidence = _dedupe(_as_list(evidence_refs))
    validation = _dedupe(_as_list(validation_refs))
    materialization = _dedupe(_as_list(materialization_refs))
    traces = _dedupe(_as_list(process_trace_refs))
    files = _dedupe(_as_list(changed_files))
    required = ["review_sdd_evidence_trace"]

    if not evidence:
        required.append("attach_evidence_refs")
    if not validation:
        required.append("attach_validation_refs")
    if not materialization:
        required.append("attach_materialization_refs")
    if not traces:
        required.append("attach_process_trace_refs")
    if not files:
        required.append("attach_changed_files")

    quality = "sufficient" if evidence and validation and materialization and traces and files else "missing"

    return SddEvidenceTrace(
        candidate_id=_text(candidate_id, limit=240),
        evidence_refs=evidence,
        validation_refs=validation,
        materialization_refs=materialization,
        process_trace_refs=traces,
        diff_summary=_text(diff_summary, limit=1200),
        changed_files=files,
        evidence_quality=quality,
        required_actions=_dedupe(required),
        can_mark_complete=False,
    )


def build_sdd_delegation_decision(
    *,
    current_stage: Any = "",
    input_contract_kind: Any = "",
    context_packet_refs: list[Any] | None = None,
    handoff_payload: dict[str, Any] | None = None,
) -> SddDelegationDecision:
    stage = _text(current_stage, "proposal", limit=120).lower()
    stage_map = {
        "explore": ("explorer", "sdd_explorer_context"),
        "proposal": ("proposer", "sdd_proposal"),
        "spec": ("spec_writer", "sdd_spec_contract"),
        "design": ("designer", "sdd_design_contract"),
        "tasks": ("task_planner", "sdd_task_dag_contract"),
        "policy": ("risk_policy_reviewer", "sdd_policy_review_contract"),
        "tests": ("test_strategist", "sdd_test_strategy_contract"),
        "implementation": ("implementer", "sdd_implementation_candidate"),
        "verification": ("verifier", "sdd_verification_report"),
        "evidence": ("evidence_recorder", "sdd_evidence_trace"),
        "approval": ("human_approval_gate", "sdd_approval_decision"),
    }
    next_role, expected_output = stage_map.get(stage, ("proposer", "sdd_proposal"))
    refs = _dedupe(_as_list(context_packet_refs))
    blockers: list[str] = []
    required = ["review_sdd_delegation_decision", "prepare_role_context_packet"]

    if not refs:
        blockers.append("missing_context_packet_refs")
        required.append("attach_context_packet_refs")
    if not input_contract_kind:
        required.append("attach_input_contract")

    payload = _safe(handoff_payload or {})
    delegation_id = f"sdd-delegation-{_hash_payload({'stage': stage, 'input': input_contract_kind, 'refs': refs})[:10]}"

    return SddDelegationDecision(
        delegation_id=delegation_id,
        current_stage=stage,
        next_role=next_role,
        input_contract_kind=_text(input_contract_kind, limit=240),
        expected_output_contract_kind=expected_output,
        context_packet_refs=refs,
        handoff_payload=payload,
        blockers=_dedupe(blockers),
        required_actions=_dedupe(required),
    )


def build_sdd_runtime_9_12_sequence(
    *,
    candidate_id: Any = "",
    task_id: Any = "",
    patch_candidate: dict[str, Any] | None = None,
    touched_files: list[Any] | None = None,
    validation_commands: list[Any] | None = None,
    workspace_id: Any = "",
    cwd: Any = "",
) -> list[Any]:
    implementation = build_sdd_implementation_candidate(
        candidate_id=candidate_id,
        task_id=task_id,
        patch_candidate=patch_candidate,
        touched_files=touched_files,
        expected_diff_summary="Implementation candidate requires review.",
        validation_commands=validation_commands,
        workspace_id=workspace_id,
        cwd=cwd,
    )
    verification = build_sdd_verification_report(
        candidate_id=candidate_id,
        test_results=[],
        remaining_risks=["runtime_execution_not_performed"],
    )
    evidence = build_sdd_evidence_trace(
        candidate_id=candidate_id,
        materialization_refs=[implementation.materialization_decision.get("candidate_id")] if implementation.materialization_decision else [],
        changed_files=touched_files or [],
    )
    delegation = build_sdd_delegation_decision(
        current_stage="implementation",
        input_contract_kind="sdd_task_dag_contract",
        context_packet_refs=["sdd_context_packet_required"],
        handoff_payload={"candidate_id": _text(candidate_id, limit=240), "task_id": _text(task_id, limit=240)},
    )
    return [implementation, verification, evidence, delegation]

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
