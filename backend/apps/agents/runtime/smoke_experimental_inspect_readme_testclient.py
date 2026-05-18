"""Smoke para task type experimental inspect_readme."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.apps.agents.runtime.experimental_dag_dependency_runner import (
    EXPERIMENTAL_DAG_DEPENDENCY_RUNNER_FLAG,
    EXPERIMENTAL_PLANNER_AGENT_RUNTIME_FLAG,
)

os.environ["OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER"] = "1"
os.environ[EXPERIMENTAL_DAG_DEPENDENCY_RUNNER_FLAG] = "1"
os.environ[EXPERIMENTAL_PLANNER_AGENT_RUNTIME_FLAG] = "0"

from backend.main import app  # noqa: E402
from backend.apps.agents.orchestration.models import AgentContract, AgentToAgentMessage, SwarmState, TaskNode  # noqa: E402
from backend.apps.agents.orchestration.store import swarm_store  # noqa: E402
from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec  # noqa: E402


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-inspect-readme-"))
    (workspace / "README.md").write_text("# Title\n\nBody line\n", encoding="utf-8")
    plan_spec = get_experimental_task_spec("plan_reused")
    inspect_spec = get_experimental_task_spec("inspect_readme")

    coordinator = AgentContract(
        role="CoordinatorAgent",
        objective="Coordinate test.",
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
        title="Inspect README smoke",
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
    swarm = swarm_store.save(swarm)

    headers = {"x-api-key": "local-dev-token"}

    with TestClient(app) as client:
        response = client.post(
            f"/api/swarms/{swarm.id}/experimental/run-dag-dependencies",
            headers=headers,
            json={"workspace_path": str(workspace)},
        )
    body = response.json()

    saved = swarm_store.load(swarm.id)
    inspect_saved = next(task for task in saved.tasks if task.id == inspect_task.id)
    inspection = next(
        (item for item in inspect_saved.evidence if item.get("kind") == "readme_inspection"),
        {},
    )

    result = {
        "ok": (
            response.status_code == 200
            and body.get("ok") is True
            and inspect_saved.status == "completed"
            and inspection.get("path") == "README.md"
            and inspection.get("has_title") is True
            and bool(inspection.get("line_count"))
        ),
        "status_code": response.status_code,
        "runner_status": body.get("status"),
        "execution_order": [
            [item.get("title"), item.get("type"), item.get("action"), item.get("status")]
            for item in body.get("execution_order", [])
        ],
        "inspect_task_status": inspect_saved.status,
        "inspection": inspection,
        "tool_history": [
            [entry.get("tool"), entry.get("status"), entry.get("ok")]
            for entry in saved.tool_history
        ],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
