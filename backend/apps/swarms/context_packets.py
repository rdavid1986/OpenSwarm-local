"""Side-effect-free Context Packet helpers for Swarm/MiniAgent runtime.

SWARM-CONTEXT-PACKETS.0-4 defines a compact, traceable context packet
contract. These helpers only normalize caller-provided data. They never fetch
files, call models, execute tools, mutate SwarmState, write memory, or grant
permissions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any

from backend.apps.swarms.agent_handoff import build_handoff_context_for_next_agent
from backend.apps.swarms.context_selection import (
    apply_context_inclusion_explanations,
    apply_context_quality_gate,
    build_context_budget_summary,
    rank_context_sources,
)
from backend.apps.swarms.state_context import normalize_state_context_value


MISSING = "missing"
UNKNOWN = "unknown"
CONTEXT_PACKET_VERSION = "openswarm.context_packet.v1"
MAX_TEXT = 1200
MAX_LIST_ITEMS = 40
MAX_DICT_ITEMS = 120

SENSITIVE_KEY_TOKENS = (
    "secret",
    "token",
    "password",
    "credential",
    "authorization",
    "cookie",
    "api_key",
    "private_key",
    "raw_prompt",
    "raw_response",
    "chain_of_thought",
    "private_reasoning",
    "hidden_reasoning",
)


@dataclass
class ContextPacketItem:
    item_kind: str = "context_packet_item"
    source_kind: str = UNKNOWN
    source_id: str = ""
    status: str = "selected"
    content_ref: str = ""
    summary: str = ""
    memory_tier: str = "task_working_memory"
    trust: str = UNKNOWN
    confidence: float = 0.0
    freshness: str = UNKNOWN
    ttl_seconds: int = 0
    token_cost: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    allowed_usage: list[str] = field(default_factory=list)
    read_policy: str = "read_only"
    write_policy: str = "no_write"
    conflict_status: str = "none"
    stale_reason: str = ""
    risk_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextPacket:
    packet_kind: str = "context_packet"
    packet_version: str = CONTEXT_PACKET_VERSION
    status: str = "ready"
    packet_id: str = ""
    target_kind: str = "miniagent"
    target_id: str = ""
    task_id: str = ""
    goal: str = ""
    mode: str = ""
    model_id: str = ""
    created_at: str = ""
    items: list[dict[str, Any]] = field(default_factory=list)
    selected_sources: list[dict[str, Any]] = field(default_factory=list)
    excluded_sources: list[dict[str, Any]] = field(default_factory=list)
    memory_tiers: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    handoff_context: dict[str, Any] = field(default_factory=dict)
    skill_context: dict[str, Any] = field(default_factory=dict)
    policy_context: dict[str, Any] = field(default_factory=dict)
    context_budget: dict[str, Any] = field(default_factory=dict)
    context_quality_gate: dict[str, Any] = field(default_factory=dict)
    context_inclusion_explanations: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_execute_tools: bool = False
    can_mutate_memory: bool = False
    contains_private_reasoning: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text[:MAX_TEXT]


def _int(value: Any, fallback: int = 0) -> int:
    try:
        number = int(value)
        return number if number >= 0 else fallback
    except Exception:
        return fallback


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        number = float(value)
        return max(0.0, min(1.0, number))
    except Exception:
        return fallback


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    if hasattr(value, "dict"):
        try:
            return value.dict()
        except Exception:
            return {}
    return {}


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").lower().replace("-", "_")
    return any(token in normalized for token in SENSITIVE_KEY_TOKENS)


def normalize_context_packet_value(value: Any) -> Any:
    """Return a JSON-safe, bounded and redacted representation."""

    if is_dataclass(value):
        value = asdict(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text[:MAX_TEXT] + ("..." if len(text) > MAX_TEXT else "")
    if isinstance(value, list | tuple | set):
        items = [normalize_context_packet_value(item) for item in list(value)[:MAX_LIST_ITEMS]]
        if len(value) > MAX_LIST_ITEMS:
            items.append(f"+{len(value) - MAX_LIST_ITEMS} more")
        return items
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, key in enumerate(sorted(value.keys(), key=lambda item: str(item))):
            if index >= MAX_DICT_ITEMS:
                output["__truncated__"] = True
                break
            if _is_sensitive_key(key):
                continue
            output[str(key)[:160]] = normalize_context_packet_value(value.get(key))
        return output
    return _text(value)


def _dedupe_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= MAX_LIST_ITEMS:
            break
    return result


def normalize_memory_tier(value: Any) -> str:
    normalized = _text(value, "task_working_memory").lower().replace("-", "_")
    allowed = {
        "core_memory",
        "task_working_memory",
        "archival_memory_ref",
        "shared_swarm_memory",
        "miniagent_private_working_memory",
        "project_instructions",
        "policy_memory",
        "evidence_memory",
        "handoff_memory",
        "skill_script_memory",
    }
    return normalized if normalized in allowed else "task_working_memory"


def normalize_context_trust(value: Any, *, evidence_refs: list[Any] | None = None, confidence: float | None = None) -> str:
    explicit = _text(value).lower()
    allowed = {"trusted", "usable", "needs_review", "stale", "conflicting", "blocked", "unknown"}
    if explicit in allowed:
        return explicit
    if evidence_refs:
        return "usable"
    if confidence is not None and confidence >= 0.8:
        return "usable"
    return UNKNOWN


def build_context_packet_item(
    *,
    source_kind: str,
    source_id: str | None = None,
    summary: str | None = None,
    content_ref: str | None = None,
    status: str = "selected",
    memory_tier: str = "task_working_memory",
    evidence_refs: list[Any] | None = None,
    confidence: float | int | None = None,
    freshness: str | None = None,
    ttl_seconds: int | None = None,
    token_cost: int | None = None,
    allowed_usage: list[Any] | None = None,
    read_policy: str = "read_only",
    write_policy: str = "no_write",
    conflict_status: str = "none",
    stale_reason: str | None = None,
    trust: str | None = None,
    risk_notes: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs = _dedupe_text(_as_list(evidence_refs))
    confidence_value = _float(confidence)
    item = ContextPacketItem(
        source_kind=_text(source_kind, UNKNOWN),
        source_id=_text(source_id),
        status=_text(status, "selected"),
        content_ref=_text(content_ref),
        summary=_text(summary),
        memory_tier=normalize_memory_tier(memory_tier),
        trust=normalize_context_trust(trust, evidence_refs=refs, confidence=confidence_value),
        confidence=confidence_value,
        freshness=_text(freshness, UNKNOWN),
        ttl_seconds=_int(ttl_seconds),
        token_cost=_int(token_cost),
        evidence_refs=refs,
        allowed_usage=_dedupe_text(_as_list(allowed_usage or ["reasoning"])),
        read_policy=_text(read_policy, "read_only"),
        write_policy=_text(write_policy, "no_write"),
        conflict_status=_text(conflict_status, "none"),
        stale_reason=_text(stale_reason),
        risk_notes=_dedupe_text(_as_list(risk_notes)),
        metadata=normalize_context_packet_value(metadata or {}),
    )
    return normalize_context_packet_value(item)


def build_memory_tier_index(items: list[dict[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
    tiers: dict[str, list[dict[str, Any]]] = {}
    for item in _as_list(items):
        item_dict = _as_dict(item)
        tier = normalize_memory_tier(item_dict.get("memory_tier"))
        tiers.setdefault(tier, []).append(normalize_context_packet_value(item_dict))
    return normalize_context_packet_value(tiers)


def _source_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return normalize_context_packet_value(
        {
            "source_kind": item.get("source_kind"),
            "source_id": item.get("source_id"),
            "status": item.get("status"),
            "reason": "context_packet_item",
            "freshness": item.get("freshness"),
            "confidence": item.get("confidence"),
            "budget_cost": item.get("token_cost"),
            "refs": {"evidence_refs": item.get("evidence_refs") or []},
            "metadata": {
                "memory_tier": item.get("memory_tier"),
                "trust": item.get("trust"),
                "conflict_status": item.get("conflict_status"),
                "stale_reason": item.get("stale_reason"),
                "risk_notes": item.get("risk_notes") or [],
                "has_evidence": bool(item.get("evidence_refs")),
            },
        }
    )


def build_context_packet_budget(
    *,
    items: list[dict[str, Any]] | None,
    context_budget_total: int | None = None,
    reserved_response_budget: int | None = None,
    reserved_tool_budget: int | None = None,
    reserved_evidence_budget: int | None = None,
    context_budget_source: str | None = None,
) -> dict[str, Any]:
    selected_sources = [_source_from_item(_as_dict(item)) for item in _as_list(items)]
    return build_context_budget_summary(
        context_budget_total=context_budget_total,
        selected_sources=selected_sources,
        reserved_response_budget=reserved_response_budget,
        reserved_tool_budget=reserved_tool_budget,
        reserved_evidence_budget=reserved_evidence_budget,
        context_budget_source=context_budget_source or "context_packet",
    )


def build_context_packet(
    *,
    packet_id: str | None = None,
    target_kind: str = "miniagent",
    target_id: str | None = None,
    task_id: str | None = None,
    goal: str | None = None,
    mode: str | None = None,
    model_id: str | None = None,
    items: list[dict[str, Any]] | None = None,
    context_sources: list[Any] | None = None,
    handoffs: list[dict[str, Any]] | None = None,
    skill_context: dict[str, Any] | None = None,
    policy_context: dict[str, Any] | None = None,
    context_budget_total: int | None = None,
    reserved_response_budget: int | None = None,
    reserved_tool_budget: int | None = None,
    reserved_evidence_budget: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic packet from already-available context pieces."""

    normalized_items = [normalize_context_packet_value(item) for item in _as_list(items) if isinstance(item, dict)]

    source_candidates = list(_as_list(context_sources))
    source_candidates.extend(_source_from_item(_as_dict(item)) for item in normalized_items)
    ranked = rank_context_sources(source_candidates)
    selected_sources = [source for source in ranked if _as_dict(source).get("status") != "excluded"]
    excluded_sources = [source for source in ranked if _as_dict(source).get("status") == "excluded"]

    base_policy = {
        "selected_sources": selected_sources,
        "excluded_sources": excluded_sources,
        "required_sources_missing": [],
        "context_budget": build_context_budget_summary(
            context_budget_total=context_budget_total,
            selected_sources=selected_sources,
            reserved_response_budget=reserved_response_budget,
            reserved_tool_budget=reserved_tool_budget,
            reserved_evidence_budget=reserved_evidence_budget,
            context_budget_source="context_packet_builder",
        ),
    }
    policy_with_explanations = apply_context_inclusion_explanations(base_policy)
    policy_with_quality = apply_context_quality_gate(policy_with_explanations)

    handoff_context = build_handoff_context_for_next_agent(handoffs or [], target_id) if handoffs else {}

    warnings: list[str] = []
    required_actions: list[str] = []

    quality = _as_dict(policy_with_quality.get("context_quality_gate"))
    if quality.get("status") not in {"sufficient", "", None}:
        warnings.append(f"context_quality_{quality.get('status')}")
        required_actions.append("review_context_packet_quality")

    for item in normalized_items:
        item_dict = _as_dict(item)
        if item_dict.get("trust") in {"blocked", "conflicting", "stale"}:
            warnings.append(f"context_item_{item_dict.get('trust')}")
        if item_dict.get("write_policy") not in {"no_write", "read_only"}:
            required_actions.append("review_context_write_policy")

    packet = ContextPacket(
        status="needs_review" if warnings or required_actions else "ready",
        packet_id=_text(packet_id, f"context_packet:{_text(target_kind)}:{_text(target_id)}:{_text(task_id)}"),
        target_kind=_text(target_kind, "miniagent"),
        target_id=_text(target_id),
        task_id=_text(task_id),
        goal=_text(goal),
        mode=_text(mode),
        model_id=_text(model_id),
        created_at=_now(),
        items=normalized_items,
        selected_sources=normalize_context_packet_value(selected_sources),
        excluded_sources=normalize_context_packet_value(excluded_sources),
        memory_tiers=build_memory_tier_index(normalized_items),
        handoff_context=normalize_context_packet_value(handoff_context),
        skill_context=normalize_context_packet_value(skill_context or {}),
        policy_context=normalize_context_packet_value(policy_context or {}),
        context_budget=normalize_context_packet_value(policy_with_quality.get("context_budget") or {}),
        context_quality_gate=normalize_context_packet_value(policy_with_quality.get("context_quality_gate") or {}),
        context_inclusion_explanations=normalize_context_packet_value(policy_with_quality.get("context_inclusion_explanations") or {}),
        warnings=_dedupe_text(warnings),
        required_actions=_dedupe_text(required_actions),
        metadata=normalize_context_packet_value(metadata or {}),
    )
    return normalize_context_packet_value(packet)


