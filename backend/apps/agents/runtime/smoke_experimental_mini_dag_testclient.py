"""TestClient smoke for automatic experimental README mini-DAG."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.apps.agents.runtime.smoke_experimental_worker_review_testclient import FakeChainOllamaAdapter


os.environ["OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER"] = "1"

from backend.apps.agents.runtime.experimental_dag_chain_runner import ExperimentalDAGChainRunner  # noqa: E402
from backend.apps.agents.runtime.experimental_dag_consolidator import ExperimentalDAGConsolidator  # noqa: E402
from backend.apps.agents.runtime.experimental_dag_mini_runner import ExperimentalDAGMiniRunner  # noqa: E402
from backend.apps.swarms import swarms as swarms_module  # noqa: E402
from backend.main import app  # noqa: E402


def main() -> int:
    FakeChainOllamaAdapter.instance_count = 0
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-mini-dag-")).resolve()
    diagnostics: dict[str, Any] = {"workspace_path": str(workspace)}
    chain_runner = ExperimentalDAGChainRunner(
        store=swarms_module.swarm_orchestrator.store,
        adapter_factory=FakeChainOllamaAdapter,
    )
    swarms_module.experimental_dag_mini_runner = ExperimentalDAGMiniRunner(
        store=swarms_module.swarm_orchestrator.store,
        chain_runner=chain_runner,
        consolidator=ExperimentalDAGConsolidator(store=swarms_module.swarm_orchestrator.store),
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

        result = client.post(
            f"/api/swarms/{swarm_id}/experimental/run-mini-dag",
            headers=headers,
            json={
                "model": "qwen2.5-coder:14b",
                "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
                "workspace_path": str(workspace),
                "max_turns": 4,
            },
        )
        if result.status_code != 200:
            return fail("run_mini_dag_failed", result.text, diagnostics)
        body = result.json()

    diagnostics["result_summary"] = {
        "ok": body.get("ok"),
        "status": body.get("status"),
        "final_result": body.get("final_result"),
        "final_evidence_count": len(body.get("final_evidence") or []),
        "tool_history": [(h.get("tool"), h.get("status"), h.get("ok")) for h in body.get("tool_history", [])],
    }
    diagnostics["tasks"] = [{"title": t.get("title"), "status": t.get("status")} for t in body.get("tasks", [])]
    diagnostics["artifacts"] = body.get("artifacts", [])
    diagnostics["messages"] = [{"type": m.get("type"), "artifact_refs": m.get("artifact_refs")} for m in body.get("messages", [])]
    diagnostics["readme_exists"] = (workspace / "README.md").exists()

    if body.get("status") != "completed" or not body.get("ok"):
        return fail("not_completed", "Expected mini DAG completed", diagnostics)
    for title in ("Create README.md", "Review README.md", "Consolidate final evidence"):
        if task_status(body, title) != "completed":
            return fail("task_not_completed", f"Expected {title} completed", diagnostics)
    if not diagnostics["readme_exists"]:
        return fail("readme_missing", "Expected README.md", diagnostics)
    if not any(a.get("path") == "README.md" for a in body.get("artifacts", [])):
        return fail("artifact_missing", "Expected README artifact", diagnostics)
    if not any(m.get("type") == "submit_artifact" for m in body.get("messages", [])):
        return fail("submit_artifact_missing", "Expected submit_artifact", diagnostics)
    if not any(m.get("type") == "request_review" for m in body.get("messages", [])):
        return fail("request_review_missing", "Expected request_review", diagnostics)
    if (body.get("final_result") or {}).get("status") != "completed" or not body.get("final_evidence"):
        return fail("final_missing", "Expected final_result and final_evidence", diagnostics)
    tools = [(h.get("tool"), h.get("ok")) for h in body.get("tool_history", [])]
    if ("Write", True) not in tools or ("Read", True) not in tools:
        return fail("tool_history_missing", "Expected Write and Read in tool_history", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def task_status(body: dict[str, Any], title: str) -> str | None:
    for task in body.get("tasks") or []:
        if task.get("title") == title:
            return task.get("status")
    return None


def fail(kind: str, message: str, diagnostics: dict[str, Any]) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
