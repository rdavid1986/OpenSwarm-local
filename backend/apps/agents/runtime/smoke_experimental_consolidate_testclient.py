"""TestClient smoke for experimental Worker -> Reviewer -> Consolidate flow."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.apps.agents.runtime.smoke_experimental_worker_review_testclient import FakeChainOllamaAdapter


os.environ["OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME"] = "1"

from backend.apps.agents.runtime.experimental_dag_chain_runner import ExperimentalDAGChainRunner  # noqa: E402
from backend.apps.swarms import swarms as swarms_module  # noqa: E402
from backend.main import app  # noqa: E402


def main() -> int:
    FakeChainOllamaAdapter.instance_count = 0
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-consolidate-")).resolve()
    diagnostics: dict = {"workspace_path": str(workspace)}
    swarms_module.experimental_dag_chain_runner = ExperimentalDAGChainRunner(
        store=swarms_module.swarm_orchestrator.store,
        adapter_factory=FakeChainOllamaAdapter,
    )
    headers = {"x-api-key": "local-dev-token"}

    with TestClient(app) as client:
        swarm = client.post(
            "/api/swarms/create",
            headers=headers,
            json={
                "user_prompt": "Crea un README.md básico en el workspace, revisalo con un agente reviewer y reportá evidencia.",
                "workspace_path": str(workspace),
            },
        )
        if swarm.status_code != 200:
            return fail("create_swarm_failed", swarm.text, diagnostics)
        swarm_id = swarm.json()["id"]
        diagnostics["swarm_id"] = swarm_id

        chain = client.post(
            f"/api/swarms/{swarm_id}/experimental/run-worker-review",
            headers=headers,
            json={
                "model": "qwen2.5-coder:14b",
                "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
                "workspace_path": str(workspace),
                "max_turns": 4,
            },
        )
        if chain.status_code != 200 or not chain.json().get("ok"):
            return fail("worker_review_failed", chain.text, diagnostics)

        consolidated = client.post(f"/api/swarms/{swarm_id}/experimental/consolidate-final", headers=headers, json={})
        if consolidated.status_code != 200:
            return fail("consolidate_failed", consolidated.text, diagnostics)
        body = consolidated.json()

        final_state = client.get(f"/api/swarms/{swarm_id}", headers=headers).json()

    diagnostics["result_summary"] = {
        "ok": body.get("ok"),
        "status": body.get("status"),
        "final_result": body.get("final_result"),
        "final_evidence_count": len(body.get("final_evidence") or []),
    }
    diagnostics["tasks"] = [{"title": t.get("title"), "status": t.get("status")} for t in body.get("tasks", [])]
    diagnostics["artifact_count"] = len(body.get("artifacts") or [])
    diagnostics["message_count"] = len(body.get("messages") or [])
    diagnostics["tool_history_count"] = len(final_state.get("tool_history") or [])
    diagnostics["readme_exists"] = (workspace / "README.md").exists()

    if body.get("status") != "completed" or not body.get("ok"):
        return fail("not_completed", "Expected consolidation completed", diagnostics)
    if task_status(body, "Create README.md") != "completed":
        return fail("worker_not_completed", "Expected Worker completed", diagnostics)
    if task_status(body, "Review README.md") != "completed":
        return fail("reviewer_not_completed", "Expected Reviewer completed", diagnostics)
    if task_status(body, "Consolidate final evidence") != "completed":
        return fail("consolidate_not_completed", "Expected Consolidate completed", diagnostics)
    if not body.get("final_evidence"):
        return fail("final_evidence_missing", "Expected final_evidence", diagnostics)
    if (body.get("final_result") or {}).get("status") != "completed":
        return fail("final_result_missing", "Expected final_result completed", diagnostics)
    if not diagnostics["readme_exists"]:
        return fail("readme_missing", "Expected README.md", diagnostics)
    if not body.get("artifacts") or not final_state.get("tool_history"):
        return fail("state_missing", "Expected artifacts and tool_history intact", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def task_status(body: dict, title: str) -> str | None:
    for task in body.get("tasks") or []:
        if task.get("title") == title:
            return task.get("status")
    return None


def fail(kind: str, message: str, diagnostics: dict) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
