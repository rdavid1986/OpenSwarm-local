"""Declarative registry of safe import adapters.

Adapters here are metadata only. They do not execute, normalize, install, or
activate tools/MCP.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

ADAPTER_VERSION = "openswarm.import_adapter.v1"


def _adapter(adapter_id: str, supported_formats: list[str], confidence: float, required_files: list[str], strategy: str, unsupported_features: list[str] | None = None) -> dict[str, Any]:
    return {
        "adapter_id": adapter_id,
        "adapter_version": ADAPTER_VERSION,
        "supported_formats": supported_formats,
        "confidence": confidence,
        "required_files": required_files,
        "optional_files": ["README.md", "metadata.json"],
        "normalization_strategy": strategy,
        "unsupported_features": unsupported_features or [],
        "security_notes": [
            "Declarative adapter only.",
            "Does not execute source material.",
            "Does not install skills or create candidates.",
            "Does not activate tools or MCP.",
        ],
        "validation_requirements": ["preview_validation", "manual_review_before_candidate_creation"],
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }


_ADAPTERS = [
    _adapter("openswarm_skillspec_adapter", ["openswarm_skillspec", "openswarm_legacy_skill"], 0.95, ["SkillSpec JSON or legacy skill metadata"], "validate existing fields and preserve provenance"),
    _adapter("anthropic_skill_adapter", ["anthropic_skill"], 0.9, ["SKILL.md"], "map SKILL.md frontmatter and content to SkillSpec preview"),
    _adapter("claude_skill_adapter", ["claude_skill"], 0.9, ["SKILL.md"], "map Claude skill markdown to SkillSpec preview"),
    _adapter("cursor_rule_adapter", ["cursor_rule"], 0.85, [".cursor/rules or rule text"], "wrap Cursor rules as expert instruction content"),
    _adapter("windsurf_rule_adapter", ["windsurf_rule"], 0.85, [".windsurf/rules or rule text"], "wrap Windsurf rules as expert instruction content"),
    _adapter("copilot_instruction_adapter", ["copilot_instruction"], 0.85, ["copilot-instructions.md"], "wrap Copilot instructions as expert instruction content"),
    _adapter("codex_instruction_adapter", ["codex_instruction"], 0.85, ["AGENTS.md or instruction text"], "wrap Codex instructions as expert instruction content"),
    _adapter("mcp_tool_instruction_adapter", ["mcp_tool_instruction"], 0.75, ["prepared MCP instruction text"], "extract declarative requirements only", ["runtime tool invocation", "server activation"]),
    _adapter("markdown_prompt_pack_adapter", ["markdown_prompt_pack", "skill_pack", "repo", "zip", "folder"], 0.65, ["prepared markdown or manifest metadata"], "combine prepared prompt content into preview", ["archive extraction", "repository fetch"]),
    _adapter("unknown_fallback_adapter", ["unknown"], 0.1, [], "preserve content with low confidence warnings", ["automatic trust", "automatic candidate creation"]),
]


def list_skill_import_adapters() -> list[dict[str, Any]]:
    return deepcopy(_ADAPTERS)


def get_skill_import_adapter(adapter_id: str) -> dict[str, Any] | None:
    for adapter in _ADAPTERS:
        if adapter["adapter_id"] == adapter_id:
            return deepcopy(adapter)
    return None


def select_skill_import_adapter(source_format: str) -> dict[str, Any]:
    fmt = str(source_format or "unknown")
    for adapter in _ADAPTERS:
        if fmt in adapter["supported_formats"]:
            return deepcopy(adapter)
    return deepcopy(_ADAPTERS[-1])
