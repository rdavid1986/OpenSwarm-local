"""TestClient smoke for one experimental DAG task.

This uses a fake OllamaAdapter-compatible provider, so it does not require a
running backend process or Ollama. It validates the API path, artifact
registration, structured messages, and that reviewer/consolidation tasks remain
pending.
"""

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

from backend.apps.agents.providers.ollama_adapter import OllamaAdapter  # noqa: E402
from backend.apps.agents.runtime.experimental_dag_task_runner import ExperimentalDAGTaskRunner  # noqa: E402
from backend.apps.agents.runtime.provider import ProviderEvent, ProviderTurnContext  # noqa: E402
from backend.apps.swarms import swarms as swarms_module  # noqa: E402
from backend.main import app  # noqa: E402


class FakeDAGOllamaAdapter(OllamaAdapter):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.pop("allow_network", None)
        super().__init__(allow_network=False, **kwargs)
        self.script = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "fake-write-1",
                            "function": {
                                "name": "write_file",
                                "arguments": {"path": "README.md", "content": "# OpenSwarm\n\nSmoke artifact.\n"},
                            },
                        }
                    ],
                }
            },
            {"message": {"role": "assistant", "content": "README.md creado con evidencia."}},
        ]

    def healthcheck(self, timeout_seconds: float = 2.0) -> dict[str, Any]:
        return {"ok": True, "mock": True}

    async def run_turn(self, context: ProviderTurnContext) -> AsyncIterator[ProviderEvent]:
        item = self.script.pop(0) if self.script else {"message": {"role": "assistant", "content": "done"}}
        yield ProviderEvent(
            type="provider_request",
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={"provider": self.id, "mock": True},
        )
        for event in self.parse_response_events(item, context):
            yield event


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-dag-testclient-")).resolve()
    diagnostics: dict[str, Any] = {"workspace_path": str(workspace)}

    swarms_module.experimental_dag_task_runner = ExperimentalDAGTaskRunner(
        store=swarms_module.swarm_orchestrator.store,
        adapter_factory=FakeDAGOllamaAdapter,
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
        swarm_body = swarm.json()
        swarm_id = swarm_body["id"]
        diagnostics["swarm_id"] = swarm_id

        tasks = client.get(f"/api/swarms/{swarm_id}/tasks", headers=headers).json()["tasks"]
        write_task = choose_task(tasks, "Create README.md")
        diagnostics["write_task_id"] = write_task["id"]

        result = client.post(
            f"/api/swarms/{swarm_id}/experimental/run-task/{write_task['id']}",
            headers=headers,
            json={
                "model": "qwen2.5-coder:14b",
                "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
                "workspace_path": str(workspace),
                "max_turns": 4,
            },
        )
        if result.status_code != 200:
            return fail("run_task_failed", result.text, diagnostics)
        diagnostics["result"] = result.json()

        final_tasks = client.get(f"/api/swarms/{swarm_id}/tasks", headers=headers).json()["tasks"]
        artifacts = client.get(f"/api/swarms/{swarm_id}/artifacts", headers=headers).json()["artifacts"]
        messages = client.get(f"/api/swarms/{swarm_id}/messages", headers=headers).json()["messages"]
        review_task = choose_task(final_tasks, "Review README.md")
        consolidate_task = choose_task(final_tasks, "Consolidate final evidence")

    readme = workspace / "README.md"
    diagnostics["readme_exists"] = readme.exists()
    diagnostics["artifacts"] = artifacts
    diagnostics["messages"] = [{"type": m.get("type"), "task_id": m.get("task_id"), "artifact_refs": m.get("artifact_refs")} for m in messages]
    diagnostics["review_status"] = review_task.get("status")
    diagnostics["consolidate_status"] = consolidate_task.get("status")

    if diagnostics["result"].get("status") != "completed":
        return fail("task_not_completed", "Expected completed", diagnostics)
    if not readme.exists():
        return fail("readme_missing", "README.md was not physically created", diagnostics)
    if not any(a.get("path") == "README.md" for a in artifacts):
        return fail("artifact_missing", "Expected README.md artifact", diagnostics)
    if not any(m.get("type") == "submit_artifact" for m in messages):
        return fail("submit_artifact_missing", "Expected submit_artifact message", diagnostics)
    if not any(m.get("type") == "request_review" for m in messages):
        return fail("request_review_missing", "Expected request_review message", diagnostics)
    if review_task.get("status") != "pending" or consolidate_task.get("status") != "pending":
        return fail("unexpected_downstream_execution", "Review/Consolidate must remain pending", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def choose_task(tasks: list[dict[str, Any]], title: str) -> dict[str, Any]:
    for task in tasks:
        if task.get("title") == title:
            return task
    raise RuntimeError(f"Task not found: {title}")


def fail(kind: str, message: str, diagnostics: dict[str, Any]) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
