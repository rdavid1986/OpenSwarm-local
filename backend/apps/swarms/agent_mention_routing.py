"""Agent mention routing contracts.

Side-effect-free contracts for resolving explicit @agent mentions against
ProjectAgentManifest. This module never creates AgentContract objects, never
creates MiniAgents, never executes handoffs, never activates tools/MCP and never
writes memory.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import re
from typing import Any

from backend.apps.swarms.project_agent_manifest import build_project_agent_manifest


AGENT_MENTION_ROUTING_VERSION = "openswarm.agent_mention_routing.v1"

MENTION_RE = re.compile(r"(?<![\w.])@([A-Za-z][A-Za-z0-9_.-]{0,80})")


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


def _text(value: Any, fallback: str = "", *, limit: int = 800) -> str:
    if value is None:
        return fallback
    result = str(value).strip()
    if not result:
        return fallback
    return result[:limit]


def _as_list(value: Any, *, limit: int = 80) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    for item in raw:
        text = _text(item, limit=240)
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
        return [_safe(item) for item in value[:120]]
    if isinstance(value, tuple):
        return [_safe(item) for item in list(value)[:120]]
    if isinstance(value, str):
        lowered = value.lower()
        if any(hint in lowered for hint in {"api_key=", "password=", "bearer ", "begin private key"}):
            return "[redacted]"
        return value[:2000]
    return value


def _slug(value: Any, fallback: str = "agent") -> str:
    text = _text(value, fallback, limit=120).lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text).strip("-")
    return text or fallback


def _manifest_dict(manifest: Any) -> dict[str, Any]:
    if manifest is None:
        return build_project_agent_manifest().metadata and {}
    if is_dataclass(manifest):
        return _safe(asdict(manifest))
    if isinstance(manifest, dict):
        return _safe(dict(manifest))
    return {}


@dataclass(frozen=True)
class AgentMentionParseResult:
    source_kind: str = "agent_mention_routing"
    mention_kind: str = "agent_mention_parse_result"
    routing_version: str = AGENT_MENTION_ROUTING_VERSION
    raw_message_preview: str = ""
    mentions: list[str] = field(default_factory=list)
    normalized_mentions: list[str] = field(default_factory=list)
    has_mentions: bool = False
    can_execute: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class AgentMentionResolverResult:
    source_kind: str = "agent_mention_routing"
    resolver_kind: str = "agent_mention_resolver_result"
    routing_version: str = AGENT_MENTION_ROUTING_VERSION
    requested_mentions: list[str] = field(default_factory=list)
    resolved_agents: list[dict[str, Any]] = field(default_factory=list)
    unresolved_mentions: list[str] = field(default_factory=list)
    alias_index: dict[str, str] = field(default_factory=dict)
    manifest_hash: str = "unknown"
    decision: str = "not_decided"
    required_actions: list[str] = field(default_factory=list)
    can_create_agent: bool = False
    can_create_miniagent: bool = False
    can_execute_handoffs: bool = False
    can_activate_tools: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class AgentDirectRouteCandidate:
    source_kind: str = "agent_mention_routing"
    route_kind: str = "agent_direct_route_candidate"
    routing_version: str = AGENT_MENTION_ROUTING_VERSION
    target_agent_id: str = ""
    target_alias: str = ""
    target_role: str = ""
    route_status: str = "needs_review"
    route_reason: str = ""
    user_message_preview: str = ""
    routing_mode: str = "direct_agent_route_candidate"
    bypass_full_replanning: bool = True
    keep_swarm_trace: bool = True
    policy_matrix_required: bool = True
    context_packets_required: bool = True
    handoff_required: bool = True
    evidence_required: bool = True
    approval_required: bool = True
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_create_agent: bool = False
    can_create_miniagent: bool = False
    can_execute_handoffs: bool = False
    can_activate_tools: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class AgentMentionLoopGuard:
    source_kind: str = "agent_mention_routing"
    guard_kind: str = "agent_mention_loop_guard"
    routing_version: str = AGENT_MENTION_ROUTING_VERSION
    source_agent_id: str = ""
    target_agent_id: str = ""
    recent_route_targets: list[str] = field(default_factory=list)
    max_same_target_routes: int = 2
    loop_detected: bool = False
    blocked: bool = False
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False


@dataclass(frozen=True)
class AgentMentionRoutingDecision:
    source_kind: str = "agent_mention_routing"
    decision_kind: str = "agent_mention_routing_decision"
    routing_version: str = AGENT_MENTION_ROUTING_VERSION
    decision: str = "needs_review"
    target_agent_id: str = ""
    target_alias: str = ""
    target_role: str = ""
    unresolved_mentions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    route_candidate: dict[str, Any] = field(default_factory=dict)
    loop_guard: dict[str, Any] = field(default_factory=dict)
    process_trace_required: bool = True
    policy_matrix_required: bool = True
    context_packets_required: bool = True
    handoff_required: bool = True
    evidence_required: bool = True
    approval_required: bool = True
    can_execute: bool = False
    can_create_agent: bool = False
    can_create_miniagent: bool = False
    can_execute_handoffs: bool = False
    can_activate_tools: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


def parse_agent_mentions(message: str) -> AgentMentionParseResult:
    raw = _text(message, limit=4000)
    mentions: list[str] = []
    normalized: list[str] = []
    for match in MENTION_RE.finditer(raw):
        label = match.group(1).rstrip("._-")
        if not label:
            continue
        mention = f"@{label}"
        norm = f"@{_slug(label)}"
        if mention not in mentions:
            mentions.append(mention)
        if norm not in normalized:
            normalized.append(norm)
    return AgentMentionParseResult(
        raw_message_preview=str(_safe(raw[:400])),
        mentions=mentions,
        normalized_mentions=normalized,
        has_mentions=bool(mentions),
    )


def resolve_agent_mentions(
    *,
    message: str = "",
    manifest: Any = None,
) -> AgentMentionResolverResult:
    parsed = parse_agent_mentions(message)
    manifest_data = _manifest_dict(manifest)
    if not manifest_data:
        built = build_project_agent_manifest()
        manifest_data = asdict(built)

    routing = manifest_data.get("skill_routing_table") if isinstance(manifest_data.get("skill_routing_table"), dict) else {}
    alias_index = routing.get("alias_index") if isinstance(routing.get("alias_index"), dict) else {}
    capability = manifest_data.get("capability_matrix") if isinstance(manifest_data.get("capability_matrix"), dict) else {}
    agents = capability.get("agents") if isinstance(capability.get("agents"), dict) else {}
    manifest_hash = _text(manifest_data.get("source_hash"), "unknown", limit=160)

    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    required_actions: list[str] = []

    for mention in parsed.normalized_mentions:
        agent_id = _text(alias_index.get(mention), "", limit=160)
        if not agent_id:
            unresolved.append(mention)
            continue
        agent = agents.get(agent_id) if isinstance(agents.get(agent_id), dict) else {}
        resolved.append(_safe({
            "mention": mention,
            "agent_id": agent_id,
            "role": agent.get("role") or "DeclaredAgent",
            "aliases": agent.get("aliases") or [mention],
            "capability_tags": agent.get("capability_tags") or [],
            "allowed_tools": agent.get("allowed_tools") or [],
            "skill_refs": agent.get("skill_refs") or [],
            "memory_access": agent.get("memory_access") or "read_only",
            "materialization_status": agent.get("materialization_status") or "declared",
            "can_create_agent": False,
            "can_activate_tools": False,
            "can_write_memory": False,
        }))

    if unresolved:
        required_actions.append("resolve_unregistered_agent_mentions")
    if len(resolved) > 1:
        required_actions.append("choose_single_target_agent")
    if resolved:
        required_actions.extend([
            "prepare_context_packet_for_target_agent",
            "prepare_handoff_payload_for_target_agent",
            "record_agent_route_process_trace",
            "apply_policy_matrix_before_execution",
        ])
    elif parsed.has_mentions:
        required_actions.append("define_agent_in_project_agent_manifest")
    else:
        required_actions.append("no_agent_mention_detected")

    decision = "unresolved" if unresolved else "resolved" if len(resolved) == 1 else "ambiguous" if len(resolved) > 1 else "no_mentions"

    return AgentMentionResolverResult(
        requested_mentions=parsed.normalized_mentions,
        resolved_agents=resolved,
        unresolved_mentions=unresolved,
        alias_index=_safe(alias_index),
        manifest_hash=manifest_hash,
        decision=decision,
        required_actions=required_actions,
    )


def build_agent_route_candidate(
    *,
    message: str,
    manifest: Any,
    source_agent_id: str = "",
    recent_route_targets: list[str] | None = None,
) -> AgentDirectRouteCandidate:
    resolved = resolve_agent_mentions(message=message, manifest=manifest)
    target = resolved.resolved_agents[0] if len(resolved.resolved_agents) == 1 and not resolved.unresolved_mentions else {}
    target_agent_id = _text(target.get("agent_id"), "", limit=160)
    target_alias = _text((target.get("aliases") or [""])[0], "", limit=160) if target else ""
    target_role = _text(target.get("role"), "", limit=160)
    guard = build_agent_mention_loop_guard(
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        recent_route_targets=recent_route_targets or [],
    )
    required_actions = list(resolved.required_actions)
    if guard.blocked:
        required_actions.extend(guard.required_actions)

    if not target_agent_id:
        status = "blocked"
        reason = "No single declared target agent was resolved from ProjectAgentManifest."
    elif guard.blocked:
        status = "blocked"
        reason = "Loop guard blocked repeated routing to the same agent."
    else:
        status = "needs_review"
        reason = "Direct route candidate prepared against ProjectAgentManifest; execution still requires gates."

    return AgentDirectRouteCandidate(
        target_agent_id=target_agent_id,
        target_alias=target_alias,
        target_role=target_role,
        route_status=status,
        route_reason=reason,
        user_message_preview=str(_safe(_text(message, limit=400))),
        required_actions=required_actions,
    )


def build_agent_mention_loop_guard(
    *,
    source_agent_id: str = "",
    target_agent_id: str = "",
    recent_route_targets: list[str] | None = None,
    max_same_target_routes: int = 2,
) -> AgentMentionLoopGuard:
    recent = [_slug(item) for item in (recent_route_targets or []) if _text(item)]
    target = _slug(target_agent_id, "")
    repeated = sum(1 for item in recent[-max_same_target_routes:] if item == target) if target else 0
    blocked = bool(target and repeated >= max_same_target_routes)
    required_actions = ["review_agent_routing_loop"] if blocked else []
    return AgentMentionLoopGuard(
        source_agent_id=_text(source_agent_id, limit=160),
        target_agent_id=target,
        recent_route_targets=recent,
        max_same_target_routes=max_same_target_routes,
        loop_detected=blocked,
        blocked=blocked,
        required_actions=required_actions,
    )


def decide_agent_mention_route(
    *,
    message: str,
    manifest: Any,
    source_agent_id: str = "",
    recent_route_targets: list[str] | None = None,
) -> AgentMentionRoutingDecision:
    resolved = resolve_agent_mentions(message=message, manifest=manifest)
    candidate = build_agent_route_candidate(
        message=message,
        manifest=manifest,
        source_agent_id=source_agent_id,
        recent_route_targets=recent_route_targets or [],
    )
    loop_guard = build_agent_mention_loop_guard(
        source_agent_id=source_agent_id,
        target_agent_id=candidate.target_agent_id,
        recent_route_targets=recent_route_targets or [],
    )

    blockers: list[str] = []
    required_actions = list(dict.fromkeys(resolved.required_actions + candidate.required_actions + loop_guard.required_actions))

    if resolved.unresolved_mentions:
        blockers.append("unresolved_agent_mentions")
    if len(resolved.resolved_agents) > 1:
        blockers.append("ambiguous_multiple_agent_mentions")
    if loop_guard.blocked:
        blockers.append("agent_routing_loop_detected")
    if not candidate.target_agent_id and parse_agent_mentions(message).has_mentions:
        blockers.append("no_declared_target_agent")
    if not parse_agent_mentions(message).has_mentions:
        blockers.append("no_agent_mention_detected")

    decision = "blocked" if blockers else "needs_review"

    return AgentMentionRoutingDecision(
        decision=decision,
        target_agent_id=candidate.target_agent_id,
        target_alias=candidate.target_alias,
        target_role=candidate.target_role,
        unresolved_mentions=resolved.unresolved_mentions,
        blockers=blockers,
        required_actions=required_actions,
        route_candidate=asdict(candidate),
        loop_guard=asdict(loop_guard),
    )


def dump_agent_mention_routing(value: Any) -> dict[str, Any]:
    return _safe(value)
