"""TDD agent contracts.

Side-effect-free contracts for Red-Green-Refactor work in OpenSwarm.

This module never writes tests, executes commands, applies patches, creates
AgentContracts, creates MiniAgents, activates tools/MCP, or writes memory.
Runtime execution depends on ACTION-MATERIALIZATION.RUNTIME, SafeShell/TestRunner,
PolicyMatrix and explicit approval gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from hashlib import sha256
import re
from typing import Any


TDD_AGENT_VERSION = "openswarm.tdd_agent.v1"

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


def _text(value: Any, fallback: str = "", *, limit: int = 1200) -> str:
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
        text = _text(item, limit=500)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _dedupe(values: list[Any], *, limit: int = 120) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value, limit=500)
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


def _slug(value: Any, fallback: str = "tdd") -> str:
    text = _text(value, fallback, limit=160).lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _hash_payload(value: Any) -> str:
    raw = repr(_safe(value))
    return sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


@dataclass(frozen=True)
class TddAgentManifestRole:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_agent_manifest_role"
    tdd_version: str = TDD_AGENT_VERSION
    agent_id: str = "tdd"
    aliases: list[str] = field(default_factory=list)
    role: str = "TddAgent"
    capabilities: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    allowed_tools_policy: str = "policy_matrix_only"
    required_actions: list[str] = field(default_factory=list)
    policy_matrix_required: bool = True
    approval_required: bool = True
    can_execute: bool = False
    can_write_tests: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_create_agent: bool = False
    can_create_miniagent: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class TddTestListContract:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_test_list_contract"
    tdd_version: str = TDD_AGENT_VERSION
    feature_under_test: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    test_cases: list[dict[str, Any]] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    fixtures_needed: list[str] = field(default_factory=list)
    files_likely_touched: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    unknowns: list[str] = field(default_factory=list)
    required_user_clarifications: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    test_plan_hash: str = "unknown"
    approval_required: bool = True
    can_execute: bool = False
    can_write_tests: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class TddRedPhaseContract:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_red_phase_contract"
    tdd_version: str = TDD_AGENT_VERSION
    target_test_file: str = ""
    test_name: str = ""
    behavior_under_test: str = ""
    expected_failure_reason: str = ""
    command_to_run: str = ""
    dry_run_only: bool = True
    evidence_required: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    approval_required: bool = True
    safeshell_required: bool = True
    test_runner_required: bool = True
    can_execute: bool = False
    can_execute_tests: bool = False
    can_write_tests: bool = False
    can_write_files: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class TddGreenPatchCandidate:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_green_patch_candidate"
    tdd_version: str = TDD_AGENT_VERSION
    minimal_patch_candidate: dict[str, Any] = field(default_factory=dict)
    touched_files: list[str] = field(default_factory=list)
    expected_test_command: str = ""
    expected_pass_condition: str = ""
    regression_scope: list[str] = field(default_factory=list)
    rollback_plan: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    materialization_required: bool = True
    approval_required: bool = True
    can_execute: bool = False
    can_write_files: bool = False
    can_write_tests: bool = False
    can_apply_patch: bool = False
    can_execute_tests: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class TddRefactorContract:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_refactor_contract"
    tdd_version: str = TDD_AGENT_VERSION
    refactor_intent: str = ""
    invariant_tests: list[str] = field(default_factory=list)
    affected_symbols: list[str] = field(default_factory=list)
    rollback_plan: list[str] = field(default_factory=list)
    no_behavior_change_claim: bool = True
    required_actions: list[str] = field(default_factory=list)
    pre_refactor_green_required: bool = True
    post_refactor_green_required: bool = True
    approval_required: bool = True
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_tests: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class TddEvidenceReport:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_evidence_report"
    tdd_version: str = TDD_AGENT_VERSION
    phase: str = "unmeasured"
    test_command: str = ""
    failing_output_ref: str = ""
    passing_output_ref: str = ""
    diff_summary: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    regression_coverage: list[str] = field(default_factory=list)
    evidence_status: str = "missing"
    required_actions: list[str] = field(default_factory=list)
    can_mark_green: bool = False
    can_mark_refactor_safe: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_tests: bool = False
    contains_private_reasoning: bool = False


def dump_tdd_agent_contract(value: Any) -> dict[str, Any]:
    return _safe(value)


def build_tdd_agent_manifest_role(
    *,
    agent_id: Any = "tdd",
    aliases: list[Any] | None = None,
    role: Any = "TddAgent",
) -> TddAgentManifestRole:
    return TddAgentManifestRole(
        agent_id=_slug(agent_id, "tdd"),
        aliases=_dedupe(_as_list(aliases or ["@tdd", "@tester", "@qa"])),
        role=_text(role, "TddAgent", limit=120),
        capabilities=[
            "test_list_generation",
            "red_green_refactor",
            "regression_guard",
            "mutation_review",
            "evidence_review",
        ],
        boundaries=[
            "no_unapproved_writes",
            "no_unapproved_test_execution",
            "no_private_reasoning",
            "no_test_fabrication",
            "no_green_without_evidence",
            "no_refactor_without_regression",
        ],
        required_actions=["review_tdd_agent_manifest_role"],
    )


def build_tdd_test_list_contract(
    *,
    feature_under_test: Any = "",
    acceptance_criteria: list[Any] | None = None,
    test_cases: list[dict[str, Any]] | None = None,
    edge_cases: list[Any] | None = None,
    fixtures_needed: list[Any] | None = None,
    files_likely_touched: list[Any] | None = None,
    risk_level: Any = "medium",
    unknowns: list[Any] | None = None,
    required_user_clarifications: list[Any] | None = None,
) -> TddTestListContract:
    criteria = _dedupe(_as_list(acceptance_criteria))
    cases = [_safe(item) for item in (test_cases or []) if isinstance(item, dict)]
    unknown_list = _dedupe(_as_list(unknowns))
    clarifications = _dedupe(_as_list(required_user_clarifications))
    required = ["review_tdd_test_list"]
    if not _text(feature_under_test):
        required.append("define_feature_under_test")
    if not criteria:
        required.append("define_acceptance_criteria")
    if not cases:
        required.append("define_test_cases")
    if unknown_list or clarifications:
        required.append("resolve_tdd_unknowns_before_red_phase")
    payload = {
        "feature": _text(feature_under_test),
        "criteria": criteria,
        "cases": cases,
        "edge_cases": edge_cases or [],
    }
    return TddTestListContract(
        feature_under_test=_text(feature_under_test, limit=1000),
        acceptance_criteria=criteria,
        test_cases=cases,
        edge_cases=_dedupe(_as_list(edge_cases)),
        fixtures_needed=_dedupe(_as_list(fixtures_needed)),
        files_likely_touched=_dedupe(_as_list(files_likely_touched)),
        risk_level=_text(risk_level, "medium", limit=80).lower(),
        unknowns=unknown_list,
        required_user_clarifications=clarifications,
        required_actions=_dedupe(required),
        test_plan_hash=_hash_payload(payload),
    )


def build_tdd_red_phase_contract(
    *,
    target_test_file: Any = "",
    test_name: Any = "",
    behavior_under_test: Any = "",
    expected_failure_reason: Any = "",
    command_to_run: Any = "",
    evidence_required: list[Any] | None = None,
) -> TddRedPhaseContract:
    required = ["review_tdd_red_phase"]
    if not _text(target_test_file):
        required.append("define_target_test_file")
    if not _text(test_name):
        required.append("define_test_name")
    if not _text(expected_failure_reason):
        required.append("define_expected_failure_reason")
    if not _text(command_to_run):
        required.append("define_test_command")
    return TddRedPhaseContract(
        target_test_file=_text(target_test_file, limit=500),
        test_name=_text(test_name, limit=240),
        behavior_under_test=_text(behavior_under_test, limit=1000),
        expected_failure_reason=_text(expected_failure_reason, limit=800),
        command_to_run=_text(command_to_run, limit=500),
        evidence_required=_dedupe(_as_list(evidence_required or ["failing_test_output", "ProcessTrace"])),
        required_actions=_dedupe(required),
    )


def build_tdd_green_patch_candidate(
    *,
    minimal_patch_candidate: dict[str, Any] | None = None,
    touched_files: list[Any] | None = None,
    expected_test_command: Any = "",
    expected_pass_condition: Any = "",
    regression_scope: list[Any] | None = None,
    rollback_plan: list[Any] | None = None,
) -> TddGreenPatchCandidate:
    required = ["review_tdd_green_patch_candidate", "request_action_materialization_before_patch"]
    if not minimal_patch_candidate:
        required.append("define_minimal_patch_candidate")
    if not touched_files:
        required.append("define_touched_files")
    if not expected_test_command:
        required.append("define_expected_test_command")
    if not expected_pass_condition:
        required.append("define_expected_pass_condition")
    return TddGreenPatchCandidate(
        minimal_patch_candidate=_safe(minimal_patch_candidate or {}),
        touched_files=_dedupe(_as_list(touched_files)),
        expected_test_command=_text(expected_test_command, limit=500),
        expected_pass_condition=_text(expected_pass_condition, limit=800),
        regression_scope=_dedupe(_as_list(regression_scope)),
        rollback_plan=_dedupe(_as_list(rollback_plan or ["revert_patch_candidate"])),
        required_actions=_dedupe(required),
    )


def build_tdd_refactor_contract(
    *,
    refactor_intent: Any = "",
    invariant_tests: list[Any] | None = None,
    affected_symbols: list[Any] | None = None,
    rollback_plan: list[Any] | None = None,
) -> TddRefactorContract:
    required = ["review_tdd_refactor_contract", "confirm_pre_refactor_green_state"]
    if not _text(refactor_intent):
        required.append("define_refactor_intent")
    if not invariant_tests:
        required.append("define_invariant_tests")
    return TddRefactorContract(
        refactor_intent=_text(refactor_intent, limit=1000),
        invariant_tests=_dedupe(_as_list(invariant_tests)),
        affected_symbols=_dedupe(_as_list(affected_symbols)),
        rollback_plan=_dedupe(_as_list(rollback_plan or ["revert_refactor_candidate"])),
        required_actions=_dedupe(required),
    )


def build_tdd_evidence_report(
    *,
    phase: Any = "unmeasured",
    test_command: Any = "",
    failing_output_ref: Any = "",
    passing_output_ref: Any = "",
    diff_summary: Any = "",
    evidence_refs: list[Any] | None = None,
    regression_coverage: list[Any] | None = None,
) -> TddEvidenceReport:
    phase_text = _text(phase, "unmeasured", limit=120).lower()
    refs = _dedupe(_as_list(evidence_refs))
    failing_ref = _text(failing_output_ref, limit=500)
    passing_ref = _text(passing_output_ref, limit=500)
    regression = _dedupe(_as_list(regression_coverage))
    required = ["review_tdd_evidence_report"]
    if phase_text in {"red", "red_phase"} and not failing_ref:
        required.append("attach_failing_test_output")
    if phase_text in {"green", "green_phase"} and not passing_ref:
        required.append("attach_passing_test_output")
    if phase_text in {"refactor", "refactor_phase"} and not regression:
        required.append("attach_regression_evidence")
    evidence_status = "sufficient" if refs or failing_ref or passing_ref else "missing"
    can_mark_green = bool(phase_text in {"green", "green_phase"} and passing_ref and regression)
    can_mark_refactor_safe = bool(phase_text in {"refactor", "refactor_phase"} and passing_ref and regression)
    return TddEvidenceReport(
        phase=phase_text,
        test_command=_text(test_command, limit=500),
        failing_output_ref=failing_ref,
        passing_output_ref=passing_ref,
        diff_summary=_text(diff_summary, limit=1000),
        evidence_refs=refs,
        regression_coverage=regression,
        evidence_status=evidence_status,
        required_actions=_dedupe(required),
        can_mark_green=can_mark_green,
        can_mark_refactor_safe=can_mark_refactor_safe,
    )



@dataclass(frozen=True)
class TddControlledTestRunRequest:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_controlled_test_run_request"
    tdd_version: str = TDD_AGENT_VERSION
    phase: str = "red"
    command: str = ""
    workspace_path: str = ""
    target_test_file: str = ""
    expected_outcome: str = "failure"
    required_actions: list[str] = field(default_factory=list)
    safeshell_required: bool = True
    test_runner_required: bool = True
    approval_required: bool = True
    can_execute: bool = False
    can_execute_tests: bool = False
    can_write_tests: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class TddControlledTestRunResult:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_controlled_test_run_result"
    tdd_version: str = TDD_AGENT_VERSION
    phase: str = "red"
    command: str = ""
    workspace_path: str = ""
    execution_status: str = "not_executed"
    test_status: str = "blocked"
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    tool_error: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    regression_coverage: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    red_confirmed: bool = False
    green_confirmed: bool = False
    refactor_confirmed: bool = False
    can_mark_green: bool = False
    can_mark_refactor_safe: bool = False
    can_execute: bool = False
    can_execute_tests: bool = False
    can_write_tests: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class TddRuntimeGate:
    source_kind: str = "tdd_agent_runtime"
    tdd_contract_kind: str = "tdd_runtime_gate"
    tdd_version: str = TDD_AGENT_VERSION
    gate_status: str = "blocked"
    red_confirmed: bool = False
    green_confirmed: bool = False
    refactor_confirmed: bool = False
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    can_mark_green: bool = False
    can_mark_refactor_safe: bool = False
    can_complete_tdd_cycle: bool = False
    can_execute: bool = False
    can_execute_tests: bool = False
    can_write_tests: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    contains_private_reasoning: bool = False


def build_tdd_controlled_test_run_request(
    *,
    phase: Any = "red",
    command: Any = "",
    workspace_path: Any = "",
    target_test_file: Any = "",
    expected_outcome: Any = "",
) -> TddControlledTestRunRequest:
    phase_text = _text(phase, "red", limit=80).lower()
    command_text = _text(command, limit=500)
    target = _text(target_test_file, limit=500)
    expected = _text(expected_outcome, "", limit=120) or ("failure" if phase_text in {"red", "red_phase"} else "success")
    required = ["review_tdd_controlled_test_run_request"]

    if not command_text:
        required.append("define_test_command")
    if not command_text.startswith("python -m pytest -q "):
        required.append("use_targeted_pytest_quiet_command")
    if not _text(workspace_path):
        required.append("define_workspace_path")
    if not target:
        required.append("define_target_test_file")
    if target and target not in command_text:
        required.append("align_command_with_target_test_file")

    return TddControlledTestRunRequest(
        phase=phase_text,
        command=command_text,
        workspace_path=_text(workspace_path, limit=1000),
        target_test_file=target,
        expected_outcome=expected,
        required_actions=_dedupe(required),
    )


def execute_tdd_controlled_test_run(
    *,
    phase: Any = "red",
    command: Any = "",
    workspace_path: Any = "",
    target_test_file: Any = "",
    regression_coverage: list[Any] | None = None,
    swarm_id: Any = "tdd-runtime",
    agent_id: Any = "tdd",
    task_id: Any = "tdd-controlled-test-run",
) -> TddControlledTestRunResult:
    from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, tool_runtime

    request = build_tdd_controlled_test_run_request(
        phase=phase,
        command=command,
        workspace_path=workspace_path,
        target_test_file=target_test_file,
    )
    phase_text = request.phase
    coverage = _dedupe(_as_list(regression_coverage))
    required = ["review_tdd_controlled_test_run_result"]

    if request.required_actions and any(action != "review_tdd_controlled_test_run_request" for action in request.required_actions):
        required.extend(request.required_actions)

    history: list[dict[str, Any]] = []
    result = tool_runtime.execute_tool(
        ToolCall(name="SafeShell", input={"command": request.command}, raw_name="SafeShell"),
        ToolExecutionContext(
            workspace_path=request.workspace_path,
            session_id="tdd-controlled-test-run",
            swarm_id=_text(swarm_id, "tdd-runtime", limit=240),
            agent_id=_text(agent_id, "tdd", limit=240),
            task_id=_text(task_id, "tdd-controlled-test-run", limit=240),
            allowed_tools=["SafeShell"],
            metadata={"task_type": "tdd_controlled_test_runner", "phase": phase_text},
        ),
        history=history,
    )

    result_data = result.result or {}
    execution_status = _text(result_data.get("execution_status"), "blocked", limit=120)
    exit_code = result_data.get("exit_code")
    stdout = _text(result_data.get("stdout"), limit=3000)
    stderr = _text(result_data.get("stderr"), limit=3000)
    executed = execution_status == "executed"

    test_status = "passed" if result.ok else "failed" if executed else "blocked"
    red_confirmed = bool(phase_text in {"red", "red_phase"} and executed and not result.ok)
    green_confirmed = bool(phase_text in {"green", "green_phase"} and executed and result.ok)
    refactor_confirmed = bool(phase_text in {"refactor", "refactor_phase"} and executed and result.ok and coverage)
    can_mark_green = bool(green_confirmed and coverage)
    can_mark_refactor_safe = bool(refactor_confirmed)

    if phase_text in {"red", "red_phase"} and not red_confirmed:
        required.append("attach_failing_red_test_output")
    if phase_text in {"green", "green_phase"} and not can_mark_green:
        required.append("attach_passing_green_test_and_regression_output")
    if phase_text in {"refactor", "refactor_phase"} and not can_mark_refactor_safe:
        required.append("attach_refactor_regression_output")
    if not executed:
        required.append("resolve_safeshell_test_execution_blocker")

    evidence_refs = ["command_executed"] if executed else []

    return TddControlledTestRunResult(
        phase=phase_text,
        command=request.command,
        workspace_path=request.workspace_path,
        execution_status=execution_status,
        test_status=test_status,
        exit_code=exit_code if isinstance(exit_code, int) else None,
        stdout=stdout,
        stderr=stderr,
        tool_error=_text(result.error, limit=1000),
        evidence_refs=evidence_refs,
        regression_coverage=coverage,
        required_actions=_dedupe(required),
        red_confirmed=red_confirmed,
        green_confirmed=green_confirmed,
        refactor_confirmed=refactor_confirmed,
        can_mark_green=can_mark_green,
        can_mark_refactor_safe=can_mark_refactor_safe,
    )


def build_tdd_runtime_gate(
    *,
    red_result: Any = None,
    green_result: Any = None,
    refactor_result: Any = None,
) -> TddRuntimeGate:
    red = _safe(red_result) if red_result is not None else {}
    green = _safe(green_result) if green_result is not None else {}
    refactor = _safe(refactor_result) if refactor_result is not None else {}

    red_ok = bool(isinstance(red, dict) and red.get("red_confirmed") is True)
    green_ok = bool(isinstance(green, dict) and green.get("can_mark_green") is True)
    refactor_ok = bool(isinstance(refactor, dict) and refactor.get("can_mark_refactor_safe") is True)

    blockers: list[str] = []
    required: list[str] = ["review_tdd_runtime_gate"]

    if not red_ok:
        blockers.append("red_phase_not_confirmed")
        required.append("run_red_phase_and_attach_failing_output")
    if not green_ok:
        blockers.append("green_phase_not_confirmed")
        required.append("run_green_phase_and_attach_passing_regression_output")
    if not refactor_ok:
        blockers.append("refactor_phase_not_confirmed")
        required.append("run_refactor_phase_and_attach_regression_output")

    evidence_refs = []
    for source in [red, green, refactor]:
        if isinstance(source, dict):
            evidence_refs.extend(_as_list(source.get("evidence_refs")))

    return TddRuntimeGate(
        gate_status="completed" if not blockers else "blocked",
        red_confirmed=red_ok,
        green_confirmed=green_ok,
        refactor_confirmed=refactor_ok,
        blockers=_dedupe(blockers),
        required_actions=_dedupe(required),
        evidence_refs=_dedupe(evidence_refs),
        can_mark_green=green_ok,
        can_mark_refactor_safe=refactor_ok,
        can_complete_tdd_cycle=bool(red_ok and green_ok and refactor_ok),
    )

def build_tdd_contract_sequence(
    *,
    feature_under_test: Any = "",
    acceptance_criteria: list[Any] | None = None,
    test_cases: list[dict[str, Any]] | None = None,
    target_test_file: Any = "",
    test_name: Any = "",
    command_to_run: Any = "",
) -> list[Any]:
    return [
        build_tdd_agent_manifest_role(),
        build_tdd_test_list_contract(
            feature_under_test=feature_under_test,
            acceptance_criteria=acceptance_criteria,
            test_cases=test_cases,
            files_likely_touched=[target_test_file] if _text(target_test_file) else [],
        ),
        build_tdd_red_phase_contract(
            target_test_file=target_test_file,
            test_name=test_name,
            behavior_under_test=feature_under_test,
            expected_failure_reason="Behavior is not implemented yet.",
            command_to_run=command_to_run,
        ),
        build_tdd_green_patch_candidate(
            minimal_patch_candidate={"status": "candidate_required"},
            touched_files=[],
            expected_test_command=command_to_run,
            expected_pass_condition="Target red test passes.",
            regression_scope=["targeted regression"],
        ),
        build_tdd_refactor_contract(
            refactor_intent="No refactor until green state is evidenced.",
            invariant_tests=[command_to_run] if _text(command_to_run) else [],
        ),
        build_tdd_evidence_report(phase="unmeasured", test_command=command_to_run),
    ]
