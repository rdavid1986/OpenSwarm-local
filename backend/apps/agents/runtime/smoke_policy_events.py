"""Smoke de eventos semánticos emitidos por PolicyRuntime + ToolRuntime."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from backend.apps.agents.runtime.events import event_trace_runtime
from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, ToolRuntime


def main() -> int:
    event_trace_runtime.clear()
    runtime = ToolRuntime()

    swarm_id = "policy-events-smoke"
    session_id = "policy-events-smoke"

    with tempfile.TemporaryDirectory(prefix="openswarm-policy-events-") as tmp:
        workspace = Path(tmp)

        runtime.execute_tool(
            ToolCall(name="NoExiste", input={}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Read", "Write"],
                session_id=session_id,
                swarm_id=swarm_id,
                task_id="unknown",
            ),
        )

        runtime.execute_tool(
            ToolCall(name="Write", input={"path": "README.md", "content": "x"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Read"],
                session_id=session_id,
                swarm_id=swarm_id,
                task_id="denied-allowed-tools",
            ),
        )

        runtime.execute_tool(
            ToolCall(name="Write", input={"path": "README.md", "content": "ok"}),
            ToolExecutionContext(
                workspace_path=str(workspace),
                allowed_tools=["Write"],
                session_id=session_id,
                swarm_id=swarm_id,
                task_id="allowed",
            ),
        )

    events = [event.to_dict() for event in event_trace_runtime.list_swarm_events(swarm_id)]

    types = {}
    for event in events:
        event_type = event.get("type")
        types[event_type] = types.get(event_type, 0) + 1

    result = {
        "ok": (
            types.get("tool_denied", 0) >= 2
            and types.get("tool_completed", 0) >= 1
            and types.get("tool_failed", 0) == 0
        ),
        "event_count": len(events),
        "types": types,
        "events": [
            {
                "type": event.get("type"),
                "task_id": event.get("task_id"),
                "tool": (event.get("payload") or {}).get("tool"),
                "status": (event.get("payload") or {}).get("status"),
                "ok": (event.get("payload") or {}).get("ok"),
                "error": (event.get("payload") or {}).get("error"),
            }
            for event in events
        ],
    }

    print("########## COPIAR DESDE AQUÍ ##########")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
