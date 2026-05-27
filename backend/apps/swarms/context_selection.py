"""Side-effect-free context retrieval and selection policy helpers.

RI-X.2.D / CTX-RET.1 defines how OpenSwarm represents candidate context
sources before a model-assisted flow receives state_context. These helpers do
not read files, query storage, call providers, execute tools, or mutate Swarm
state. Callers provide already-known state; this module normalizes it.
"""

from __future__ import annotations

from typing import Any


MISSING = "missing"
UNKNOWN = "unknown"
MAX_TEXT = 600
MAX_LIST_ITEMS = 24
MAX_DICT_ITEMS = 64

VALID_SCOPES = {
    "swarm",
    "agent",
    "mini_agent",
    "planner",
    "refinement",
    "debug",
    "web_ground",
    "tool",
    "validation",
}

VALID_SOURCE_KINDS = {
    "project_memory",
    "swarm_messages",
    "artifacts",
    "evidence",
    "outputs",
    "candidates",
    "filesystem",
    "agents_md",
    "docs",
    "tool_registry",
    "research_cache",
    "miniagent_runs",
    "runtime_checkpoints",
    "dependency_outputs",
}

VALID_SELECTION_STATUS = {
    "selected",
    "excluded",
    "missing",
    "blocked",
}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _count_or_zero(value: Any) -> int:
    try:
        number = int(value)
        return number if number >= 0 else 0
    except Exception:
        return 0


def normalize_context_selection_value(value: Any) -> Any:
    """Return a bounded JSON-safe representation without inventing values."""

    if value is None:
        return None
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return value.strip()[:MAX_TEXT]
    if isinstance(value, list | tuple | set):
        return [normalize_context_selection_value(item) for item in list(value)[:MAX_LIST_ITEMS]]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for index, key in enumerate(sorted(value.keys(), key=lambda item: str(item))):
            if index >= MAX_DICT_ITEMS:
                normalized["__truncated__"] = True
                break
            normalized[str(key)[:120]] = normalize_context_selection_value(value.get(key))
        return normalized
    return _as_text(value)[:MAX_TEXT]


def normalize_context_source(value: Any) -> dict[str, Any]:
    """Normalize a caller-provided context source candidate."""

    raw = _as_dict(value)
    source_kind = _as_text(raw.get("source_kind") or raw.get("kind"))
    if source_kind not in VALID_SOURCE_KINDS:
        source_kind = UNKNOWN if source_kind else MISSING

    source_id = _as_text(raw.get("source_id") or raw.get("id"))
    status = _as_text(raw.get("status"))
    if status not in VALID_SELECTION_STATUS:
        status = "selected"

    reason = _as_text(raw.get("reason") or raw.get("selection_reason"))
    if not reason:
        reason = "caller_provided"

    return normalize_context_selection_value(
        {
            "source_kind": source_kind,
            "source_id": source_id or None,
            "status": status,
            "reason": reason,
            "freshness": raw.get("freshness"),
            "confidence": raw.get("confidence"),
            "budget_cost": _count_or_zero(raw.get("budget_cost")),
            "refs": normalize_context_selection_value(raw.get("refs") or {}),
            "metadata": normalize_context_selection_value(raw.get("metadata") or {}),
        }
    )


