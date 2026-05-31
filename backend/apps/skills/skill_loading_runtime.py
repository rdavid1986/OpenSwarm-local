"""Side-effect-free skill loading runtime contracts.

The helpers in this module prepare compact skill availability, budget, selection,
context payload and trace metadata. They do not install skills, execute skill
content, activate tools, activate MCP servers, or load the full registry into a
model prompt by default.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "chain_of_thought",
    "cookie",
    "credential",
    "credentials",
    "hidden_reasoning",
    "password",
    "private_key",
    "prompt",
    "raw_prompt",
    "raw_response",
    "response",
    "secret",
    "session",
    "token",
}
INSTALLED_SOURCES = {"installed_skill", "installed", "local_skill"}
CANDIDATE_SOURCES = {"candidate", "skill_candidate", "import_candidate"}
REGISTRY_SOURCES = {"registry", "remote_registry", "skill_registry"}
LOADING_STATUSES = {
    "available",
    "selected",
    "loaded_summary",
    "loaded_full",
    "blocked",
    "not_found",
    "over_budget",
    "needs_review",
}


@dataclass
class SkillAvailabilityIndex:
    index_kind: str = "skill_availability_index"
    status: str = "available"
    installed_count: int = 0
    candidate_count: int = 0
    registry_count: int = 0
    total_count: int = 0
    entries: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_install_skill: bool = False
    can_execute_source: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False


@dataclass
class SkillContextBudgetCost:
    cost_kind: str = "skill_context_budget_cost"
    skill_ref: str = "unknown"
    skill_name: str = "unknown"
    source: str = "unknown"
    summary_tokens: int = 0
    content_tokens: int = 0
    examples_tokens: int = 0
    constraints_tokens: int = 0
    provenance_tokens: int = 0
    selected_tokens: int = 0
    max_context_tokens: int | None = None
    usage_ratio: float | None = None
    status: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_install_skill: bool = False
    can_execute_source: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False


@dataclass
class SkillRuntimeSelection:
    selection_kind: str = "skill_runtime_selection"
    status: str = "not_found"
    task_id: str = ""
    selected_skill_ref: str = ""
    selected_skill_name: str = ""
    selected_source: str = "unknown"
    load_mode: str = "summary_only"
    match_score: float = 0.0
    matched_requirements: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    alternatives_considered: list[dict[str, Any]] = field(default_factory=list)
    budget_cost: dict[str, Any] = field(default_factory=dict)
    reason: str = "No matching skill was selected."
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_install_skill: bool = False
    can_execute_source: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False


@dataclass
class SkillRuntimeContextPayload:
    payload_kind: str = "skill_runtime_context_payload"
    status: str = "not_loaded"
    skill_ref: str = ""
    skill_name: str = ""
    source: str = "unknown"
    load_mode: str = "summary_only"
    context_sections: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    version_refs: dict[str, Any] = field(default_factory=dict)
    context_tokens: int = 0
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_install_skill: bool = False
    can_execute_source: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    return {}


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:120]:
            normalized = str(key or "").lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS or any(token in normalized for token in ("secret", "token", "password", "credential", "authorization", "cookie", "api_key", "private_key", "prompt", "response", "chain_of_thought")):
                continue
            output[str(key)] = _safe(item)
        if len(value) > 120:
            output["__truncated__"] = f"+{len(value) - 120} more fields"
        return output
    if isinstance(value, list):
        visible = [_safe(item) for item in value[:120]]
        if len(value) > 120:
            visible.append(f"+{len(value) - 120} more")
        return visible
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, str):
        return value[:4000].rstrip() + ("..." if len(value) > 4000 else "")
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:4000]


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def estimate_skill_context_tokens(value: Any, *, chars_per_token: int = 4) -> int:
    text = _text(value)
    if not text:
        return 0
    divisor = max(1, int(chars_per_token or 4))
    return max(1, (len(text) + divisor - 1) // divisor)


def _skill_ref(skill: dict[str, Any]) -> str:
    spec = skill.get("skill_spec") if isinstance(skill.get("skill_spec"), dict) else skill
    return _text(
        skill.get("skill_ref")
        or skill.get("skill_id")
        or skill.get("candidate_id")
        or skill.get("id")
        or spec.get("id")
        or spec.get("command")
        or spec.get("name"),
        "unknown",
    )


def _skill_name(skill: dict[str, Any]) -> str:
    spec = skill.get("skill_spec") if isinstance(skill.get("skill_spec"), dict) else skill
    return _text(skill.get("skill_name") or skill.get("name") or spec.get("name") or spec.get("command"), "unknown")


def _skill_source(source: str | None, skill: dict[str, Any]) -> str:
    requested = _text(source or skill.get("skill_source") or skill.get("source") or skill.get("status"), "unknown").lower()
    if requested in INSTALLED_SOURCES or skill.get("file_path"):
        return "installed_skill"
    if requested in CANDIDATE_SOURCES or skill.get("candidate_id") or skill.get("skill_spec"):
        return "candidate"
    if requested in REGISTRY_SOURCES or skill.get("repositoryUrl") or skill.get("repository_url"):
        return "registry"
    return requested if requested else "unknown"


def _entry_from_skill(skill: Any, *, source: str = "unknown") -> dict[str, Any]:
    data = _as_dict(skill)
    spec = data.get("skill_spec") if isinstance(data.get("skill_spec"), dict) else data
    resolved_source = _skill_source(source, data)
    ref = _skill_ref(data)
    name = _skill_name(data)
    description = _text(data.get("description") or spec.get("description"))
    content = _text(data.get("content") or spec.get("content"))
    required_tools = _dedupe(_as_list(data.get("required_tools") or spec.get("required_tools")))
    required_mcp = _dedupe(_as_list(data.get("required_mcp_servers") or spec.get("required_mcp_servers")))
    tags = _dedupe(_as_list(data.get("tags") or spec.get("tags")))
    provenance = _safe(data.get("provenance") if isinstance(data.get("provenance"), dict) else spec.get("provenance") if isinstance(spec.get("provenance"), dict) else {})
    version_refs = _safe({
        "snapshot_id": data.get("snapshot_id"),
        "content_hash": data.get("content_hash") or data.get("source_hash") or provenance.get("source_hash") if isinstance(provenance, dict) else None,
        "spec_hash": data.get("spec_hash"),
    })
    content_hash = _text(data.get("content_hash") or version_refs.get("content_hash")) if isinstance(version_refs, dict) else ""
    if not content_hash and content:
        content_hash = sha256(content.encode("utf-8", errors="replace")).hexdigest()
    return _safe({
        "skill_ref": ref,
        "skill_name": name,
        "source": resolved_source,
        "status": "available",
        "description": description,
        "summary": _text(data.get("summary") or description or name),
        "tags": tags,
        "required_tools": required_tools,
        "required_mcp_servers": required_mcp,
        "has_full_content": bool(content),
        "content_preview": content[:500],
        "content_char_count": len(content),
        "content_hash": content_hash or "unknown",
        "provenance": provenance,
        "version_refs": version_refs,
        "compatibility": _safe(data.get("compatibility") if isinstance(data.get("compatibility"), dict) else spec.get("compatibility") if isinstance(spec.get("compatibility"), dict) else {}),
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    })


def build_skill_availability_index(
    *,
    installed_skills: list[Any] | None = None,
    candidates: list[Any] | None = None,
    registry_skills: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> SkillAvailabilityIndex:
    entries: list[dict[str, Any]] = []
    for skill in installed_skills or []:
        entries.append(_entry_from_skill(skill, source="installed_skill"))
    for candidate in candidates or []:
        entries.append(_entry_from_skill(candidate, source="candidate"))
    for registry_skill in registry_skills or []:
        entries.append(_entry_from_skill(registry_skill, source="registry"))

    compact_entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        key = (entry.get("skill_ref") or "unknown", entry.get("source") or "unknown")
        if key in seen:
            continue
        seen.add(key)
        compact_entries.append(entry)

    return SkillAvailabilityIndex(
        installed_count=sum(1 for item in compact_entries if item.get("source") == "installed_skill"),
        candidate_count=sum(1 for item in compact_entries if item.get("source") == "candidate"),
        registry_count=sum(1 for item in compact_entries if item.get("source") == "registry"),
        total_count=len(compact_entries),
        entries=compact_entries,
        warnings=[],
        required_actions=[],
        metadata=_safe(metadata or {}),
    )


def dump_skill_availability_index(index: SkillAvailabilityIndex | dict[str, Any]) -> dict[str, Any]:
    return _safe(index)


def build_skill_context_budget_cost(
    skill: dict[str, Any] | Any,
    *,
    load_mode: str = "summary_only",
    max_context_tokens: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> SkillContextBudgetCost:
    entry = _entry_from_skill(skill, source=_as_dict(skill).get("source") if isinstance(skill, dict) else "unknown")
    summary_text = " ".join([_text(entry.get("skill_name")), _text(entry.get("description")), " ".join(entry.get("tags") or [])])
    content_text = _text(entry.get("content_preview"))
    provenance_text = repr(entry.get("provenance") or {}) + repr(entry.get("version_refs") or {})
    constraints_text = repr({"required_tools": entry.get("required_tools"), "required_mcp_servers": entry.get("required_mcp_servers")})

    summary_tokens = estimate_skill_context_tokens(summary_text)
    content_tokens = estimate_skill_context_tokens(content_text)
    provenance_tokens = estimate_skill_context_tokens(provenance_text)
    constraints_tokens = estimate_skill_context_tokens(constraints_text)
    examples_tokens = estimate_skill_context_tokens(_as_dict(skill).get("examples"))

    normalized_mode = load_mode if load_mode in {"summary_only", "full_content", "metadata_only"} else "summary_only"
    if normalized_mode == "metadata_only":
        selected_tokens = provenance_tokens + constraints_tokens
    elif normalized_mode == "full_content":
        selected_tokens = summary_tokens + content_tokens + provenance_tokens + constraints_tokens + examples_tokens
    else:
        selected_tokens = summary_tokens + provenance_tokens + constraints_tokens

    warnings: list[str] = []
    required: list[str] = []
    usage_ratio = None
    status = "within_budget"
    if max_context_tokens is not None and max_context_tokens > 0:
        usage_ratio = round(selected_tokens / max_context_tokens, 4)
        if selected_tokens > max_context_tokens:
            status = "over_budget"
            warnings.append("skill_context_over_budget")
            required.append("review_skill_context_budget")
        elif usage_ratio >= 0.85:
            status = "near_limit"
            warnings.append("skill_context_near_limit")
            required.append("review_skill_context_budget")
    elif max_context_tokens is None:
        status = "unknown_budget"

    return SkillContextBudgetCost(
        skill_ref=_text(entry.get("skill_ref"), "unknown"),
        skill_name=_text(entry.get("skill_name"), "unknown"),
        source=_text(entry.get("source"), "unknown"),
        summary_tokens=summary_tokens,
        content_tokens=content_tokens,
        examples_tokens=examples_tokens,
        constraints_tokens=constraints_tokens,
        provenance_tokens=provenance_tokens,
        selected_tokens=selected_tokens,
        max_context_tokens=max_context_tokens,
        usage_ratio=usage_ratio,
        status=status,
        warnings=warnings,
        required_actions=required,
        metadata=_safe(metadata or {}),
    )


def dump_skill_context_budget_cost(cost: SkillContextBudgetCost | dict[str, Any]) -> dict[str, Any]:
    return _safe(cost)


def _task_requirements(task: dict[str, Any]) -> list[str]:
    requirements = _as_list(task.get("requirements")) + _as_list(task.get("required_skills")) + _as_list(task.get("tags"))
    text = " ".join([_text(task.get("title")), _text(task.get("description")), _text(task.get("goal"))]).lower()
    output = [str(item).lower().strip() for item in requirements if _text(item)]
    output.extend(token for token in text.replace(",", " ").replace(".", " ").split() if len(token) > 3)
    return _dedupe(output)


def _match_entry(entry: dict[str, Any], requirements: list[str]) -> tuple[float, list[str]]:
    searchable = " ".join(
        [
            _text(entry.get("skill_ref")),
            _text(entry.get("skill_name")),
            _text(entry.get("description")),
            " ".join(entry.get("tags") or []),
            " ".join(entry.get("required_tools") or []),
            " ".join(entry.get("required_mcp_servers") or []),
        ]
    ).lower()
    matches = [req for req in requirements if req and req in searchable]
    if not requirements:
        return (0.5 if entry.get("source") == "installed_skill" else 0.35, [])
    score = min(1.0, len(matches) / max(1, len(requirements)))
    if entry.get("source") == "installed_skill":
        score = min(1.0, score + 0.15)
    elif entry.get("source") == "candidate":
        score = min(1.0, score + 0.05)
    return score, matches


def select_skill_for_runtime(
    *,
    task: dict[str, Any] | None = None,
    availability_index: SkillAvailabilityIndex | dict[str, Any] | None = None,
    max_context_tokens: int | None = None,
    allow_full_content: bool = False,
    metadata: dict[str, Any] | None = None,
) -> SkillRuntimeSelection:
    task_data = _as_dict(task)
    index = dump_skill_availability_index(availability_index or {})
    entries = [item for item in index.get("entries") or [] if isinstance(item, dict)]
    requirements = _task_requirements(task_data)

    alternatives: list[dict[str, Any]] = []
    best_entry: dict[str, Any] | None = None
    best_score = -1.0
    best_matches: list[str] = []

    for entry in entries:
        score, matches = _match_entry(entry, requirements)
        alternatives.append({
            "skill_ref": entry.get("skill_ref"),
            "skill_name": entry.get("skill_name"),
            "source": entry.get("source"),
            "match_score": round(score, 4),
            "matched_requirements": matches,
        })
        if score > best_score:
            best_entry = entry
            best_score = score
            best_matches = matches

    if not best_entry:
        return SkillRuntimeSelection(
            status="not_found",
            task_id=_text(task_data.get("task_id") or task_data.get("id")),
            alternatives_considered=alternatives,
            warnings=["no_available_skill"],
            required_actions=["continue_without_skill_or_create_candidate"],
            metadata=_safe(metadata or {}),
        )

    load_mode = "full_content" if allow_full_content and best_entry.get("source") == "installed_skill" and best_entry.get("has_full_content") else "summary_only"
    budget = build_skill_context_budget_cost(best_entry, load_mode=load_mode, max_context_tokens=max_context_tokens)
    budget_data = dump_skill_context_budget_cost(budget)
    status = "selected"
    warnings = list(budget_data.get("warnings") or [])
    required = list(budget_data.get("required_actions") or [])
    if budget_data.get("status") == "over_budget":
        status = "over_budget"
    elif best_entry.get("source") != "installed_skill":
        warnings.append("skill_not_installed_runtime_load_summary_only")
        required.append("review_skill_candidate_or_registry_source")
        load_mode = "summary_only"

    missing = [req for req in requirements if req not in best_matches]
    return SkillRuntimeSelection(
        status=status,
        task_id=_text(task_data.get("task_id") or task_data.get("id")),
        selected_skill_ref=_text(best_entry.get("skill_ref")),
        selected_skill_name=_text(best_entry.get("skill_name"), "unknown"),
        selected_source=_text(best_entry.get("source"), "unknown"),
        load_mode=load_mode,
        match_score=round(max(0.0, best_score), 4),
        matched_requirements=best_matches,
        missing_requirements=missing,
        alternatives_considered=alternatives[:8],
        budget_cost=budget_data,
        reason="Selected by compact skill availability index and declarative requirements.",
        warnings=_dedupe(warnings),
        required_actions=_dedupe(required),
        metadata=_safe(metadata or {}),
    )


def dump_skill_runtime_selection(selection: SkillRuntimeSelection | dict[str, Any]) -> dict[str, Any]:
    return _safe(selection)


def build_skill_runtime_context_payload(
    selection: SkillRuntimeSelection | dict[str, Any],
    *,
    availability_index: SkillAvailabilityIndex | dict[str, Any] | None = None,
    include_full_content: bool = False,
    metadata: dict[str, Any] | None = None,
) -> SkillRuntimeContextPayload:
    selected = dump_skill_runtime_selection(selection)
    index = dump_skill_availability_index(availability_index or {})
    entries = [item for item in index.get("entries") or [] if isinstance(item, dict)]
    entry = next((item for item in entries if item.get("skill_ref") == selected.get("selected_skill_ref") and item.get("source") == selected.get("selected_source")), None)

    if not entry:
        return SkillRuntimeContextPayload(
            status="not_found",
            skill_ref=_text(selected.get("selected_skill_ref")),
            skill_name=_text(selected.get("selected_skill_name")),
            warnings=["selected_skill_entry_missing"],
            required_actions=["review_skill_selection"],
            metadata=_safe(metadata or {}),
        )

    allow_full = include_full_content and selected.get("load_mode") == "full_content" and entry.get("source") == "installed_skill"
    content = _text(entry.get("content_preview")) if allow_full else _text(entry.get("summary") or entry.get("description") or entry.get("skill_name"))
    status = "loaded_full" if allow_full else "loaded_summary"
    context_tokens = estimate_skill_context_tokens(content)
    evidence_refs = _dedupe(_as_list(entry.get("evidence_refs")) + _as_list(_as_dict(entry.get("provenance")).get("evidence_refs")))
    section = {
        "kind": "skill_runtime_context",
        "source": entry.get("skill_ref"),
        "content": content,
        "metadata": {
            "skill_name": entry.get("skill_name"),
            "skill_source": entry.get("source"),
            "load_mode": "full_content" if allow_full else "summary_only",
            "content_hash": entry.get("content_hash"),
            "injection_authorizes_actions": False,
            "can_install_skill": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
    }
    return SkillRuntimeContextPayload(
        status=status,
        skill_ref=_text(entry.get("skill_ref")),
        skill_name=_text(entry.get("skill_name"), "unknown"),
        source=_text(entry.get("source"), "unknown"),
        load_mode="full_content" if allow_full else "summary_only",
        context_sections=[_safe(section)],
        evidence_refs=evidence_refs,
        provenance=_safe(entry.get("provenance") or {}),
        version_refs=_safe(entry.get("version_refs") or {}),
        context_tokens=context_tokens,
        warnings=[] if allow_full or selected.get("load_mode") != "full_content" else ["full_content_not_loaded"],
        required_actions=[],
        metadata=_safe(metadata or {}),
    )


def dump_skill_runtime_context_payload(payload: SkillRuntimeContextPayload | dict[str, Any]) -> dict[str, Any]:
    return _safe(payload)


def build_skill_loading_trace_source(
    *,
    availability_index: SkillAvailabilityIndex | dict[str, Any] | None = None,
    budget_cost: SkillContextBudgetCost | dict[str, Any] | None = None,
    selection: SkillRuntimeSelection | dict[str, Any] | None = None,
    context_payload: SkillRuntimeContextPayload | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = dump_skill_availability_index(availability_index or {})
    budget = dump_skill_context_budget_cost(budget_cost or {})
    selected = dump_skill_runtime_selection(selection or {})
    payload = dump_skill_runtime_context_payload(context_payload or {})
    warnings = _dedupe(_as_list(index.get("warnings")) + _as_list(budget.get("warnings")) + _as_list(selected.get("warnings")) + _as_list(payload.get("warnings")))
    required = _dedupe(_as_list(index.get("required_actions")) + _as_list(budget.get("required_actions")) + _as_list(selected.get("required_actions")) + _as_list(payload.get("required_actions")))
    return _safe({
        "source_kind": "skill_loading_runtime",
        "loading_kind": "skill_loading_runtime",
        "status": payload.get("status") or selected.get("status") or index.get("status") or "available",
        "availability_index": index or None,
        "budget_cost": budget or None,
        "selection": selected or None,
        "context_payload": payload or None,
        "warnings": warnings,
        "required_actions": required,
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
        "metadata": _safe(metadata or {}),
    })


def attach_skill_loading_to_metadata(
    metadata: dict[str, Any] | None,
    *,
    availability_index: SkillAvailabilityIndex | dict[str, Any] | None = None,
    selection: SkillRuntimeSelection | dict[str, Any] | None = None,
    context_payload: SkillRuntimeContextPayload | dict[str, Any] | None = None,
) -> dict[str, Any]:
    clone = deepcopy(metadata) if isinstance(metadata, dict) else {}
    clone["skill_loading_runtime"] = _safe({
        "availability_index": dump_skill_availability_index(availability_index or {}),
        "selection": dump_skill_runtime_selection(selection or {}),
        "context_payload": dump_skill_runtime_context_payload(context_payload or {}),
    })
    return _safe(clone)
