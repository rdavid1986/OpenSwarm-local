"""Project agent manifest contracts.

This module is side-effect-free. It parses and normalizes declared project
agents, aliases, skill routes, capabilities and drift metadata without creating
AgentContract objects, MiniAgents, handoffs, memory writes, tool activation or
runtime sessions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import re
from typing import Any


PROJECT_AGENT_MANIFEST_VERSION = "openswarm.project_agent_manifest.v1"

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "private_key",
    "authorization",
    "cookie",
    "env",
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


def _dedupe(values: list[Any], *, limit: int = 80) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value, limit=240)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _safe(value: Any) -> Any:
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
    text = re.sub(r"[^a-z0-9_@.-]+", "-", text).strip("-")
    if text.startswith("@"):
        text = text[1:]
    return text or fallback


def _hash_text(text: str) -> str:
    if not text:
        return "unknown"
    return sha256(text.encode("utf-8", errors="ignore")).hexdigest()


@dataclass(frozen=True)
class ProjectAgentManifestEntry:
    entry_kind: str = "project_agent_manifest_entry"
    agent_id: str = "generalist"
    aliases: list[str] = field(default_factory=list)
    role: str = "GeneralistAgent"
    objective: str = "Assist with project work."
    allowed_tools: list[str] = field(default_factory=list)
    skill_refs: list[str] = field(default_factory=list)
    capability_tags: list[str] = field(default_factory=list)
    memory_access: str = "read_only"
    handoff_targets: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    materialization_status: str = "declared"
    can_create_agent: bool = False
    can_create_miniagent: bool = False
    can_activate_tools: bool = False
    can_execute_handoffs: bool = False
    can_write_memory: bool = False


@dataclass(frozen=True)
class ProjectAgentSkillRoutingTable:
    source_kind: str = "project_agent_manifest"
    route_kind: str = "project_agent_skill_routing_table"
    manifest_version: str = PROJECT_AGENT_MANIFEST_VERSION
    routes: dict[str, list[str]] = field(default_factory=dict)
    alias_index: dict[str, str] = field(default_factory=dict)
    lazy_loading_required: bool = True
    context_budget_required: bool = True
    can_load_all_skills: bool = False
    can_activate_tools: bool = False


@dataclass(frozen=True)
class ProjectAgentCapabilityMatrix:
    source_kind: str = "project_agent_manifest"
    capability_kind: str = "project_agent_capability_matrix"
    manifest_version: str = PROJECT_AGENT_MANIFEST_VERSION
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)
    policy_matrix_required: bool = True
    can_create_agent: bool = False
    can_activate_tools: bool = False
    can_write_memory: bool = False


@dataclass(frozen=True)
class ProjectAgentManifestDriftReport:
    source_kind: str = "project_agent_manifest"
    drift_kind: str = "project_agent_manifest_drift_report"
    manifest_version: str = PROJECT_AGENT_MANIFEST_VERSION
    manifest_hash: str = "unknown"
    runtime_agent_count: int = 0
    declared_agent_count: int = 0
    missing_runtime_agents: list[str] = field(default_factory=list)
    undeclared_runtime_agents: list[str] = field(default_factory=list)
    changed_fields: list[str] = field(default_factory=list)
    drift_status: str = "not_checked"
    required_actions: list[str] = field(default_factory=list)
    can_mutate_runtime: bool = False


@dataclass(frozen=True)
class ProjectAgentManifest:
    source_kind: str = "project_agent_manifest"
    manifest_kind: str = "project_agent_manifest"
    manifest_version: str = PROJECT_AGENT_MANIFEST_VERSION
    manifest_id: str = "project-agent-manifest"
    source_uri: str = "unknown"
    source_hash: str = "unknown"
    source_author: str = "unknown"
    source_license: str = "unknown"
    agents: list[dict[str, Any]] = field(default_factory=list)
    skill_routing_table: dict[str, Any] = field(default_factory=dict)
    capability_matrix: dict[str, Any] = field(default_factory=dict)
    drift_report: dict[str, Any] = field(default_factory=dict)
    required_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_create_agent: bool = False
    can_create_miniagent: bool = False
    can_activate_tools: bool = False
    can_write_memory: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def dump_project_agent_manifest(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dataclass_fields__"):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return _safe(dict(value))
    return {"source_kind": "project_agent_manifest", "value": _text(value, limit=200)}


def _entry_from_dict(data: dict[str, Any]) -> ProjectAgentManifestEntry:
    aliases = _dedupe(_as_list(data.get("aliases")))
    explicit_id = _text(data.get("agent_id") or data.get("id") or data.get("name"))
    if not explicit_id and aliases:
        explicit_id = aliases[0]
    agent_id = _slug(explicit_id, "generalist")
    if not aliases:
        aliases = [f"@{agent_id}"]
    aliases = [alias if alias.startswith("@") else f"@{_slug(alias)}" for alias in aliases]
    return ProjectAgentManifestEntry(
        agent_id=agent_id,
        aliases=aliases,
        role=_text(data.get("role"), "GeneralistAgent", limit=120),
        objective=_text(data.get("objective") or data.get("goal") or data.get("description"), "Assist with project work.", limit=500),
        allowed_tools=_dedupe(_as_list(data.get("allowed_tools") or data.get("tools"))),
        skill_refs=_dedupe(_as_list(data.get("skill_refs") or data.get("skills"))),
        capability_tags=_dedupe(_as_list(data.get("capability_tags") or data.get("capabilities"))),
        memory_access=_text(data.get("memory_access"), "read_only", limit=80),
        handoff_targets=[_slug(item) for item in _as_list(data.get("handoff_targets") or data.get("handoffs"))],
        boundaries=_dedupe(_as_list(data.get("boundaries") or ["no_private_reasoning", "no_unapproved_tools", "no_unapproved_memory_writes"])),
        materialization_status=_text(data.get("materialization_status"), "declared", limit=80),
    )


def parse_agent_manifest_text(raw_text: str = "") -> list[ProjectAgentManifestEntry]:
    text = _text(raw_text, limit=12000)
    if not text:
        return []
    entries: list[ProjectAgentManifestEntry] = []
    current: dict[str, Any] | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()

        match = re.match(r"^#{1,4}\s*(?:agent|subagent)\s*[:\-]\s*(.+)$", stripped, flags=re.I)
        alias_match = re.search(r"(@[A-Za-z][A-Za-z0-9_.-]*)", stripped)

        if match:
            if current:
                entries.append(_entry_from_dict(current))
            name = match.group(1).strip()
            alias = alias_match.group(1) if alias_match else ""
            clean_name = name.replace(alias, "").strip() if alias else name
            current = {"name": clean_name, "aliases": [alias] if alias else [f"@{_slug(clean_name)}"]}
            continue

        if current is None and alias_match and ("agent" in lowered or "role" in lowered):
            current = {"name": alias_match.group(1), "aliases": [alias_match.group(1)]}

        if current is None:
            continue

        if lowered.startswith(("role:", "- role:")):
            current["role"] = stripped.split(":", 1)[1].strip()
        elif lowered.startswith(("objective:", "- objective:", "goal:", "- goal:")):
            current["objective"] = stripped.split(":", 1)[1].strip()
        elif lowered.startswith(("tools:", "- tools:", "allowed_tools:", "- allowed_tools:")):
            current["allowed_tools"] = [part.strip(" ,") for part in stripped.split(":", 1)[1].split(",")]
        elif lowered.startswith(("skills:", "- skills:", "skill_refs:", "- skill_refs:")):
            current["skill_refs"] = [part.strip(" ,") for part in stripped.split(":", 1)[1].split(",")]
        elif lowered.startswith(("capabilities:", "- capabilities:")):
            current["capability_tags"] = [part.strip(" ,") for part in stripped.split(":", 1)[1].split(",")]
        elif lowered.startswith(("handoffs:", "- handoffs:", "handoff_targets:", "- handoff_targets:")):
            current["handoff_targets"] = [part.strip(" ,@") for part in stripped.split(":", 1)[1].split(",")]
        elif lowered.startswith(("memory:", "- memory:", "memory_access:", "- memory_access:")):
            current["memory_access"] = stripped.split(":", 1)[1].strip()
        elif alias_match and alias_match.group(1) not in current.get("aliases", []):
            current.setdefault("aliases", []).append(alias_match.group(1))

    if current:
        entries.append(_entry_from_dict(current))

    return entries


def build_skill_routing_table(entries: list[ProjectAgentManifestEntry]) -> ProjectAgentSkillRoutingTable:
    routes: dict[str, list[str]] = {}
    alias_index: dict[str, str] = {}
    for entry in entries:
        for alias in entry.aliases:
            alias_index[alias] = entry.agent_id
        for skill in entry.skill_refs:
            routes.setdefault(skill, [])
            if entry.agent_id not in routes[skill]:
                routes[skill].append(entry.agent_id)
    return ProjectAgentSkillRoutingTable(routes=routes, alias_index=alias_index)


def build_agent_capability_matrix(entries: list[ProjectAgentManifestEntry]) -> ProjectAgentCapabilityMatrix:
    agents: dict[str, dict[str, Any]] = {}
    for entry in entries:
        agents[entry.agent_id] = _safe({
            "role": entry.role,
            "aliases": entry.aliases,
            "capability_tags": entry.capability_tags,
            "allowed_tools": entry.allowed_tools,
            "skill_refs": entry.skill_refs,
            "memory_access": entry.memory_access,
            "handoff_targets": entry.handoff_targets,
            "materialization_status": entry.materialization_status,
            "can_create_agent": False,
            "can_activate_tools": False,
            "can_write_memory": False,
        })
    return ProjectAgentCapabilityMatrix(agents=agents)


def build_manifest_drift_report(
    *,
    manifest_hash: str,
    declared_agents: list[ProjectAgentManifestEntry],
    runtime_agents: list[dict[str, Any]] | None = None,
) -> ProjectAgentManifestDriftReport:
    runtime_agents = runtime_agents or []
    declared_ids = {entry.agent_id for entry in declared_agents}
    runtime_ids = {_slug(agent.get("agent_id") or agent.get("id") or agent.get("name") or agent.get("role"), "runtime-agent") for agent in runtime_agents if isinstance(agent, dict)}
    missing_runtime = sorted(declared_ids - runtime_ids) if runtime_agents else []
    undeclared_runtime = sorted(runtime_ids - declared_ids) if runtime_agents else []
    required_actions: list[str] = []

    if not runtime_agents:
        status = "not_checked"
        required_actions.append("provide_runtime_agents_for_drift_check")
    elif missing_runtime or undeclared_runtime:
        status = "drift_detected"
        required_actions.append("review_manifest_runtime_drift")
    else:
        status = "in_sync"

    return ProjectAgentManifestDriftReport(
        manifest_hash=manifest_hash,
        runtime_agent_count=len(runtime_agents),
        declared_agent_count=len(declared_agents),
        missing_runtime_agents=missing_runtime,
        undeclared_runtime_agents=undeclared_runtime,
        drift_status=status,
        required_actions=required_actions,
    )


def build_project_agent_manifest(
    *,
    raw_text: str = "",
    agents: list[dict[str, Any]] | None = None,
    runtime_agents: list[dict[str, Any]] | None = None,
    source_uri: str = "unknown",
    source_hash: str = "",
    source_author: str = "unknown",
    source_license: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> ProjectAgentManifest:
    parsed_entries = parse_agent_manifest_text(raw_text)
    explicit_entries = [_entry_from_dict(agent) for agent in agents or [] if isinstance(agent, dict)]
    entries = explicit_entries or parsed_entries
    warnings: list[str] = []
    required_actions: list[str] = ["review_project_agent_manifest_before_routing"]

    if not entries:
        entries = [_entry_from_dict({"agent_id": "generalist", "aliases": ["@generalist"], "role": "GeneralistAgent"})]
        warnings.append("manifest_missing_agents_default_generalist_added")
        required_actions.append("define_project_agents")

    manifest_hash = _text(source_hash, fallback="", limit=160) or _hash_text(raw_text + repr([asdict(entry) for entry in entries]))
    routing = build_skill_routing_table(entries)
    matrix = build_agent_capability_matrix(entries)
    drift = build_manifest_drift_report(manifest_hash=manifest_hash, declared_agents=entries, runtime_agents=runtime_agents)

    if not routing.routes:
        warnings.append("skill_routing_table_empty")
        required_actions.append("define_skill_routes_or_accept_lazy_default")

    return ProjectAgentManifest(
        source_uri=_text(source_uri, "unknown", limit=500),
        source_hash=manifest_hash,
        source_author=_text(source_author, "unknown", limit=240),
        source_license=_text(source_license, "unknown", limit=120),
        agents=[asdict(entry) for entry in entries],
        skill_routing_table=asdict(routing),
        capability_matrix=asdict(matrix),
        drift_report=asdict(drift),
        required_actions=_dedupe(required_actions + drift.required_actions),
        warnings=_dedupe(warnings),
        metadata=_safe(metadata or {}),
    )
