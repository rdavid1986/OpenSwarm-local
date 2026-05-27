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
            "stop_on_blocked": bool(raw.get("stop_on_blocked", True)),
            "allow_refinement": bool(raw.get("allow_refinement", True)),
            "reason": _as_text(raw.get("reason")) or "default_eval_stop_policy",
        }
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
            {
                "node_id": "evaluator",
                "node_type": "evaluator",
                "objective": "Produce final pass/fail evaluation summary.",
                "reason": "Default evaluation evaluator node.",
            },
        ],
        stop_policy={"max_iterations": 3, "min_score": 0.8},
        metadata={"task_kind": task},
    )