def build_context_selection_policy(
    *,
    request_id: str | None = None,
    scope: str | None = None,
    mode: str | None = None,
    task_kind: str | None = None,
    user_goal: str | None = None,
    selected_sources: list[Any] | None = None,
    excluded_sources: list[Any] | None = None,
    required_sources_missing: list[Any] | None = None,
    allowed_files: list[Any] | None = None,
    relevant_files: list[Any] | None = None,
    forbidden_files: list[Any] | None = None,
    evidence_refs: list[Any] | None = None,
    artifact_refs: list[Any] | None = None,
    output_refs: list[Any] | None = None,
    candidate_refs: list[Any] | None = None,
    memory_refs: list[Any] | None = None,
    dependency_output_refs: list[Any] | None = None,
    freshness_refs: dict[str, Any] | None = None,
    context_budget_used: int | None = None,
    context_budget_total: int | None = None,
    context_budget_source: str | None = None,
    selection_reason: str | None = None,
    risk_notes: list[Any] | None = None,
    confidence: float | int | None = None,
    fallback_used: bool | None = None,
) -> dict[str, Any]:
    """Build a normalized context selection policy from caller-provided state."""

    resolved_scope = _as_text(scope)
    if resolved_scope not in VALID_SCOPES:
        resolved_scope = UNKNOWN if resolved_scope else MISSING

    policy = {
        "request_id": _as_text(request_id) or None,
        "scope": resolved_scope,
        "mode": _as_text(mode) or MISSING,
        "task_kind": _as_text(task_kind) or MISSING,
        "user_goal": _as_text(user_goal) or MISSING,
        "selected_sources": [normalize_context_source(item) for item in _as_list(selected_sources)],
        "excluded_sources": [
            normalize_context_source({**_as_dict(item), "status": _as_dict(item).get("status") or "excluded"})
            for item in _as_list(excluded_sources)
        ],
        "required_sources_missing": [
            normalize_context_source({**_as_dict(item), "status": _as_dict(item).get("status") or "missing"})
            for item in _as_list(required_sources_missing)
        ],
        "allowed_files": normalize_context_selection_value(allowed_files or []),
        "relevant_files": normalize_context_selection_value(relevant_files or []),
        "forbidden_files": normalize_context_selection_value(forbidden_files or []),
        "evidence_refs": normalize_context_selection_value(evidence_refs or []),
        "artifact_refs": normalize_context_selection_value(artifact_refs or []),
        "output_refs": normalize_context_selection_value(output_refs or []),
        "candidate_refs": normalize_context_selection_value(candidate_refs or []),
        "memory_refs": normalize_context_selection_value(memory_refs or []),
        "dependency_output_refs": normalize_context_selection_value(dependency_output_refs or []),
        "freshness_refs": normalize_context_selection_value(freshness_refs or {}),
        "context_budget_used": _count_or_zero(context_budget_used),
        "context_budget_total": _count_or_zero(context_budget_total),
        "context_budget_source": _as_text(context_budget_source) or MISSING,
        "selection_reason": _as_text(selection_reason) or "caller_provided",
        "risk_notes": normalize_context_selection_value(risk_notes or []),
        "confidence": max(0.0, min(1.0, float(confidence))) if isinstance(confidence, int | float) else 0.0,
        "fallback_used": bool(fallback_used),
    }
    return normalize_context_selection_value(policy)


def summarize_context_selection_policy(policy: dict[str, Any] | None) -> str:
    """Return a compact, human-readable summary for logs/prompts/UI."""

    normalized = _as_dict(normalize_context_selection_value(policy or {}))
    selected = len(_as_list(normalized.get("selected_sources")))
    excluded = len(_as_list(normalized.get("excluded_sources")))
    missing = len(_as_list(normalized.get("required_sources_missing")))
    budget_used = _count_or_zero(normalized.get("context_budget_used"))
    budget_total = _count_or_zero(normalized.get("context_budget_total"))
    return (
        "Context Selection: "
        f"scope={normalized.get('scope') or MISSING}; "
        f"task_kind={normalized.get('task_kind') or MISSING}; "
        f"selected={selected}; excluded={excluded}; missing={missing}; "
        f"budget={budget_used}/{budget_total}; "
        f"source={normalized.get('context_budget_source') or MISSING}"
    )


def _score_flag(value: Any, *, positive: float = 0.0, negative: float = 0.0) -> float:
    if value is True:
        return positive
    if value is False:
        return negative
    return 0.0


