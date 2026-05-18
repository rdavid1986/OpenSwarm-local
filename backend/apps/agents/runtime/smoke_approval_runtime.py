"""Smoke del ApprovalRuntime experimental aislado."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from backend.apps.agents.runtime.approvals import ApprovalRuntime
from backend.apps.agents.runtime.events import event_trace_runtime
from backend.apps.agents.orchestration.models import SwarmState
from backend.apps.agents.orchestration.store import swarm_store


def main() -> int:
    event_trace_runtime.clear()
    approvals = ApprovalRuntime(events=event_trace_runtime, store=swarm_store)

    with tempfile.TemporaryDirectory(prefix="openswarm-approval-") as tmp:
        workspace = Path(tmp)
        swarm = swarm_store.save(SwarmState(title="Approval smoke", user_prompt="approval smoke", workspace_path=str(workspace)))
        request = approvals.create_request(
            tool_name="DangerousTool",
            tool_input={"path": "danger.txt"},
            workspace_path=str(workspace),
            session_id="approval-smoke",
            swarm_id=swarm.id,
            task_id="approval-task",
            reason="tool policy requires human approval",
        )

        pending_before = approvals.list_pending(swarm_id=swarm.id)

        allow_decision = approvals.resolve_request(
            request.id,
            swarm_id=swarm.id,
            behavior="allow",
            message="Allowed by smoke test",
        )

        second = approvals.create_request(
            tool_name="DangerousTool",
            tool_input={"path": "danger-deny.txt"},
            workspace_path=str(workspace),
            session_id="approval-smoke",
            swarm_id=swarm.id,
            task_id="approval-task-deny",
            reason="tool policy requires human approval",
        )

        deny_decision = approvals.resolve_request(
            second.id,
            swarm_id=swarm.id,
            behavior="deny",
            message="Denied by smoke test",
        )

        pending_after = approvals.list_pending(swarm_id=swarm.id)
        persisted = approvals.list_approvals(swarm_id=swarm.id)
        decisions = approvals.list_decisions()

    events = [event.to_dict() for event in event_trace_runtime.list_swarm_events(swarm.id)]
    event_types = [event.get("type") for event in events]

    result = {
        "ok": (
            len(pending_before) == 1
            and len(pending_after) == 0
            and allow_decision.behavior == "allow"
            and deny_decision.behavior == "deny"
            and len(decisions) == 2
            and len(persisted) == 2
            and {item.get("status") for item in persisted} == {"allowed", "denied"}
            and "approval_required" in event_types
            and "approval_allowed" in event_types
            and "approval_denied" in event_types
            and "tool_denied" in event_types
        ),
        "request": request.to_dict(),
        "pending_before_count": len(pending_before),
        "pending_after_count": len(pending_after),
        "allow_decision": allow_decision.to_dict(),
        "deny_decision": deny_decision.to_dict(),
        "persisted": persisted,
        "decisions_count": len(decisions),
        "event_types": event_types,
    }

    print("########## COPIAR DESDE AQUÍ ##########")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
