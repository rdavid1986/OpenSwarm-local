"""Deterministic subsystem identity registry for ProcessTraceItem."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

SUBSYSTEMS: dict[str, dict[str, str]] = {
    "SwarmCore": {
        "subsystem_id": "SwarmCore",
        "label": "SwarmCore",
        "description": "Multi-agent orchestration.",
        "icon_id": "swarm-core",
        "color_token": "trace.swarm",
        "accent_token": "trace.swarm.accent",
    },
    "ReasoningCore": {
        "subsystem_id": "ReasoningCore",
        "label": "ReasoningCore",
        "description": "Reasoning summaries, thinking traces and decision context.",
        "icon_id": "reasoning-core",
        "color_token": "trace.reasoning",
        "accent_token": "trace.reasoning.accent",
    },
    "ContextCore": {
        "subsystem_id": "ContextCore",
        "label": "ContextCore",
        "description": "Selected context, retrieval packets and active scope.",
        "icon_id": "context-core",
        "color_token": "trace.context",
        "accent_token": "trace.context.accent",
    },
    "MemoryCore": {
        "subsystem_id": "MemoryCore",
        "label": "MemoryCore",
        "description": "Memory and context retrieval.",
        "icon_id": "memory-core",
        "color_token": "trace.memory",
        "accent_token": "trace.memory.accent",
    },
    "SkillCore": {
        "subsystem_id": "SkillCore",
        "label": "SkillCore",
        "description": "Skills used, requested or created.",
        "icon_id": "skill-core",
        "color_token": "trace.skill",
        "accent_token": "trace.skill.accent",
    },
    "ModeCore": {
        "subsystem_id": "ModeCore",
        "label": "ModeCore",
        "description": "Active mode and intent.",
        "icon_id": "mode-core",
        "color_token": "trace.mode",
        "accent_token": "trace.mode.accent",
    },
    "ActionCore": {
        "subsystem_id": "ActionCore",
        "label": "ActionCore",
        "description": "Executable actions, pending actions and user-confirmed operations.",
        "icon_id": "action-core",
        "color_token": "trace.action",
        "accent_token": "trace.action.accent",
    },
    "ToolCore": {
        "subsystem_id": "ToolCore",
        "label": "ToolCore",
        "description": "Tool calls, tool inputs, tool results and tool execution state.",
        "icon_id": "tool-core",
        "color_token": "trace.tool",
        "accent_token": "trace.tool.accent",
    },
    "FileCore": {
        "subsystem_id": "FileCore",
        "label": "FileCore",
        "description": "Files, diffs and workspace changes.",
        "icon_id": "file-core",
        "color_token": "trace.file",
        "accent_token": "trace.file.accent",
    },
    "EvidenceCore": {
        "subsystem_id": "EvidenceCore",
        "label": "EvidenceCore",
        "description": "Evidence, artifacts and sources.",
        "icon_id": "evidence-core",
        "color_token": "trace.evidence",
        "accent_token": "trace.evidence.accent",
    },
    "TraceCore": {
        "subsystem_id": "TraceCore",
        "label": "TraceCore",
        "description": "Worklog, timeline and dropdown traces.",
        "icon_id": "trace-core",
        "color_token": "trace.trace",
        "accent_token": "trace.trace.accent",
    },
    "MetricCore": {
        "subsystem_id": "MetricCore",
        "label": "MetricCore",
        "description": "Timers, duration and baselines.",
        "icon_id": "metric-core",
        "color_token": "trace.metric",
        "accent_token": "trace.metric.accent",
    },
    "HandoffCore": {
        "subsystem_id": "HandoffCore",
        "label": "HandoffCore",
        "description": "MiniAgent handoff.",
        "icon_id": "handoff-core",
        "color_token": "trace.handoff",
        "accent_token": "trace.handoff.accent",
    },
    "MiniAgentCore": {
        "subsystem_id": "MiniAgentCore",
        "label": "MiniAgentCore",
        "description": "MiniAgent task execution and worker-level trace.",
        "icon_id": "miniagent-core",
        "color_token": "trace.miniagent",
        "accent_token": "trace.miniagent.accent",
    },
    "ValidationCore": {
        "subsystem_id": "ValidationCore",
        "label": "ValidationCore",
        "description": "Validation, checks and quality gates.",
        "icon_id": "validation-core",
        "color_token": "trace.validation",
        "accent_token": "trace.validation.accent",
    },
    "OutputCore": {
        "subsystem_id": "OutputCore",
        "label": "OutputCore",
        "description": "Outputs, previews, artifacts and candidate versions.",
        "icon_id": "output-core",
        "color_token": "trace.output",
        "accent_token": "trace.output.accent",
    },
    "ReviewCore": {
        "subsystem_id": "ReviewCore",
        "label": "ReviewCore",
        "description": "Reviewer, integrator and final audit.",
        "icon_id": "review-core",
        "color_token": "trace.review",
        "accent_token": "trace.review.accent",
    },
    "BrowserCore": {
        "subsystem_id": "BrowserCore",
        "label": "BrowserCore",
        "description": "Visible research and navigation.",
        "icon_id": "browser-core",
        "color_token": "trace.browser",
        "accent_token": "trace.browser.accent",
    },
    "ConfigCore": {
        "subsystem_id": "ConfigCore",
        "label": "ConfigCore",
        "description": "Effective configuration.",
        "icon_id": "config-core",
        "color_token": "trace.config",
        "accent_token": "trace.config.accent",
    },
    "ModelCore": {
        "subsystem_id": "ModelCore",
        "label": "ModelCore",
        "description": "Model, provider and capabilities.",
        "icon_id": "model-core",
        "color_token": "trace.model",
        "accent_token": "trace.model.accent",
    },
}

_KIND_TO_SUBSYSTEM = {
    "reasoning": "ReasoningCore",
    "thinking": "ReasoningCore",
    "context": "ContextCore",
    "memory": "MemoryCore",
    "skill": "SkillCore",
    "mode": "ModeCore",
    "action": "ActionCore",
    "tool": "ToolCore",
    "file": "FileCore",
    "diff": "FileCore",
    "workspace": "FileCore",
    "evidence": "EvidenceCore",
    "handoff": "HandoffCore",
    "miniagent": "MiniAgentCore",
    "metric": "MetricCore",
    "review": "ReviewCore",
    "browser": "BrowserCore",
    "config": "ConfigCore",
    "model": "ModelCore",
    "timeline": "TraceCore",
    "worklog": "TraceCore",
    "validation": "ValidationCore",
    "output": "OutputCore",
    "artifact": "OutputCore",
    "summary": "TraceCore",
    "unknown": "TraceCore",
}



def build_subsystem_identity_registry() -> dict[str, dict[str, str]]:
    return deepcopy(SUBSYSTEMS)


def normalize_subsystem_id(value: Any) -> str:
    text = str(value or "").strip()
    for subsystem_id in SUBSYSTEMS:
        if text.lower() == subsystem_id.lower():
            return subsystem_id
    return "TraceCore"


def get_subsystem_identity(subsystem_id: Any) -> dict[str, str]:
    return deepcopy(SUBSYSTEMS[normalize_subsystem_id(subsystem_id)])


def list_subsystem_identities() -> list[dict[str, str]]:
    return [deepcopy(identity) for identity in SUBSYSTEMS.values()]


def subsystem_identity_for_trace_kind(kind: Any) -> dict[str, str]:
    normalized = str(kind or "").strip().lower()
    return get_subsystem_identity(_KIND_TO_SUBSYSTEM.get(normalized, "TraceCore"))


def apply_subsystem_identity_to_trace_item(item: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(item or {})
    current_subsystem = normalize_subsystem_id(updated.get("subsystem")) if updated.get("subsystem") else ""
    kind_identity = subsystem_identity_for_trace_kind(updated.get("kind"))
    identity = get_subsystem_identity(current_subsystem) if current_subsystem and current_subsystem != "TraceCore" else kind_identity
    updated["subsystem"] = identity["subsystem_id"]
    if not updated.get("icon_id"):
        updated["icon_id"] = identity["icon_id"]
    if not updated.get("badge"):
        updated["badge"] = identity["label"]
    metadata = dict(updated.get("metadata") or {})
    metadata.setdefault("subsystem_description", identity["description"])
    metadata.setdefault("color_token", identity["color_token"])
    metadata.setdefault("accent_token", identity["accent_token"])
    updated["metadata"] = metadata
    return updated