def score_context_source(value: Any) -> dict[str, Any]:
    """Score a normalized context source without fetching external state."""

    source = normalize_context_source(value)
    metadata = _as_dict(source.get("metadata"))
    refs = _as_dict(source.get("refs"))
    status = _as_text(source.get("status"))
    freshness = _as_text(source.get("freshness")).lower()
    confidence_raw = source.get("confidence")
    confidence = float(confidence_raw) if isinstance(confidence_raw, int | float) else 0.0
    confidence = max(0.0, min(1.0, confidence))
    budget_cost = _count_or_zero(source.get("budget_cost"))

    score = 0.0
    reasons: list[str] = []

    if status == "selected":
        score += 10.0
        reasons.append("selected")
    elif status == "excluded":
        score -= 50.0
        reasons.append("excluded")
    elif status == "blocked":
        score -= 100.0
        reasons.append("blocked")
    elif status == "missing":
        score -= 25.0
        reasons.append("missing")

    if freshness in {"fresh", "current", "verified"}:
        score += 15.0
        reasons.append("fresh")
    elif freshness in {"stale", "old", "unknown"}:
        score -= 10.0
        reasons.append("stale_or_unknown")

    if confidence:
        score += confidence * 20.0
        reasons.append("confidence")

    if metadata.get("directly_related") is True:
        score += 25.0
        reasons.append("directly_related")
    if metadata.get("allowed") is True:
        score += 15.0
        reasons.append("allowed")
    if metadata.get("forbidden") is True:
        score -= 100.0
        reasons.append("forbidden")
    if metadata.get("has_evidence") is True or refs.get("evidence_refs"):
        score += 20.0
        reasons.append("has_evidence")
    if metadata.get("dependency") is True:
        score += 10.0
        reasons.append("dependency")
    if metadata.get("risk") in {"high", "danger", "destructive"}:
        score -= 20.0
        reasons.append("risk_penalty")

    if budget_cost > 0:
        score -= min(float(budget_cost) / 1000.0, 20.0)
        reasons.append("budget_cost")

    ranked = dict(source)
    ranked["rank_score"] = round(score, 4)
    ranked["rank_reasons"] = reasons
    return normalize_context_selection_value(ranked)


def rank_context_sources(sources: list[Any] | None) -> list[dict[str, Any]]:
    """Return context sources ranked from most to least useful."""

    ranked = [score_context_source(item) for item in _as_list(sources)]
    return sorted(
        ranked,
        key=lambda item: (
            float(_as_dict(item).get("rank_score") or 0.0),
            _as_text(_as_dict(item).get("source_kind")),
            _as_text(_as_dict(item).get("source_id")),
        ),
        reverse=True,
    )



def build_context_budget_summary(
    *,
    context_budget_total: int | None = None,
    context_budget_used: int | None = None,
    selected_sources: list[Any] | None = None,
    reserved_response_budget: int | None = None,
    reserved_tool_budget: int | None = None,
    reserved_evidence_budget: int | None = None,
    context_budget_source: str | None = None,
    overflow_strategy: str | None = None,
) -> dict[str, Any]:
    """Build a side-effect-free context budget summary.

    The helper only summarizes caller-provided context candidates. It does not
    fetch files, estimate tokens from content, call models, mutate SwarmState or
    decide permissions.
    """

    total = _count_or_zero(context_budget_total)
    explicit_used = _count_or_zero(context_budget_used)
    source_cost = sum(
        _count_or_zero(_as_dict(normalize_context_source(item)).get("budget_cost"))
        for item in _as_list(selected_sources)
    )
    used = explicit_used or source_cost

    reserved_response = _count_or_zero(reserved_response_budget)
    reserved_tool = _count_or_zero(reserved_tool_budget)
    reserved_evidence = _count_or_zero(reserved_evidence_budget)
    reserved_total = reserved_response + reserved_tool + reserved_evidence

    available_for_context = max(total - reserved_total, 0) if total else 0
    remaining = max(available_for_context - used, 0) if available_for_context else 0
    overflow_amount = max(used - available_for_context, 0) if available_for_context else 0

    if not total:
        status = "unknown_budget"
    elif overflow_amount > 0:
        status = "over_budget"
    elif available_for_context and used >= available_for_context:
        status = "at_limit"
    else:
        status = "within_budget"

    return normalize_context_selection_value(
        {
            "context_budget_total": total,
            "context_budget_used": used,
            "context_budget_remaining": remaining,
            "context_budget_available_for_context": available_for_context,
            "context_budget_reserved_total": reserved_total,
            "reserved_response_budget": reserved_response,
            "reserved_tool_budget": reserved_tool,
            "reserved_evidence_budget": reserved_evidence,
            "context_budget_source": _as_text(context_budget_source) or MISSING,
            "context_budget_status": status,
            "overflow_amount": overflow_amount,
            "overflow_strategy": _as_text(overflow_strategy) or "exclude_lowest_ranked_sources",
        }
    )


