"""Smoke directo del PolicyRuntime integrado en ToolRuntime."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from backend.apps.agents.runtime.events import event_trace_runtime
from backend.apps.agents.runtime.policies import PolicyDecision, PolicyRuntime
from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, ToolRuntime


class ForceApprovalPolicyRuntime(PolicyRuntime):
    def evaluate_tool_call(self, *, resolution, context, requested_tool_name: str) -> PolicyDecision:
        return PolicyDecision(
            status="approval_required",
            allowed=False,
            reason="forced approval for smoke",
            tool_name=requested_tool_name,
        )


def main() -> int:
    event_trace_runtime.clear()
    runtime = ToolRuntime()
    approval_runtime = ToolRuntime(events=event_trace_runtime, policies=ForceApprovalPolicyRuntime())

    with tempfile.TemporaryDirectory(prefix="openswarm-policy-") as tmp:
        workspace = Path(tmp)

        history: list[dict] = []

        unknown = runtime.execute_tool(
            ToolCall(name="NoExiste", input={}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Read", "Write"],
                session_id="policy-smoke",
                swarm_id="policy-smoke",
                task_id="unknown",
            ),
            history=history,
        )

        denied_by_allowed_tools = runtime.execute_tool(
            ToolCall(name="Write", input={"path": "README.md", "content": "x"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Read"],
                session_id="policy-smoke",
                swarm_id="policy-smoke",
                task_id="denied-allowed-tools",
            ),
            history=history,
        )

        allowed = runtime.execute_tool(
            ToolCall(name="Write", input={"path": "README.md", "content": "ok"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Write"],
                session_id="policy-smoke",
                swarm_id="policy-smoke",
                task_id="allowed",
            ),
            history=history,
        )

        inspect_readme_write_denied = runtime.execute_tool(
            ToolCall(name="Write", input={"path": "INSPECT.md", "content": "should-not-write"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Read", "Write"],
                session_id="policy-smoke",
                swarm_id="policy-smoke",
                task_id="inspect-write-denied",
                metadata={
                    "task_type": "inspect_readme",
                    "task_type_allowed_tools": ["Read"],
                    "agent_contract_allowed_tools": ["Read", "Write"],
                },
            ),
            history=history,
        )

        approval_required = approval_runtime.execute_tool(
            ToolCall(name="Write", input={"path": "APPROVAL.md", "content": "should-not-write"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Write"],
                require_human_approval=True,
                session_id="policy-smoke",
                swarm_id="policy-smoke",
                task_id="approval",
            ),
            history=history,
        )

        result = {
            "ok": (
                unknown.status == "denied"
                and denied_by_allowed_tools.status == "denied"
                and inspect_readme_write_denied.status == "denied"
                and allowed.status == "completed"
                and approval_required.status == "approval_required"
                and not (workspace / "INSPECT.md").exists()
                and not (workspace / "APPROVAL.md").exists()
                and event_order_ok("policy-smoke", "allowed", ["tool_approved", "tool_started", "tool_completed"])
                and no_event("policy-smoke", "denied-allowed-tools", "tool_started")
                and no_event("policy-smoke", "inspect-write-denied", "tool_started")
                and no_event("policy-smoke", "approval", "tool_started")
                and all("policy_decision" in item for item in history if item.get("status") in {"denied", "approval_required"})
            ),
            "unknown": unknown.to_history_entry(),
            "denied_by_allowed_tools": denied_by_allowed_tools.to_history_entry(),
            "inspect_readme_write_denied": inspect_readme_write_denied.to_history_entry(),
            "allowed": allowed.to_history_entry(),
            "approval_required": approval_required.to_history_entry(),
            "history_count": len(history),
            "readme_exists": (workspace / "README.md").exists(),
            "inspect_exists": (workspace / "INSPECT.md").exists(),
            "approval_exists": (workspace / "APPROVAL.md").exists(),
            "events": [
                {"type": event.type, "task_id": event.task_id}
                for event in event_trace_runtime.list_swarm_events("policy-smoke")
            ],
        }

    print("########## COPIAR DESDE AQUÍ ##########")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


def event_order_ok(swarm_id: str, task_id: str, expected: list[str]) -> bool:
    actual = [
        event.type
        for event in event_trace_runtime.list_swarm_events(swarm_id)
        if event.task_id == task_id and event.type in expected
    ]
    return actual == expected


def no_event(swarm_id: str, task_id: str, event_type: str) -> bool:
    return all(
        event.type != event_type
        for event in event_trace_runtime.list_swarm_events(swarm_id)
        if event.task_id == task_id
    )


if __name__ == "__main__":
    raise SystemExit(main())