def build_context_packet_state_context_section(packet: dict[str, Any]) -> dict[str, Any]:
    normalized = _as_dict(normalize_context_packet_value(packet))
    summaries = []
    for item in _as_list(normalized.get("items")):
        item_dict = _as_dict(item)
        summary = _text(item_dict.get("summary"))
        if summary:
            summaries.append(f"{item_dict.get('memory_tier') or UNKNOWN}: {summary}")
    if not summaries:
        summaries.append("No context packet items selected.")

    return normalize_state_context_value(
        {
            "kind": "context_packet",
            "source": "ContextCore",
            "content": "\n".join(summaries[:MAX_LIST_ITEMS]),
            "metadata": {
                "packet_id": normalized.get("packet_id"),
                "status": normalized.get("status"),
                "target_kind": normalized.get("target_kind"),
                "target_id": normalized.get("target_id"),
                "task_id": normalized.get("task_id"),
                "item_count": len(_as_list(normalized.get("items"))),
                "selected_source_count": len(_as_list(normalized.get("selected_sources"))),
                "excluded_source_count": len(_as_list(normalized.get("excluded_sources"))),
                "context_budget": normalized.get("context_budget"),
                "context_quality_gate": normalized.get("context_quality_gate"),
                "injection_authorizes_actions": False,
                "can_execute_tools": False,
                "can_mutate_memory": False,
            },
        }
    )


def build_context_packet_trace_source(packet: dict[str, Any], *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = _as_dict(normalize_context_packet_value(packet))
    return normalize_context_packet_value(
        {
            "source_kind": "context_packet",
            "packet_kind": "context_packet",
            "status": normalized.get("status") or "ready",
            "packet_id": normalized.get("packet_id"),
            "target_kind": normalized.get("target_kind"),
            "target_id": normalized.get("target_id"),
            "task_id": normalized.get("task_id"),
            "item_count": len(_as_list(normalized.get("items"))),
            "selected_source_count": len(_as_list(normalized.get("selected_sources"))),
            "excluded_source_count": len(_as_list(normalized.get("excluded_sources"))),
            "memory_tiers": normalized.get("memory_tiers") or {},
            "context_budget": normalized.get("context_budget") or {},
            "context_quality_gate": normalized.get("context_quality_gate") or {},
            "warnings": normalized.get("warnings") or [],
            "required_actions": normalized.get("required_actions") or [],
            "metadata": normalize_context_packet_value(metadata or {}),
        }
    )
