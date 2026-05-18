"""TestClient smoke for experimental swarm approval management endpoints."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

os.environ["OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"] = "1"

from backend.apps.agents.runtime.approvals import approval_runtime  # noqa: E402
from backend.apps.agents.runtime.events import event_trace_runtime  # noqa: E402
from backend.apps.agents.runtime.policies import PolicyDecision, PolicyRuntime  # noqa: E402
from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, ToolRuntime  # noqa: E402
from backend.main import app  # noqa: E402


class ForceApprovalPolicyRuntime(PolicyRuntime):
    def evaluate_tool_call(self, *, resolution, context, requested_tool_name: str) -> PolicyDecision:
        return PolicyDecision(
            status="approval_required",
            allowed=False,
            reason="forced approval for experimental approvals smoke",
            tool_name=requested_tool_name,
        )


def main() -> int:
    event_trace_runtime.clear()
    approval_runtime.clear()
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-experimental-approvals-")).resolve()
    diagnostics: dict[str, Any] = {"workspace_path": str(workspace)}
    headers = {"x-api-key": "local-dev-token"}

    with TestClient(app) as client:
        swarm_response = client.post(
            "/api/swarms/create",
            headers=headers,
            json={"user_prompt": "Approval smoke", "workspace_path": str(workspace)},
        )
        if swarm_response.status_code != 200:
            return fail("create_swarm_failed", swarm_response.text, diagnostics)
        swarm_id = swarm_response.json()["id"]
        diagnostics["swarm_id"] = swarm_id

        runtime = ToolRuntime(events=event_trace_runtime, policies=ForceApprovalPolicyRuntime(), approvals=approval_runtime)
        history: list[dict[str, Any]] = []
        first = runtime.execute_tool(
            ToolCall(name="Write", input={"path": "ALLOW.md", "content": "must-not-write"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Write"],
                session_id=f"mini-{swarm_id}",
                swarm_id=swarm_id,
                task_id="approval-allow-task",
                require_human_approval=True,
            ),
            history=history,
        )
        if first.status != "approval_required":
            return fail("approval_not_required", first.to_history_entry(), diagnostics)
        first_id = first.metadata.get("approval_request_id")

        pending = client.get(f"/api/swarms/{swarm_id}/experimental/approvals", headers=headers).json()
        fetched = client.get(f"/api/swarms/{swarm_id}/experimental/approvals/{first_id}", headers=headers).json()
        allowed = client.post(
            f"/api/swarms/{swarm_id}/experimental/approvals/{first_id}/allow",
            headers=headers,
            json={"message": "allow recorded only", "updated_input": {"path": "ALLOW-UPDATED.md"}},
        ).json()
        before_resume_exists = (workspace / "ALLOW.md").exists()
        resumed_response = client.post(
            f"/api/swarms/{swarm_id}/experimental/approvals/{first_id}/resume",
            headers=headers,
        )
        resumed = resumed_response.json()
        second_resume_response = client.post(
            f"/api/swarms/{swarm_id}/experimental/approvals/{first_id}/resume",
            headers=headers,
        )

        second = runtime.execute_tool(
            ToolCall(name="Write", input={"path": "DENY.md", "content": "must-not-write"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Write"],
                session_id=f"mini-{swarm_id}",
                swarm_id=swarm_id,
                task_id="approval-deny-task",
                require_human_approval=True,
            ),
            history=history,
        )
        second_id = second.metadata.get("approval_request_id")
        denied = client.post(
            f"/api/swarms/{swarm_id}/experimental/approvals/{second_id}/deny",
            headers=headers,
            json={"message": "deny recorded"},
        ).json()
        denied_resume_response = client.post(
            f"/api/swarms/{swarm_id}/experimental/approvals/{second_id}/resume",
            headers=headers,
        )
        missing_resume_response = client.post(
            f"/api/swarms/{swarm_id}/experimental/approvals/missing-approval/resume",
            headers=headers,
        )

        final_pending = client.get(f"/api/swarms/{swarm_id}/experimental/approvals?status=pending", headers=headers).json()
        final_swarm = client.get(f"/api/swarms/{swarm_id}", headers=headers).json()
        events = client.get(f"/api/swarms/{swarm_id}/events", headers=headers).json()

    event_types = [item.get("type") for item in events.get("events") or []]
    persisted = final_swarm.get("experimental_approvals") or []
    statuses = {item.get("status") for item in persisted}
    persisted_history = final_swarm.get("tool_history") or []
    real_writes = [
        item for item in persisted_history
        if item.get("tool") == "Write" and item.get("status") == "completed" and item.get("ok")
    ]

    result = {
        "ok": (
            pending.get("pending_count") == 1
            and (fetched.get("approval") or {}).get("id") == first_id
            and allowed.get("ok") is True
            and allowed.get("resume_supported") is True
            and before_resume_exists is False
            and resumed_response.status_code == 200
            and resumed.get("ok") is True
            and (resumed.get("approval") or {}).get("status") == "resumed"
            and second_resume_response.status_code == 409
            and (denied.get("approval") or {}).get("status") == "denied"
            and denied_resume_response.status_code == 400
            and missing_resume_response.status_code == 404
            and final_pending.get("pending_count") == 0
            and statuses == {"resumed", "denied"}
            and (workspace / "ALLOW.md").exists()
            and not (workspace / "ALLOW-UPDATED.md").exists()
            and not (workspace / "DENY.md").exists()
            and len(real_writes) == 1
            and "approval_allowed" in event_types
            and "approval_denied" in event_types
            and "approval_resumed" in event_types
            and "tool_approved" in event_types
            and "tool_started" in event_types
            and "tool_completed" in event_types
            and "tool_denied" in event_types
        ),
        "pending": pending,
        "fetched": fetched,
        "allowed": allowed,
        "resumed": resumed,
        "second_resume_status": second_resume_response.status_code,
        "denied": denied,
        "denied_resume_status": denied_resume_response.status_code,
        "missing_resume_status": missing_resume_response.status_code,
        "final_pending": final_pending,
        "persisted": persisted,
        "event_types": event_types,
        "history": history,
        "persisted_history": persisted_history,
        "files": {
            "allow_exists": (workspace / "ALLOW.md").exists(),
            "allow_updated_exists": (workspace / "ALLOW-UPDATED.md").exists(),
            "deny_exists": (workspace / "DENY.md").exists(),
        },
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def fail(kind: str, message: Any, diagnostics: dict[str, Any]) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
