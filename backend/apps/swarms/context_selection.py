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