def apply_context_budget_to_policy(
    policy: dict[str, Any] | None,
    *,
    reserved_response_budget: int | None = None,
    reserved_tool_budget: int | None = None,
    reserved_evidence_budget: int | None = None,
    overflow_strategy: str | None = None,
) -> dict[str, Any]:
    """Attach a computed context budget summary to a normalized policy."""

    normalized = _as_dict(normalize_context_selection_value(policy or {}))
    budget = build_context_budget_summary(
        context_budget_total=normalized.get("context_budget_total"),
        context_budget_used=normalized.get("context_budget_used"),
        selected_sources=_as_list(normalized.get("selected_sources")),
        reserved_response_budget=reserved_response_budget,
        reserved_tool_budget=reserved_tool_budget,
        reserved_evidence_budget=reserved_evidence_budget,
        context_budget_source=_as_text(normalized.get("context_budget_source")) or None,
        overflow_strategy=overflow_strategy,
    )

    merged = dict(normalized)
    merged["context_budget"] = budget
    merged["context_budget_used"] = budget["context_budget_used"]
    merged["context_budget_total"] = budget["context_budget_total"]
    merged["context_budget_source"] = budget["context_budget_source"]
    return normalize_context_selection_value(merged)



def apply_context_budget_exclusion_policy(
    policy: dict[str, Any] | None,
    *,
    reserved_response_budget: int | None = None,
    reserved_tool_budget: int | None = None,
    reserved_evidence_budget: int | None = None,
    overflow_strategy: str | None = None,
) -> dict[str, Any]:
    """Move lowest-priority selected sources to excluded_sources when over budget.

    This helper is deterministic and side-effect free. It does not delete
    context candidates; it preserves overflowed items as excluded sources with a
    traceable reason.
    """

    enriched = apply_context_budget_to_policy(
        policy,
        reserved_response_budget=reserved_response_budget,
        reserved_tool_budget=reserved_tool_budget,
        reserved_evidence_budget=reserved_evidence_budget,
        overflow_strategy=overflow_strategy,
    )
    budget = _as_dict(enriched.get("context_budget"))
    available = _count_or_zero(budget.get("context_budget_available_for_context"))

    if not available:
        return normalize_context_selection_value(enriched)

    selected_ranked = rank_context_sources(_as_list(enriched.get("selected_sources")))
    kept: list[dict[str, Any]] = []
    excluded_by_budget: list[dict[str, Any]] = []
    used = 0

    for source in selected_ranked:
        source_cost = _count_or_zero(_as_dict(source).get("budget_cost"))
        if used + source_cost <= available:
            kept.append(source)
            used += source_cost
            continue

        excluded = dict(source)
        excluded["status"] = "excluded"
        excluded["reason"] = "excluded_by_context_budget"
        excluded_metadata = dict(_as_dict(excluded.get("metadata")))
        excluded_metadata["excluded_reason"] = "context_budget_exceeded"
        excluded_metadata["excluded_by"] = "context_budget_policy"
        excluded["metadata"] = excluded_metadata
        excluded_by_budget.append(normalize_context_selection_value(excluded))

    merged = dict(enriched)
    merged["selected_sources"] = kept
    merged["excluded_sources"] = rank_context_sources(
        _as_list(enriched.get("excluded_sources")) + excluded_by_budget
    )
    merged["context_budget"] = build_context_budget_summary(
        context_budget_total=budget.get("context_budget_total"),
        context_budget_used=used,
        selected_sources=kept,
        reserved_response_budget=budget.get("reserved_response_budget"),
        reserved_tool_budget=budget.get("reserved_tool_budget"),
        reserved_evidence_budget=budget.get("reserved_evidence_budget"),
        context_budget_source=budget.get("context_budget_source"),
        overflow_strategy=budget.get("overflow_strategy"),
    )
    merged["context_budget_used"] = merged["context_budget"]["context_budget_used"]
    merged["context_budget_total"] = merged["context_budget"]["context_budget_total"]
    merged["context_budget_source"] = merged["context_budget"]["context_budget_source"]
    merged["selection_reason"] = _as_text(merged.get("selection_reason")) or "context_budget_policy"
    return normalize_context_selection_value(merged)


def build_ranked_context_selection_policy(**kwargs: Any) -> dict[str, Any]:
    """Build a policy and rank its selected sources."""

    policy = build_context_selection_policy(**kwargs)
    policy["selected_sources"] = rank_context_sources(policy.get("selected_sources"))
    policy["excluded_sources"] = rank_context_sources(policy.get("excluded_sources"))
    policy["required_sources_missing"] = rank_context_sources(policy.get("required_sources_missing"))
    return normalize_context_selection_value(policy)
