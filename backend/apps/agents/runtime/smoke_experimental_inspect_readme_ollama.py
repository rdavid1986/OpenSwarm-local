"""HTTP smoke for the isolated inspect_readme task type.

Requires a running backend with the experimental dependency runner enabled and
PlannerAgent runtime disabled. This smoke intentionally does not add
inspect_readme to the base README review DAG; it creates a custom SwarmState
containing only Plan task DAG -> Inspect README.md.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from backend.apps.agents.orchestration.models import AgentContract, AgentToAgentMessage, SwarmState, TaskNode
from backend.apps.agents.orchestration.store import swarm_store
from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


BACKEND_URL = os.environ.get("OPENSWARM_SMOKE_BACKEND_URL", "http://127.0.0.1:8324").rstrip("/")


def main() -> int:
    missing = [
        name
        for name in (
            "OPENSWARM_EXPERIMENTAL_MINI_RUNTIME",
            "OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME",
            "OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME",
            "OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME",
            "OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER",
            "OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER",
        )
        if os.environ.get(name) != "1"
    ]
    if missing:
        return fail("feature_flag_missing", f"Set flags: {', '.join(missing)}")
    if os.environ.get("OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME") == "1":
        return fail(
            "planner_runtime_must_be_disabled",
            "Set OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME=0 for this inspect-only DAG smoke.",
        )

    workspace = Path(os.environ.get("OPENSWARM_SMOKE_WORKSPACE", tempfile.mkdtemp(prefix="openswarm-inspect-readme-http-"))).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    readme = workspace / "README.md"
    readme.write_text("# Title\n\nBody line\n", encoding="utf-8")

    diagnostics: dict[str, Any] = {
        "backend_url": BACKEND_URL,
        "workspace_path": str(workspace),
        "readme_path": str(readme),
    }

    try:
        diagnostics["health"] = request_json("GET", "/api/health/check", expect_json=False)
        swarm = create_inspect_swarm(workspace)
        diagnostics["swarm_id"] = swarm.id
        response = request_json(
            "POST",
            f"/api/swarms/{swarm.id}/experimental/run-dag-dependencies",
            {"workspace_path": str(workspace)},
            timeout=120,
        )
        saved = request_json("GET", f"/api/swarms/{swarm.id}")
    except Exception as exc:
        return fail("http_smoke_failed", str(exc), diagnostics)

    inspect_task = next((task for task in saved.get("tasks", []) if task.get("title") == "Inspect README.md"), {})
    inspection = next((item for item in inspect_task.get("evidence", []) if item.get("kind") == "readme_inspection"), {})
    tool_history = saved.get("tool_history", [])

    diagnostics["result_summary"] = {
        "ok": response.get("ok"),
        "status": response.get("status"),
        "execution_order": [
            [item.get("title"), item.get("type"), item.get("action"), item.get("status")]
            for item in response.get("execution_order", [])
        ],
        "inspect_task_status": inspect_task.get("status"),
        "inspection": inspection,
        "tool_history": [(entry.get("tool"), entry.get("status"), entry.get("ok")) for entry in tool_history],
    }
    diagnostics["readme_exists"] = readme.exists()

    if response.get("status") != "completed" or response.get("ok") is not True:
        return fail("runner_not_completed", "Expected runner status completed and ok=true", diagnostics)
    if inspect_task.get("status") != "completed":
        return fail("inspect_task_not_completed", "Expected Inspect README.md completed", diagnostics)
    if inspection.get("kind") != "readme_inspection":
        return fail("inspection_missing", "Expected readme_inspection evidence", diagnostics)
    if inspection.get("path") != "README.md":
        return fail("inspection_path_invalid", "Expected inspection path README.md", diagnostics)
    if inspection.get("has_title") is not True:
        return fail("inspection_title_missing", "Expected has_title=true", diagnostics)
    if int(inspection.get("line_count") or 0) <= 0:
        return fail("inspection_line_count_invalid", "Expected line_count > 0", diagnostics)
    if not any(entry.get("tool") == "Read" and entry.get("status") == "completed" and entry.get("ok") for entry in tool_history):
        return fail("read_tool_history_missing", "Expected Read completed true in tool_history", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def create_inspect_swarm(workspace: Path) -> SwarmState:
    plan_spec = get_experimental_task_spec("plan_reused")
    inspect_spec = get_experimental_task_spec("inspect_readme")
    coordinator = AgentContract(
        role="CoordinatorAgent",
        objective="Coordinate inspect README smoke.",
        allowed_tools=list(plan_spec.allowed_tools),
        output_contract=dict(plan_spec.output_contract),
    )
    inspector = AgentContract(
        role="ReviewerAgent",
        objective="Inspect README.md metadata.",
        allowed_tools=list(inspect_spec.allowed_tools),
        output_contract=dict(inspect_spec.output_contract),
    )
    plan_task = TaskNode(
        title="Plan task DAG",
        objective="Create or reuse a minimal plan for the requested work.",
        assigned_contract_id=coordinator.id,
    )
    inspect_task = TaskNode(
        title="Inspect README.md",
        objective="Inspect README.md metadata.",
        assigned_contract_id=inspector.id,
        depends_on=[plan_task.id],
    )
    swarm = SwarmState(
        title="Inspect README HTTP smoke",
        user_prompt="Inspect README.md",
        workspace_path=str(workspace),
        coordinator_contract_id=coordinator.id,
        contracts=[coordinator, inspector],
        tasks=[plan_task, inspect_task],
        messages=[
            AgentToAgentMessage(
                type="broadcast_to_swarm",
                from_agent_id=coordinator.id,
                payload={"user_prompt": "Inspect README.md"},
                requires_response=False,
            )
        ],
    )
    return swarm_store.save(swarm)


def request_json(method: str, path: str, body: dict[str, Any] | None = None, *, timeout: int = 30, expect_json: bool = True) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Origin": "http://localhost", "x-api-key": "local-dev-token"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return raw if not expect_json else (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {path}: {raw}") from exc


def fail(kind: str, message: str, diagnostics: dict[str, Any] | None = None) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics or {}}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
