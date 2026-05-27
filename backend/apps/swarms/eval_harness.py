"""Side-effect-free evaluation harness contract helpers.

EVAL-HARNESS.1 defines the normalized contract for planner/generator/critic/
refiner/evaluator loops. These helpers do not call providers, execute tools,
write files, mutate SwarmState, persist memory, or authorize actions.
"""

from __future__ import annotations

from typing import Any


MISSING = "missing"
UNKNOWN = "unknown"
MAX_TEXT = 1200
MAX_LIST_ITEMS = 40
MAX_DICT_ITEMS = 80

VALID_EVAL_NODE_TYPES = {
    "planner",
    "generator",
    "critic",
    "refiner",
    "evaluator",
}

VALID_EVAL_STATUSES = {
    "draft",
    "ready",
    "running",
    "passed",
    "failed",
    "needs_refinement",
    "blocked",
    "cancelled",
    "stopped",
}

VALID_EVAL_SEVERITIES = {"info", "low", "medium", "high", "critical"}


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


def _bounded_score(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    return max(0.0, min(1.0, score))


def normalize_eval_metric(value: Any) -> dict[str, Any]:
    """Normalize one evaluation metric without computing external state."""

    raw = _as_dict(value)
    status = _as_text(raw.get("status")) or UNKNOWN
    if status not in VALID_EVAL_STATUSES:
        status = UNKNOWN

    severity = _as_text(raw.get("severity")) or "info"
    if severity not in VALID_EVAL_SEVERITIES:
        severity = "info"

    return _bounded_value(
        {
            "metric_id": _as_text(raw.get("metric_id") or raw.get("id")) or None,
            "name": _as_text(raw.get("name")) or "unnamed_metric",
            "status": status,
            "score": _bounded_score(raw.get("score")),
            "severity": severity,
            "reason": _as_text(raw.get("reason")) or "metric_normalized",
            "evidence_refs": [_as_text(item) for item in _as_list(raw.get("evidence_refs")) if _as_text(item)],
            "metadata": _bounded_value(raw.get("metadata") or {}),
        }
    )


def normalize_eval_node(value: Any) -> dict[str, Any]:
    """Normalize one planner/generator/critic/refiner/evaluator node."""

    raw = _as_dict(value)
    node_type = _as_text(raw.get("node_type") or raw.get("type"))
    if node_type not in VALID_EVAL_NODE_TYPES:
        node_type = UNKNOWN if node_type else MISSING

    status = _as_text(raw.get("status")) or "draft"
    if status not in VALID_EVAL_STATUSES:
        status = "draft"

    metrics = [normalize_eval_metric(item) for item in _as_list(raw.get("metrics"))]

    return _bounded_value(
        {
            "node_id": _as_text(raw.get("node_id") or raw.get("id")) or None,
            "node_type": node_type,
            "status": status,
            "objective": _as_text(raw.get("objective")) or None,
            "input_refs": [_as_text(item) for item in _as_list(raw.get("input_refs")) if _as_text(item)],
            "output_refs": [_as_text(item) for item in _as_list(raw.get("output_refs")) if _as_text(item)],
            "metrics": metrics,
            "score": _bounded_score(raw.get("score")),
            "reason": _as_text(raw.get("reason")) or "eval_node_normalized",
            "requires_provider": bool(raw.get("requires_provider", False)),
            "executed": False,
            "execution_result": None,
            "metadata": _bounded_value(raw.get("metadata") or {}),
        }
    )


def normalize_eval_planner_criterion(value: Any) -> dict[str, Any]:
    """Normalize one planner criterion without evaluating it."""

    raw = _as_dict(value)
    severity = _as_text(raw.get("severity")) or "medium"
    if severity not in VALID_EVAL_SEVERITIES:
        severity = "medium"

    return _bounded_value(
        {
            "criterion_id": _as_text(raw.get("criterion_id") or raw.get("id")) or None,
            "name": _as_text(raw.get("name")) or "unnamed_criterion",
            "description": _as_text(raw.get("description")) or None,
            "required": bool(raw.get("required", True)),
            "severity": severity,
            "metric_refs": [_as_text(item) for item in _as_list(raw.get("metric_refs")) if _as_text(item)],
            "evidence_required": [_as_text(item) for item in _as_list(raw.get("evidence_required")) if _as_text(item)],
            "reason": _as_text(raw.get("reason")) or "planner_criterion_normalized",
        }
    )


def build_eval_planner_node(
    *,
    node_id: str | None = None,
    objective: str | None = None,
    task_kind: str | None = None,
    criteria: list[Any] | None = None,
    expected_metrics: list[Any] | None = None,
    required_evidence: list[Any] | None = None,
    risks: list[Any] | None = None,
    suggested_nodes: list[Any] | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an eval planner node contract without executing the plan."""

    normalized_criteria = [normalize_eval_planner_criterion(item) for item in _as_list(criteria)]
    normalized_metrics = [normalize_eval_metric(item) for item in _as_list(expected_metrics)]
    normalized_suggested_nodes = [normalize_eval_node(item) for item in _as_list(suggested_nodes)]

    resolved_status = _as_text(status) or "ready"
    if resolved_status not in VALID_EVAL_STATUSES:
        resolved_status = "ready"

    planner_metadata = _bounded_value(
        {
            "task_kind": _as_text(task_kind) or "generic",
            "criteria": normalized_criteria,
            "expected_metrics": normalized_metrics,
            "required_evidence": [_as_text(item) for item in _as_list(required_evidence) if _as_text(item)],
            "risks": [_as_text(item) for item in _as_list(risks) if _as_text(item)],
            "suggested_nodes": normalized_suggested_nodes,
            "metadata": _bounded_value(metadata or {}),
        }
    )

    return normalize_eval_node(
        {
            "node_id": _as_text(node_id) or "planner",
            "node_type": "planner",
            "status": resolved_status,
            "objective": _as_text(objective) or "Plan evaluation criteria and required checks.",
            "metrics": normalized_metrics,
            "score": 0.0,
            "reason": "eval_planner_node_contract",
            "requires_provider": False,
            "metadata": planner_metadata,
        }
    )


def build_default_eval_planner_node(
    *,
    objective: str | None = None,
    task_kind: str | None = None,
) -> dict[str, Any]:
    """Build a default planner node for common OpenSwarm evaluation flows."""

    task = _as_text(task_kind) or "generic"
    return build_eval_planner_node(
        objective=objective or "Plan evaluation criteria and required checks.",
        task_kind=task,
        criteria=[
            {
                "criterion_id": "contract_validity",
                "name": "Contract validity",
                "description": "Output must follow the expected contract shape.",
                "severity": "high",
                "metric_refs": ["contract_validity"],
                "evidence_required": ["normalized contract"],
            },
            {
                "criterion_id": "grounding",
                "name": "Grounding",
                "description": "Claims must be grounded in provided state, evidence, files or explicit payload.",
                "severity": "high",
                "metric_refs": ["grounding"],
                "evidence_required": ["state_context", "evidence_refs"],
            },
            {
                "criterion_id": "safety",
                "name": "Safety and non-execution claims",
                "description": "The result must not claim tool execution, file mutation or validation without evidence.",
                "severity": "critical",
                "metric_refs": ["safety"],
                "evidence_required": ["execution evidence or explicit no-execution state"],
            },
        ],
        expected_metrics=[
            {"metric_id": "contract_validity", "name": "Contract validity", "status": "draft", "severity": "high"},
            {"metric_id": "grounding", "name": "Grounding", "status": "draft", "severity": "high"},
            {"metric_id": "safety", "name": "Safety", "status": "draft", "severity": "critical"},
        ],
        required_evidence=["state_context", "expected_contract", "evidence_refs"],
        risks=["invented_evidence", "false_execution_claim", "contract_drift"],
        suggested_nodes=[
            {"node_id": "critic", "node_type": "critic", "objective": "Check defects, risks and missing evidence."},
            {"node_id": "evaluator", "node_type": "evaluator", "objective": "Return final pass/fail evaluation."},
        ],
    )


def normalize_eval_generator_candidate(value: Any) -> dict[str, Any]:
    """Normalize one generated or provided candidate without generating it."""

    raw = _as_dict(value)
    status = _as_text(raw.get("status")) or "draft"
    if status not in VALID_EVAL_STATUSES:
        status = "draft"

    return _bounded_value(
        {
            "candidate_id": _as_text(raw.get("candidate_id") or raw.get("id")) or None,
            "kind": _as_text(raw.get("kind") or raw.get("type")) or "candidate",
            "status": status,
            "summary": _as_text(raw.get("summary")) or None,
            "content_ref": _as_text(raw.get("content_ref")) or None,
            "artifact_refs": [_as_text(item) for item in _as_list(raw.get("artifact_refs")) if _as_text(item)],
            "evidence_refs": [_as_text(item) for item in _as_list(raw.get("evidence_refs")) if _as_text(item)],
            "source_refs": [_as_text(item) for item in _as_list(raw.get("source_refs")) if _as_text(item)],
            "claims": [_as_text(item) for item in _as_list(raw.get("claims")) if _as_text(item)],
            "metadata": _bounded_value(raw.get("metadata") or {}),
            "generated": False,
            "executed": False,
            "execution_result": None,
        }
    )


def build_eval_generator_node(
    *,
    node_id: str | None = None,
    objective: str | None = None,
    task_kind: str | None = None,
    candidates: list[Any] | None = None,
    input_refs: list[Any] | None = None,
    output_refs: list[Any] | None = None,
    claims: list[Any] | None = None,
    artifact_refs: list[Any] | None = None,
    evidence_refs: list[Any] | None = None,
    source_refs: list[Any] | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an eval generator node contract without generating output."""

    normalized_candidates = [normalize_eval_generator_candidate(item) for item in _as_list(candidates)]
    resolved_status = _as_text(status) or "ready"
    if resolved_status not in VALID_EVAL_STATUSES:
        resolved_status = "ready"

    generator_metadata = _bounded_value(
        {
            "task_kind": _as_text(task_kind) or "generic",
            "candidates": normalized_candidates,
            "claims": [_as_text(item) for item in _as_list(claims) if _as_text(item)],
            "artifact_refs": [_as_text(item) for item in _as_list(artifact_refs) if _as_text(item)],
            "evidence_refs": [_as_text(item) for item in _as_list(evidence_refs) if _as_text(item)],
            "source_refs": [_as_text(item) for item in _as_list(source_refs) if _as_text(item)],
            "metadata": _bounded_value(metadata or {}),
        }
    )

    return normalize_eval_node(
        {
            "node_id": _as_text(node_id) or "generator",
            "node_type": "generator",
            "status": resolved_status,
            "objective": _as_text(objective) or "Represent candidate output for evaluation.",
            "input_refs": input_refs,
            "output_refs": output_refs,
            "metrics": [],
            "score": 0.0,
            "reason": "eval_generator_node_contract",
            "requires_provider": False,
            "metadata": generator_metadata,
        }
    )


def build_default_eval_generator_node(
    *,
    objective: str | None = None,
    task_kind: str | None = None,
) -> dict[str, Any]:
    """Build a default non-generating generator node for OpenSwarm eval loops."""

    task = _as_text(task_kind) or "generic"
    return build_eval_generator_node(
        objective=objective or "Represent candidate output for evaluation.",
        task_kind=task,
        candidates=[],
        claims=[],
        artifact_refs=[],
        evidence_refs=[],
        source_refs=[],
        metadata={"candidate_source": "not_provided"},
    )


def normalize_eval_critic_finding(value: Any) -> dict[str, Any]:
    """Normalize one critic finding without judging external state."""

    raw = _as_dict(value)
    severity = _as_text(raw.get("severity")) or "medium"
    if severity not in VALID_EVAL_SEVERITIES:
        severity = "medium"

    status = _as_text(raw.get("status")) or "draft"
    if status not in VALID_EVAL_STATUSES:
        status = "draft"

    return _bounded_value(
        {
            "finding_id": _as_text(raw.get("finding_id") or raw.get("id")) or None,
            "kind": _as_text(raw.get("kind") or raw.get("type")) or "defect",
            "status": status,
            "severity": severity,
            "summary": _as_text(raw.get("summary")) or None,
            "claim_ref": _as_text(raw.get("claim_ref")) or None,
            "criterion_ref": _as_text(raw.get("criterion_ref")) or None,
            "metric_ref": _as_text(raw.get("metric_ref")) or None,
            "evidence_refs": [_as_text(item) for item in _as_list(raw.get("evidence_refs")) if _as_text(item)],
            "missing_evidence": [_as_text(item) for item in _as_list(raw.get("missing_evidence")) if _as_text(item)],
            "recommendation": _as_text(raw.get("recommendation")) or None,
            "reason": _as_text(raw.get("reason")) or "critic_finding_normalized",
        }
    )


def build_eval_critic_node(
    *,
    node_id: str | None = None,
    objective: str | None = None,
    task_kind: str | None = None,
    findings: list[Any] | None = None,
    unsupported_claims: list[Any] | None = None,
    contract_violations: list[Any] | None = None,
    missing_evidence: list[Any] | None = None,
    refinement_recommendations: list[Any] | None = None,
    input_refs: list[Any] | None = None,
    output_refs: list[Any] | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an eval critic node contract without running critique."""

    normalized_findings = [normalize_eval_critic_finding(item) for item in _as_list(findings)]
    resolved_status = _as_text(status) or "ready"
    if resolved_status not in VALID_EVAL_STATUSES:
        resolved_status = "ready"

    critical_count = sum(1 for item in normalized_findings if item.get("severity") == "critical")
    high_count = sum(1 for item in normalized_findings if item.get("severity") == "high")
    total_findings = len(normalized_findings)
    score = 1.0 if total_findings == 0 else max(0.0, 1.0 - (critical_count * 0.4) - (high_count * 0.25) - (total_findings * 0.1))

    critic_metadata = _bounded_value(
        {
            "task_kind": _as_text(task_kind) or "generic",
            "findings": normalized_findings,
            "unsupported_claims": [_as_text(item) for item in _as_list(unsupported_claims) if _as_text(item)],
            "contract_violations": [_as_text(item) for item in _as_list(contract_violations) if _as_text(item)],
            "missing_evidence": [_as_text(item) for item in _as_list(missing_evidence) if _as_text(item)],
            "refinement_recommendations": [
                _as_text(item) for item in _as_list(refinement_recommendations) if _as_text(item)
            ],
            "finding_count": total_findings,
            "critical_count": critical_count,
            "high_count": high_count,
            "metadata": _bounded_value(metadata or {}),
        }
    )

    return normalize_eval_node(
        {
            "node_id": _as_text(node_id) or "critic",
            "node_type": "critic",
            "status": resolved_status,
            "objective": _as_text(objective) or "Identify defects, risks, missing evidence and contract violations.",
            "input_refs": input_refs,
            "output_refs": output_refs,
            "metrics": [
                {
                    "metric_id": "critic_findings",
                    "name": "Critic findings",
                    "status": "passed" if total_findings == 0 else "needs_refinement",
                    "score": score,
                    "severity": "critical" if critical_count else "high" if high_count else "info",
                    "reason": "critic_findings_metric",
                }
            ],
            "score": score,
            "reason": "eval_critic_node_contract",
            "requires_provider": False,
            "metadata": critic_metadata,
        }
    )


def build_default_eval_critic_node(
    *,
    objective: str | None = None,
    task_kind: str | None = None,
) -> dict[str, Any]:
    """Build a default critic node for OpenSwarm evaluation loops."""

    task = _as_text(task_kind) or "generic"
    return build_eval_critic_node(
        objective=objective or "Identify defects, risks, missing evidence and contract violations.",
        task_kind=task,
        findings=[],
        unsupported_claims=[],
        contract_violations=[],
        missing_evidence=[],
        refinement_recommendations=[],
        metadata={"critic_source": "not_run"},
    )


def normalize_eval_refinement_proposal(value: Any) -> dict[str, Any]:
    """Normalize one refiner proposal without applying it."""

    raw = _as_dict(value)
    status = _as_text(raw.get("status")) or "draft"
    if status not in VALID_EVAL_STATUSES:
        status = "draft"

    severity = _as_text(raw.get("severity")) or "medium"
    if severity not in VALID_EVAL_SEVERITIES:
        severity = "medium"

    return _bounded_value(
        {
            "proposal_id": _as_text(raw.get("proposal_id") or raw.get("id")) or None,
            "status": status,
            "severity": severity,
            "summary": _as_text(raw.get("summary")) or None,
            "target_ref": _as_text(raw.get("target_ref")) or None,
            "finding_refs": [_as_text(item) for item in _as_list(raw.get("finding_refs")) if _as_text(item)],
            "required_evidence": [_as_text(item) for item in _as_list(raw.get("required_evidence")) if _as_text(item)],
            "expected_change": _as_text(raw.get("expected_change")) or None,
            "risk": _as_text(raw.get("risk")) or None,
            "reason": _as_text(raw.get("reason")) or "refinement_proposal_normalized",
            "applied": False,
            "executed": False,
            "execution_result": None,
        }
    )


def build_eval_refiner_node(
    *,
    node_id: str | None = None,
    objective: str | None = None,
    task_kind: str | None = None,
    proposals: list[Any] | None = None,
    finding_refs: list[Any] | None = None,
    blocked_reasons: list[Any] | None = None,
    input_refs: list[Any] | None = None,
    output_refs: list[Any] | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an eval refiner node contract without applying refinements."""

    normalized_proposals = [normalize_eval_refinement_proposal(item) for item in _as_list(proposals)]
    resolved_status = _as_text(status) or "ready"
    if resolved_status not in VALID_EVAL_STATUSES:
        resolved_status = "ready"

    blocked = [_as_text(item) for item in _as_list(blocked_reasons) if _as_text(item)]
    proposal_count = len(normalized_proposals)
    score = 1.0 if proposal_count > 0 and not blocked else 0.0 if blocked else 0.5

    refiner_metadata = _bounded_value(
        {
            "task_kind": _as_text(task_kind) or "generic",
            "proposals": normalized_proposals,
            "proposal_count": proposal_count,
            "finding_refs": [_as_text(item) for item in _as_list(finding_refs) if _as_text(item)],
            "blocked_reasons": blocked,
            "metadata": _bounded_value(metadata or {}),
        }
    )

    return normalize_eval_node(
        {
            "node_id": _as_text(node_id) or "refiner",
            "node_type": "refiner",
            "status": resolved_status,
            "objective": _as_text(objective) or "Propose safe refinements without applying them.",
            "input_refs": input_refs,
            "output_refs": output_refs,
            "metrics": [
                {
                    "metric_id": "refinement_proposals",
                    "name": "Refinement proposals",
                    "status": "blocked" if blocked else "passed" if proposal_count else "draft",
                    "score": score,
                    "severity": "high" if blocked else "info",
                    "reason": "refinement_proposals_metric",
                }
            ],
            "score": score,
            "reason": "eval_refiner_node_contract",
            "requires_provider": False,
            "metadata": refiner_metadata,
        }
    )


def build_default_eval_refiner_node(
    *,
    objective: str | None = None,
    task_kind: str | None = None,
) -> dict[str, Any]:
    """Build a default refiner node for OpenSwarm evaluation loops."""

    task = _as_text(task_kind) or "generic"
    return build_eval_refiner_node(
        objective=objective or "Propose improvements when evaluation fails and refinement is allowed.",
        task_kind=task,
        proposals=[],
        finding_refs=[],
        blocked_reasons=[],
        metadata={"refiner_source": "not_run"},
    )


def normalize_eval_final_decision(value: Any) -> dict[str, Any]:
    """Normalize final evaluator decision without executing validation."""

    raw = _as_dict(value)
    status = _as_text(raw.get("status")) or "draft"
    if status not in VALID_EVAL_STATUSES:
        status = "draft"

    return _bounded_value(
        {
            "decision_id": _as_text(raw.get("decision_id") or raw.get("id")) or None,
            "status": status,
            "passed": bool(raw.get("passed", False)),
            "score": _bounded_score(raw.get("score")),
            "summary": _as_text(raw.get("summary")) or None,
            "needs_refinement": bool(raw.get("needs_refinement", False)),
            "blocked": bool(raw.get("blocked", False)),
            "blockers": [_as_text(item) for item in _as_list(raw.get("blockers")) if _as_text(item)],
            "evidence_refs": [_as_text(item) for item in _as_list(raw.get("evidence_refs")) if _as_text(item)],
            "metric_refs": [_as_text(item) for item in _as_list(raw.get("metric_refs")) if _as_text(item)],
            "reason": _as_text(raw.get("reason")) or "final_decision_normalized",
        }
    )


def build_eval_evaluator_node(
    *,
    node_id: str | None = None,
    objective: str | None = None,
    task_kind: str | None = None,
    final_decision: dict[str, Any] | None = None,
    metrics: list[Any] | None = None,
    evidence_refs: list[Any] | None = None,
    blockers: list[Any] | None = None,
    needs_refinement: bool | None = None,
    input_refs: list[Any] | None = None,
    output_refs: list[Any] | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an eval evaluator node contract without executing validation."""

    normalized_metrics = [normalize_eval_metric(item) for item in _as_list(metrics)]
    blocker_values = [_as_text(item) for item in _as_list(blockers) if _as_text(item)]
    metric_scores = [float(item.get("score") or 0.0) for item in normalized_metrics]
    average_score = sum(metric_scores) / len(metric_scores) if metric_scores else 0.0

    raw_decision = _as_dict(final_decision)
    if not raw_decision:
        raw_decision = {
            "status": "blocked" if blocker_values else "draft",
            "passed": bool(normalized_metrics) and average_score >= 0.8 and not blocker_values,
            "score": average_score,
            "needs_refinement": bool(needs_refinement) or average_score < 0.8 or bool(blocker_values),
            "blocked": bool(blocker_values),
            "blockers": blocker_values,
            "evidence_refs": evidence_refs,
            "metric_refs": [item.get("metric_id") for item in normalized_metrics if item.get("metric_id")],
            "summary": "Evaluation decision prepared from normalized metrics.",
        }
    decision = normalize_eval_final_decision(raw_decision)

    resolved_status = _as_text(status) or decision.get("status") or "ready"
    if resolved_status not in VALID_EVAL_STATUSES:
        resolved_status = "ready"

    evaluator_metadata = _bounded_value(
        {
            "task_kind": _as_text(task_kind) or "generic",
            "final_decision": decision,
            "evidence_refs": [_as_text(item) for item in _as_list(evidence_refs) if _as_text(item)],
            "blockers": blocker_values,
            "needs_refinement": bool(decision.get("needs_refinement")),
            "passed": bool(decision.get("passed")),
            "metadata": _bounded_value(metadata or {}),
        }
    )

    return normalize_eval_node(
        {
            "node_id": _as_text(node_id) or "evaluator",
            "node_type": "evaluator",
            "status": resolved_status,
            "objective": _as_text(objective) or "Produce final pass/fail evaluation summary.",
            "input_refs": input_refs,
            "output_refs": output_refs,
            "metrics": normalized_metrics,
            "score": decision.get("score"),
            "reason": "eval_evaluator_node_contract",
            "requires_provider": False,
            "metadata": evaluator_metadata,
        }
    )


def build_default_eval_evaluator_node(
    *,
    objective: str | None = None,
    task_kind: str | None = None,
) -> dict[str, Any]:
    """Build a default evaluator node for OpenSwarm evaluation loops."""

    task = _as_text(task_kind) or "generic"
    return build_eval_evaluator_node(
        objective=objective or "Produce final pass/fail evaluation summary.",
        task_kind=task,
        final_decision={
            "status": "draft",
            "passed": False,
            "score": 0.0,
            "needs_refinement": False,
            "blocked": False,
            "summary": "Evaluator has not run.",
            "reason": "default_eval_evaluator_node",
        },
        metrics=[],
        evidence_refs=[],
        blockers=[],
        metadata={"evaluator_source": "not_run"},
    )


def build_eval_loop_contract(
    *,
    loop_id: str | None = None,
    objective: str | None = None,
    task_kind: str | None = None,
    nodes: list[Any] | None = None,
    stop_policy: dict[str, Any] | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized evaluation loop contract without running it."""

    normalized_nodes = [normalize_eval_node(item) for item in _as_list(nodes)]
    resolved_status = _as_text(status) or "draft"
    if resolved_status not in VALID_EVAL_STATUSES:
        resolved_status = "draft"

    policy = normalize_eval_stop_policy(stop_policy)

    return _bounded_value(
        {
            "loop_id": _as_text(loop_id) or None,
            "kind": "eval_loop_contract",
            "objective": _as_text(objective) or None,
            "task_kind": _as_text(task_kind) or "generic",
            "status": resolved_status,
            "nodes": normalized_nodes,
            "node_count": len(normalized_nodes),
            "stop_policy": policy,
            "stop_decision": evaluate_eval_loop_stop_policy(
                stop_policy=policy,
                evaluator_node=normalized_nodes[-1] if normalized_nodes else None,
                current_iteration=0,
            ),
            "summary": summarize_eval_loop(nodes=normalized_nodes, stop_policy=policy, status=resolved_status),
            "executed": False,
            "execution_result": None,
            "metadata": _bounded_value(metadata or {}),
        }
    )


def normalize_eval_stop_policy(value: Any) -> dict[str, Any]:
    """Normalize loop stop policy without evaluating external execution."""

    raw = _as_dict(value)
    max_iterations_raw = raw.get("max_iterations")
    try:
        max_iterations = int(max_iterations_raw)
    except Exception:
        max_iterations = 3
    max_iterations = max(1, min(max_iterations, 12))

    min_score = _bounded_score(raw.get("min_score") if raw.get("min_score") is not None else 0.80)

    return _bounded_value(
        {
            "max_iterations": max_iterations,
            "min_score": min_score,
            "stop_on_pass": bool(raw.get("stop_on_pass", True)),
            "stop_on_failed": bool(raw.get("stop_on_failed", False)),
            "stop_on_blocked": bool(raw.get("stop_on_blocked", True)),
            "stop_on_max_iterations": bool(raw.get("stop_on_max_iterations", True)),
            "allow_refinement": bool(raw.get("allow_refinement", True)),
            "require_evidence": bool(raw.get("require_evidence", True)),
            "reason": _as_text(raw.get("reason")) or "default_eval_stop_policy",
        }
    )


def evaluate_eval_loop_stop_policy(
    *,
    stop_policy: dict[str, Any] | None = None,
    evaluator_node: dict[str, Any] | None = None,
    current_iteration: int | None = None,
    blockers: list[Any] | None = None,
) -> dict[str, Any]:
    """Evaluate whether an eval loop should stop without running the loop."""

    policy = normalize_eval_stop_policy(stop_policy)
    evaluator = _as_dict(evaluator_node)
    evaluator_metadata = _as_dict(evaluator.get("metadata"))
    final_decision = normalize_eval_final_decision(evaluator_metadata.get("final_decision"))
    blocker_values = [_as_text(item) for item in _as_list(blockers) if _as_text(item)]
    blocker_values.extend([item for item in final_decision.get("blockers", []) if item not in blocker_values])

    try:
        iteration = int(current_iteration or 0)
    except Exception:
        iteration = 0
    iteration = max(0, iteration)

    score = _bounded_score(final_decision.get("score"))
    passed = bool(final_decision.get("passed")) and score >= float(policy.get("min_score") or 0.0)
    blocked = bool(final_decision.get("blocked")) or bool(blocker_values)
    needs_refinement = bool(final_decision.get("needs_refinement")) or score < float(policy.get("min_score") or 0.0)
    max_iterations_reached = iteration >= int(policy.get("max_iterations") or 1)

    should_stop = False
    reason = "continue"
    final_status = "needs_refinement" if needs_refinement else "ready"

    if blocked and policy.get("stop_on_blocked"):
        should_stop = True
        reason = "blocked"
        final_status = "blocked"
    elif passed and policy.get("stop_on_pass"):
        should_stop = True
        reason = "passed"
        final_status = "passed"
    elif max_iterations_reached and policy.get("stop_on_max_iterations"):
        should_stop = True
        reason = "max_iterations_reached"
        final_status = "failed" if needs_refinement else "stopped"
    elif final_decision.get("status") == "failed" and policy.get("stop_on_failed"):
        should_stop = True
        reason = "failed"
        final_status = "failed"
    elif needs_refinement and not policy.get("allow_refinement"):
        should_stop = True
        reason = "refinement_not_allowed"
        final_status = "failed"

    return _bounded_value(
        {
            "status": final_status,
            "should_stop": should_stop,
            "reason": reason,
            "passed": passed,
            "blocked": blocked,
            "needs_refinement": needs_refinement,
            "current_iteration": iteration,
            "max_iterations": policy.get("max_iterations"),
            "max_iterations_reached": max_iterations_reached,
            "score": score,
            "min_score": policy.get("min_score"),
            "blockers": blocker_values,
            "stop_policy": policy,
            "executed": False,
            "execution_result": None,
        }
    )


def collect_eval_loop_memory_items(loop_contract: dict[str, Any] | None) -> dict[str, Any]:
    """Collect portable eval memory items without persisting them."""

    loop = _as_dict(loop_contract)
    nodes = [_as_dict(item) for item in _as_list(loop.get("nodes"))]

    findings: list[Any] = []
    proposals: list[Any] = []
    evidence_refs: list[str] = []
    blockers: list[str] = []

    for node in nodes:
        metadata = _as_dict(node.get("metadata"))
        findings.extend(_as_list(metadata.get("findings")))
        proposals.extend(_as_list(metadata.get("proposals")))
        evidence_refs.extend(_as_text(item) for item in _as_list(metadata.get("evidence_refs")) if _as_text(item))
        blockers.extend(_as_text(item) for item in _as_list(metadata.get("blockers")) if _as_text(item))
        final_decision = _as_dict(metadata.get("final_decision"))
        evidence_refs.extend(_as_text(item) for item in _as_list(final_decision.get("evidence_refs")) if _as_text(item))
        blockers.extend(_as_text(item) for item in _as_list(final_decision.get("blockers")) if _as_text(item))

    stop_decision = _as_dict(loop.get("stop_decision"))
    blockers.extend(_as_text(item) for item in _as_list(stop_decision.get("blockers")) if _as_text(item))

    return _bounded_value(
        {
            "findings": findings,
            "proposals": proposals,
            "evidence_refs": sorted({item for item in evidence_refs if item}),
            "blockers": sorted({item for item in blockers if item}),
        }
    )


def build_eval_memory_record(
    *,
    loop_contract: dict[str, Any] | None = None,
    memory_id: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a side-effect-free memory record for future eval retrieval.

    This does not persist to DB, project memory, filesystem, or vector storage.
    It only returns the normalized record that a later persistence layer may store.
    """

    loop = _as_dict(loop_contract)
    stop_decision = _as_dict(loop.get("stop_decision"))
    memory_items = collect_eval_loop_memory_items(loop)
    score = _bounded_score(stop_decision.get("score"))

    return _bounded_value(
        {
            "memory_id": _as_text(memory_id) or None,
            "kind": "eval_memory_record",
            "source": _as_text(source) or "eval_harness",
            "loop_id": _as_text(loop.get("loop_id")) or None,
            "task_kind": _as_text(loop.get("task_kind")) or "generic",
            "objective": _as_text(loop.get("objective")) or None,
            "status": _as_text(stop_decision.get("status") or loop.get("status")) or "draft",
            "passed": bool(stop_decision.get("passed", False)),
            "blocked": bool(stop_decision.get("blocked", False)),
            "needs_refinement": bool(stop_decision.get("needs_refinement", False)),
            "score": score,
            "min_score": stop_decision.get("min_score"),
            "reason": _as_text(stop_decision.get("reason")) or "eval_memory_record",
            "node_count": int(loop.get("node_count") or 0),
            "findings": memory_items.get("findings", []),
            "proposals": memory_items.get("proposals", []),
            "evidence_refs": memory_items.get("evidence_refs", []),
            "blockers": memory_items.get("blockers", []),
            "final_decision": stop_decision,
            "persisted": False,
            "executed": False,
            "execution_result": None,
            "metadata": _bounded_value(metadata or {}),
        }
    )


def summarize_eval_memory_record(memory_record: dict[str, Any] | None) -> str:
    """Return compact summary for an eval memory record."""

    record = _as_dict(memory_record)
    return (
        "Eval Memory: "
        f"task_kind={_as_text(record.get('task_kind')) or MISSING}; "
        f"status={_as_text(record.get('status')) or MISSING}; "
        f"passed={bool(record.get('passed', False))}; "
        f"blocked={bool(record.get('blocked', False))}; "
        f"needs_refinement={bool(record.get('needs_refinement', False))}; "
        f"score={record.get('score', 0.0)}; "
        f"findings={len(_as_list(record.get('findings')))}; "
        f"proposals={len(_as_list(record.get('proposals')))}; "
        f"evidence_refs={len(_as_list(record.get('evidence_refs')))}; "
        "persisted=False"
    )


def summarize_eval_loop(
    *,
    nodes: list[Any] | None = None,
    stop_policy: dict[str, Any] | None = None,
    status: str | None = None,
) -> str:
    """Return compact loop summary for logs, prompts and tests."""

    normalized_nodes = [_as_dict(item) for item in _as_list(nodes)]
    policy = _as_dict(stop_policy)
    node_types: dict[str, int] = {}
    for node in normalized_nodes:
        node_type = _as_text(node.get("node_type")) or UNKNOWN
        node_types[node_type] = node_types.get(node_type, 0) + 1

    parts = [f"{key}={node_types[key]}" for key in sorted(node_types)]
    return (
        "Eval Loop: "
        f"status={_as_text(status) or MISSING}; "
        f"nodes={len(normalized_nodes)}; "
        f"types={','.join(parts) if parts else 'none'}; "
        f"max_iterations={policy.get('max_iterations', 3)}; "
        f"min_score={policy.get('min_score', 0.8)}; "
        "executed=False"
    )


def build_default_eval_loop_contract(*, objective: str | None = None, task_kind: str | None = None) -> dict[str, Any]:
    """Build the default planner/generator/critic/refiner/evaluator loop shape."""

    task = _as_text(task_kind) or "generic"
    return build_eval_loop_contract(
        objective=objective,
        task_kind=task,
        nodes=[
            build_default_eval_planner_node(
                objective="Plan evaluation criteria and required checks.",
                task_kind=task,
            ),
            build_default_eval_generator_node(
                objective="Generate or receive candidate output for evaluation.",
                task_kind=task,
            ),
            build_default_eval_critic_node(
                objective="Identify defects, risks, missing evidence and contract violations.",
                task_kind=task,
            ),
            build_default_eval_refiner_node(
                objective="Propose improvements when evaluation fails and refinement is allowed.",
                task_kind=task,
            ),
            build_default_eval_evaluator_node(
                objective="Produce final pass/fail evaluation summary.",
                task_kind=task,
            ),
        ],
        stop_policy={"max_iterations": 3, "min_score": 0.8},
        metadata={"task_kind": task},
    )
