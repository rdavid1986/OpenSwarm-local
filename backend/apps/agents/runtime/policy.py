"""Policy Runtime facade.

Phase 7/Policy base centralizes automatic allow/ask/deny decisions without
executing tools. It mirrors existing builtin/MCP permissions so future provider
adapters can use one policy boundary instead of duplicating rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from backend.apps.agents.runtime.tools import ToolRuntime, ToolSpec, tool_runtime


PolicyDecisionValue = Literal["allow", "ask", "deny"]


@dataclass(frozen=True)
class PolicyDecision:
    decision: PolicyDecisionValue
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed_without_human(self) -> bool:
        return self.decision == "allow"

    @property
    def requires_approval(self) -> bool:
        return self.decision == "ask"

    @property
    def denied(self) -> bool:
        return self.decision == "deny"


class PolicyRuntime:
    """Automatic policy checks for tools, paths, and shell commands."""

    def __init__(self, tools: ToolRuntime | None = None) -> None:
        self.tools = tools or tool_runtime

    def decide_tool_use(
        self,
        tool_name: str,
        *,
        active_mcps: list[str] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> PolicyDecision:
        resolution = self.tools.resolve_tool(tool_name, active_mcps=active_mcps)
        if not resolution.found or resolution.tool is None:
            return PolicyDecision("deny", resolution.reason or "unknown tool")

        tool = resolution.tool
        if allowed_tools is not None and tool.kind == "builtin" and tool.name not in allowed_tools:
            return PolicyDecision("deny", f"tool not allowed by current mode/session: {tool.name}")
        if allowed_tools is not None and tool.kind == "mcp":
            mcp_ref = f"mcp:{tool.metadata.get('tool_definition_name')}"
            if mcp_ref not in allowed_tools and tool.name not in allowed_tools:
                return PolicyDecision("deny", f"MCP tool not allowed by current mode/session: {tool.name}")

        if tool.policy == "deny":
            return PolicyDecision("deny", "tool policy is deny", {"tool": tool.name})
        if tool.policy == "ask":
            return PolicyDecision("ask", "tool policy requires human approval", {"tool": tool.name})
        return PolicyDecision("allow", "tool policy allows execution", {"tool": tool.name})

    def validate_workspace_path(self, base_dir: str, candidate_path: str | None) -> PolicyDecision:
        base = Path(base_dir).resolve()
        raw = "." if candidate_path in (None, "") else str(candidate_path)
        if raw.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", raw):
            return PolicyDecision("deny", "absolute paths are not allowed")
        target = (base / raw).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return PolicyDecision("deny", "path escapes workspace")
        return PolicyDecision("allow", "path is inside workspace", {"path": str(target)})

    def validate_command(self, command: str) -> PolicyDecision:
        if not isinstance(command, str) or not command.strip():
            return PolicyDecision("deny", "command is required")

        blocked_fragments = (
            "&&",
            "||",
            "|",
            ">",
            "<",
            ";",
            "`",
            "$(",
            "rm -rf",
            "del /s",
            "format ",
            "shutdown",
            "restart-computer",
            "remove-item",
            "rmdir /s",
            "curl ",
            "wget ",
            "invoke-webrequest",
            "iwr ",
            "powershell ",
            "pwsh ",
            "cmd /c",
        )
        lowered = command.lower()
        for fragment in blocked_fragments:
            if fragment in lowered:
                return PolicyDecision("deny", f"command contains blocked fragment: {fragment}")

        allowed_exact = {
            "npm install",
            "npm run build",
            "npm run dev",
            "npm run test",
            "npm run lint",
            "git status",
            "git status --short",
            "git diff --stat",
            "git diff",
            "git log --oneline",
        }
        allowed_prefixes = (
            "npm run ",
            "python -m py_compile ",
            "node --check ",
        )
        normalized = " ".join(command.split()).lower()
        if normalized in allowed_exact or any(normalized.startswith(prefix) for prefix in allowed_prefixes):
            return PolicyDecision("allow", "command is allowlisted")
        return PolicyDecision("ask", "command is not allowlisted and requires approval")


policy_runtime = PolicyRuntime()
