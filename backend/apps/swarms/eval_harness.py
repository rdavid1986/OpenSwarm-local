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
            {
                "node_id": "planner",
                "node_type": "planner",
                "objective": "Plan evaluation criteria and required checks.",
                "reason": "Default evaluation planner node.",
            },
            {
                "node_id": "generator",
                "node_type": "generator",
                "objective": "Generate or receive candidate output for evaluation.",
                "reason": "Default evaluation generator node.",
            },
            {
                "node_id": "critic",
                "node_type": "critic",
                "objective": "Identify defects, risks, missing evidence and contract violations.",
                "reason": "Default evaluation critic node.",
            },
            {
                "node_id": "refiner",
                "node_type": "refiner",
                "objective": "Propose improvements when evaluation fails and refinement is allowed.",
                "reason": "Default evaluation refiner node.",
            },
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
