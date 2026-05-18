"""TestClient smoke for experimental Worker -> Reviewer chain."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi.testclient import TestClient


os.environ["OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME"] = "1"

from backend.apps.agents.providers.ollama_adapter import OllamaAdapter  # noqa: E402
from backend.apps.agents.runtime.experimental_dag_chain_runner import ExperimentalDAGChainRunner  # noqa: E402
from backend.apps.agents.runtime.provider import ProviderEvent, ProviderTurnContext  # noqa: E402
from backend.apps.swarms import swarms as swarms_module  # noqa: E402
from backend.main import app  # noqa: E402


class FakeChainOllamaAdapter(OllamaAdapter):
    instance_count = 0

    def __init__(self, **kwargs: Any) -> None:
        kwargs.pop("allow_network", None)
        super().__init__(allow_network=False, **kwargs)
        FakeChainOllamaAdapter.instance_count += 1
        if FakeChainOllamaAdapter.instance_count == 1:
            self.script = [
                tool_response("write_file", {"path": "README.md", "content": "# OpenSwarm\n\nWorker output.\n"}, "fake-write-1"),
                final_response("Worker submitted README.md."),
            ]
        else:
            self.script = [
                tool_response("read_file", {"path": "README.md"}, "fake-read-1"),
                final_response('{"review_result":{"status":"approved","evidence":["README.md read successfully"]}}'),
            ]

    def healthcheck(self, timeout_seconds: float = 2.0) -> dict[str, Any]:
        return {"ok": True, "mock": True}

    async def run_turn(self, context: ProviderTurnContext) -> AsyncIterator[ProviderEvent]:
        item = self.script.pop(0) if self.script else final_response("done")
        yield ProviderEvent(
            type="provider_request",
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={"provider": self.id, "mock": True},
        )
        for event in self.parse_response_events(item, context):
            yield event


def tool_response(name: str, arguments: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": "", "tool_calls": [{"id": call_id, "function": {"name": name, "arguments": arguments}}]}}


def final_response(content: str) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": content}}


def main() -> int:
    FakeChainOllamaAdapter.instance_count = 0
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-worker-review-")).resolve()
    diagnostics: dict[str, Any] = {"workspace_path": str(workspace)}
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

        result = client.post(
            f"/api/swarms/{swarm_id}/experimental/run-worker-review",
            headers=headers,
            json={
                "model": "qwen2.5-coder:14b",
                "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
                "workspace_path": str(workspace),
                "max_turns": 4,
            },
        )
        if result.status_code != 200:
            return fail("run_worker_review_failed", result.text, diagnostics)
        body = result.json()
        tasks = client.get(f"/api/swarms/{swarm_id}/tasks", headers=headers).json()["tasks"]
        messages = client.get(f"/api/swarms/{swarm_id}/messages", headers=headers).json()["messages"]
        artifacts = client.get(f"/api/swarms/{swarm_id}/artifacts", headers=headers).json()["artifacts"]

    diagnostics["result_summary"] = {
        "ok": body.get("ok"),
        "status": body.get("status"),
        "worker_status": (body.get("worker") or {}).get("status"),
        "reviewer_status": (body.get("reviewer") or {}).get("status"),
        "review_result": body.get("review_result"),
        "reviewer_tool_history": [(h.get("tool"), h.get("status"), h.get("ok")) for h in (body.get("reviewer") or {}).get("tool_history", [])],
    }
    diagnostics["tasks"] = [{"title": t.get("title"), "status": t.get("status"), "evidence_count": len(t.get("evidence") or [])} for t in tasks]
    diagnostics["artifacts"] = artifacts
    diagnostics["messages"] = [{"type": m.get("type"), "task_id": m.get("task_id"), "artifact_refs": m.get("artifact_refs")} for m in messages]
    diagnostics["readme_exists"] = (workspace / "README.md").exists()

    worker = task_by_title(tasks, "Create README.md")
    reviewer = task_by_title(tasks, "Review README.md")
    consolidate = task_by_title(tasks, "Consolidate final evidence")
    reviewer_history = (body.get("reviewer") or {}).get("tool_history", [])

    if body.get("status") != "completed" or not body.get("ok"):
        return fail("chain_not_completed", "Expected chain completed", diagnostics)
    if worker.get("status") != "completed" or reviewer.get("status") != "completed":
        return fail("task_status_invalid", "Expected Worker and Reviewer completed", diagnostics)
    if consolidate.get("status") != "pending":
        return fail("consolidate_not_pending", "Expected Consolidate pending", diagnostics)
    if not diagnostics["readme_exists"]:
        return fail("readme_missing", "Expected README.md", diagnostics)
    if not any(a.get("path") == "README.md" for a in artifacts):
        return fail("artifact_missing", "Expected README.md artifact", diagnostics)
    if not any(m.get("type") == "submit_artifact" for m in messages):
        return fail("submit_artifact_missing", "Expected submit_artifact", diagnostics)
    if not any(m.get("type") == "request_review" for m in messages):
        return fail("request_review_missing", "Expected request_review", diagnostics)
    if (body.get("review_result") or {}).get("status") != "approved":
        return fail("review_result_invalid", "Expected approved review_result", diagnostics)
    if not any(h.get("tool") == "Read" and h.get("ok") for h in reviewer_history):
        return fail("reviewer_read_missing", "Expected Reviewer Read tool_history", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def task_by_title(tasks: list[dict[str, Any]], title: str) -> dict[str, Any]:
    for task in tasks:
        if task.get("title") == title:
            return task
    raise RuntimeError(f"Task not found: {title}")


def fail(kind: str, message: str, diagnostics: dict[str, Any]) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
