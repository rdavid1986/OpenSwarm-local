"""Experimental Policy Runtime.

Capa mínima para decidir si una tool puede ejecutarse antes de entrar al
ToolRuntime efectivo. No ejecuta tools. No toca AgentManager, Claude SDK,
MCP, Browser tools, InvokeAgent ni UI.

Importante:
No importa tipos desde tools.py en runtime para evitar ciclos:
tools.py -> policies.py -> tools.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


PolicyDecisionStatus = Literal["allowed", "denied", "approval_required"]


@dataclass(frozen=True)
class PolicyDecision:
    status: PolicyDecisionStatus
    allowed: bool
    reason: str | None = None
    tool_name: str | None = None

    @property
    def requires_approval(self) -> bool:
        return self.status == "approval_required"


class PolicyRuntime:
    """Policy facade para tool calls normalizadas."""

    def evaluate_tool_call(
        self,
        *,
        resolution: Any,
        context: Any,
        requested_tool_name: str,
    ) -> PolicyDecision:
        if not getattr(resolution, "found", False) or not getattr(resolution, "tool", None):
            return PolicyDecision(
                status="denied",
                allowed=False,
                reason=getattr(resolution, "reason", None) or "unknown tool",
                tool_name=requested_tool_name,
            )

        spec = resolution.tool

        allowed_tools = getattr(context, "allowed_tools", None)
        metadata = getattr(context, "metadata", None) or {}
        task_type = metadata.get("task_type")
        task_type_allowed_tools = metadata.get("task_type_allowed_tools")
        agent_contract_allowed_tools = metadata.get("agent_contract_allowed_tools")
        spec_name = getattr(spec, "name", None)
        spec_raw_name = getattr(spec, "raw_name", None)

        if task_type_allowed_tools is not None and not self._is_tool_allowed(spec_name, spec_raw_name, task_type_allowed_tools):
            return PolicyDecision(
                status="denied",
                allowed=False,
                reason=f"tool is not allowed by task type registry for {task_type}: {spec_name}",
                tool_name=spec_name,
            )

        if agent_contract_allowed_tools is not None and not self._is_tool_allowed(spec_name, spec_raw_name, agent_contract_allowed_tools):
            return PolicyDecision(
                status="denied",
                allowed=False,
                reason=f"tool is not allowed by agent contract: {spec_name}",
                tool_name=spec_name,
            )

        if allowed_tools is not None and not self._is_tool_allowed(spec_name, spec_raw_name, allowed_tools):
            return PolicyDecision(
                status="denied",
                allowed=False,
                reason=f"tool is not allowed in this context: {spec_name}",
                tool_name=spec_name,
            )

        if getattr(spec, "policy", None) == "deny":
            return PolicyDecision(
                status="denied",
                allowed=False,
                reason="tool policy is deny",
                tool_name=spec_name,
            )

        if metadata.get("policy_resume_approved") is True:
            resume_error = self._validate_resume_approval(
                context=context,
                spec_name=spec_name,
                spec_raw_name=spec_raw_name,
            )
            if resume_error:
                return PolicyDecision(
                    status="denied",
                    allowed=False,
                    reason=resume_error,
                    tool_name=spec_name,
                )
            return PolicyDecision(
                status="allowed",
                allowed=True,
                reason=None,
                tool_name=spec_name,
            )

        if getattr(spec, "policy", None) == "ask" and getattr(context, "require_human_approval", False):
            return PolicyDecision(
                status="approval_required",
                allowed=False,
                reason="tool policy requires human approval",
                tool_name=spec_name,
            )

        return PolicyDecision(
            status="allowed",
            allowed=True,
            reason=None,
            tool_name=spec_name,
        )

    @staticmethod
    def _is_tool_allowed(spec_name: str | None, spec_raw_name: str | None, allowed_tools: Any) -> bool:
        if allowed_tools is None:
            return True
        allowed = set(allowed_tools or [])
        return bool(spec_name in allowed or (spec_raw_name or spec_name) in allowed)

    def _validate_resume_approval(self, *, context: Any, spec_name: str | None, spec_raw_name: str | None) -> str | None:
        metadata = getattr(context, "metadata", None) or {}
        approval_id = metadata.get("approval_id")
        swarm_id = getattr(context, "swarm_id", None)
        if not approval_id:
            return "resume approval_id missing"
        if not swarm_id:
            return "resume swarm_id missing"

        try:
            from backend.apps.agents.orchestration.store import swarm_store

            swarm = swarm_store.load(str(swarm_id))
        except FileNotFoundError:
            return "resume swarm not found"
        except Exception as exc:
            return f"resume approval validation failed: {exc}"

        approval = None
        for item in getattr(swarm, "experimental_approvals", []) or []:
            if isinstance(item, dict) and item.get("id") == approval_id:
                approval = item
                break
        if approval is None:
            return "resume approval not found"
        if approval.get("swarm_id") != swarm_id:
            return "resume approval swarm mismatch"
        if approval.get("status") != "allowed":
            return "resume approval is not allowed"
        if approval.get("tool_name") not in {spec_name, spec_raw_name}:
            return "resume approval tool mismatch"
        if metadata.get("resume_tool_input") != approval.get("tool_input"):
            return "resume approval input mismatch"

        task_id = approval.get("task_id")
        if task_id is not None and task_id != getattr(context, "task_id", None):
            return "resume approval task mismatch"
        agent_id = approval.get("agent_id")
        if agent_id is not None and agent_id != getattr(context, "agent_id", None):
            return "resume approval agent mismatch"

        approval_workspace = approval.get("workspace_path")
        context_workspace = getattr(context, "workspace_path", None)
        if approval_workspace is not None:
            try:
                if Path(str(approval_workspace)).expanduser().resolve() != Path(str(context_workspace)).expanduser().resolve():
                    return "resume approval workspace mismatch"
            except Exception:
                if str(approval_workspace) != str(context_workspace):
                    return "resume approval workspace mismatch"

        allowed_tools = getattr(context, "allowed_tools", None)
        if allowed_tools is not None and not self._is_tool_allowed(spec_name, spec_raw_name, allowed_tools):
            return "resume approval tool is not allowed in this context"
        return None


policy_runtime = PolicyRuntime()
