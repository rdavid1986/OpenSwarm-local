"""Smoke failure paths for experimental approval resume."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

os.environ["OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"] = "1"

from backend.apps.agents.orchestration.orchestrator import swarm_orchestrator  # noqa: E402
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
            reason="forced approval for resume failure smoke",
            tool_name=requested_tool_name,
        )


def main() -> int:
    event_trace_runtime.clear()
    approval_runtime.clear()
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-approval-resume-failures-")).resolve()
    headers = {"x-api-key": "local-dev-token"}

    with TestClient(app) as client:
        swarm_response = client.post(
            "/api/swarms/create",
            headers=headers,
            json={"user_prompt": "Approval resume failure smoke", "workspace_path": str(workspace)},
        )
        if swarm_response.status_code != 200:
            return fail("create_swarm_failed", swarm_response.text)
        swarm_id = swarm_response.json()["id"]

        runtime = ToolRuntime(events=event_trace_runtime, policies=ForceApprovalPolicyRuntime(), approvals=approval_runtime)

        inconsistent_id = _create_allowed(
            client,
            headers,
            runtime,
            swarm_id,
            workspace,
            ToolCall(name="Write", input={"path": "SHOULD_NOT_WRITE.md", "content": "blocked"}),
            task_id="metadata-inconsistent",
        )
        _remove_allowed_tools(swarm_id, inconsistent_id)
        inconsistent_resume = client.post(
            f"/api/swarms/{swarm_id}/experimental/approvals/{inconsistent_id}/resume",
            headers=headers,
        )

        read_failure_id = _create_allowed(
            client,
            headers,
            runtime,
            swarm_id,
            workspace,
            ToolCall(name="Read", input={"path": "MISSING.md"}),
            task_id="read-failure",
        )
        read_failure_resume = client.post(
            f"/api/swarms/{swarm_id}/experimental/approvals/{read_failure_id}/resume",
            headers=headers,
        )

        final_swarm = client.get(f"/api/swarms/{swarm_id}", headers=headers).json()
        events = client.get(f"/api/swarms/{swarm_id}/events", headers=headers).json()

    approvals = {item.get("id"): item for item in final_swarm.get("experimental_approvals") or []}
    event_types = [item.get("type") for item in events.get("events") or []]
    result = {
        "ok": (
            inconsistent_resume.status_code == 200
            and read_failure_resume.status_code == 200
            and (inconsistent_resume.json().get("approval") or {}).get("status") == "resume_failed"
            and (read_failure_resume.json().get("approval") or {}).get("status") == "resume_failed"
            and approvals.get(inconsistent_id, {}).get("resume_result", {}).get("status") == "denied"
            and approvals.get(read_failure_id, {}).get("resume_result", {}).get("status") == "failed"
            and not (workspace / "SHOULD_NOT_WRITE.md").exists()
            and "approval_resume_failed" in event_types
            and "approval_required" in event_types
            and "tool_denied" in event_types
            and "tool_failed" in event_types
        ),
        "inconsistent_resume": inconsistent_resume.json(),
        "read_failure_resume": read_failure_resume.json(),
        "approvals": approvals,
        "event_types": event_types,
        "files": {"should_not_write_exists": (workspace / "SHOULD_NOT_WRITE.md").exists()},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _create_allowed(
    client: TestClient,
    headers: dict[str, str],
    runtime: ToolRuntime,
    swarm_id: str,
    workspace: Path,
    call: ToolCall,
    *,
    task_id: str,
) -> str:
    history: list[dict[str, Any]] = []
    blocked = runtime.execute_tool(
        call,
        ToolExecutionContext(
            workspace_path=str(workspace),
            allowed_tools=[call.name],
            session_id=f"mini-{swarm_id}",
            swarm_id=swarm_id,
            task_id=task_id,
            require_human_approval=True,
        ),
        history=history,
    )
    if blocked.status != "approval_required":
        raise RuntimeError(f"expected approval_required, got {blocked.status}")
    approval_id = blocked.metadata.get("approval_request_id")
    allowed = client.post(f"/api/swarms/{swarm_id}/experimental/approvals/{approval_id}/allow", headers=headers).json()
    if (allowed.get("approval") or {}).get("status") != "allowed":
        raise RuntimeError(f"expected allowed approval: {allowed}")
    return str(approval_id)


def _remove_allowed_tools(swarm_id: str, approval_id: str) -> None:
    swarm = swarm_orchestrator.store.load(swarm_id)
    for approval in swarm.experimental_approvals:
        if isinstance(approval, dict) and approval.get("id") == approval_id:
            approval.setdefault("metadata", {})["allowed_tools"] = []
            break
    swarm_orchestrator.store.save(swarm)


def fail(kind: str, message: Any) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
