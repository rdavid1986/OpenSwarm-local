"""Smoke de integración ToolRuntime + PolicyRuntime + ApprovalRuntime."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from backend.apps.agents.runtime.approvals import ApprovalRuntime
from backend.apps.agents.runtime.events import event_trace_runtime
from backend.apps.agents.runtime.policies import PolicyRuntime, PolicyDecision
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
    approvals = ApprovalRuntime(events=event_trace_runtime)
    runtime = ToolRuntime(
        events=event_trace_runtime,
        policies=ForceApprovalPolicyRuntime(),
        approvals=approvals,
    )

    swarm_id = "tool-approval-integration-smoke"

    with tempfile.TemporaryDirectory(prefix="openswarm-tool-approval-") as tmp:
        workspace = Path(tmp)
        history: list[dict] = []

        result = runtime.execute_tool(
            ToolCall(name="Write", input={"path": "README.md", "content": "should-not-write"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Write"],
                session_id=swarm_id,
                swarm_id=swarm_id,
                task_id="approval-required-task",
                require_human_approval=True,
            ),
            history=history,
        )

        pending = approvals.list_pending(swarm_id=swarm_id)
        readme_exists = (workspace / "README.md").exists()

    events = [event.to_dict() for event in event_trace_runtime.list_swarm_events(swarm_id)]
    event_types = [event.get("type") for event in events]

    result_payload = {
        "ok": (
            result.status == "approval_required"
            and not result.ok
            and len(pending) == 1
            and not readme_exists
            and "approval_required" in event_types
            and "tool_started" not in event_types
            and len(history) == 1
            and history[0].get("approval_request_id") == pending[0].get("id")
        ),
        "tool_result": result.to_history_entry(),
        "pending_count": len(pending),
        "pending": pending,
        "readme_exists": readme_exists,
        "event_types": event_types,
        "history": history,
    }

    print("########## COPIAR DESDE AQUÍ ##########")
    print(json.dumps(result_payload, indent=2, ensure_ascii=False))
    return 0 if result_payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
