"""HTTP smoke for running one existing DAG task through experimental MiniRuntime.

Requires backend with:
- OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
- OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1

Defaults target local Ollama qwen2.5-coder:14b.
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

BACKEND_URL = os.environ.get("OPENSWARM_SMOKE_BACKEND_URL", "http://127.0.0.1:8324").rstrip("/")
MODEL = os.environ.get("OPENSWARM_SMOKE_OLLAMA_MODEL", "qwen2.5-coder:14b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def main() -> int:
    missing_flags = [name for name in ("OPENSWARM_EXPERIMENTAL_MINI_RUNTIME", "OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME") if os.environ.get(name) != "1"]
    if missing_flags:
        return fail("feature_flag_missing", f"Set flags: {', '.join(missing_flags)}")

    workspace = Path(os.environ.get("OPENSWARM_SMOKE_WORKSPACE", tempfile.mkdtemp(prefix="openswarm-dag-task-"))).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    diagnostics: dict[str, Any] = {"backend_url": BACKEND_URL, "model": MODEL, "workspace_path": str(workspace)}

    try:
        diagnostics["health"] = request_json("GET", "/api/health/check", expect_json=False)
        swarm = request_json("POST", "/api/swarms/create", {
            "user_prompt": "Crea un README.md básico en el workspace, revisalo con un agente reviewer y reportá evidencia.",
            "workspace_path": str(workspace),
        })
        swarm_id = swarm["id"]
        diagnostics["swarm_id"] = swarm_id
        tasks_response = request_json("GET", f"/api/swarms/{swarm_id}/tasks")
        tasks = tasks_response.get("tasks", [])
        diagnostics["tasks"] = [{"id": t.get("id"), "title": t.get("title"), "status": t.get("status")} for t in tasks]
        task = choose_write_task(tasks)
        task_id = task["id"]
        diagnostics["selected_task"] = {"id": task_id, "title": task.get("title")}
        payload = {
            "model": MODEL,
            "base_url": OLLAMA_BASE_URL,
            "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
            "max_turns": 8,
            "workspace_path": str(workspace),
        }
        result = request_json("POST", f"/api/swarms/{swarm_id}/experimental/run-task/{task_id}", payload, timeout=180)
        diagnostics["result_summary"] = {
            "ok": result.get("ok"),
            "status": result.get("status"),
            "turns": result.get("turns"),
            "persisted": result.get("persisted"),
            "tool_history": [(h.get("tool"), h.get("status"), h.get("ok")) for h in result.get("tool_history", [])],
            "errors": result.get("errors", []),
        }
        final_task = next((t for t in request_json("GET", f"/api/swarms/{swarm_id}/tasks").get("tasks", []) if t.get("id") == task_id), None)
        diagnostics["updated_task"] = final_task
        swarm_state = request_json("GET", f"/api/swarms/{swarm_id}")
        diagnostics["artifacts"] = swarm_state.get("artifacts", [])
        diagnostics["messages"] = [
            {
                "type": message.get("type"),
                "task_id": message.get("task_id"),
                "artifact_refs": message.get("artifact_refs"),
                "requires_response": message.get("requires_response"),
            }
            for message in swarm_state.get("messages", [])
        ]
        diagnostics["review_task"] = next((t for t in request_json("GET", f"/api/swarms/{swarm_id}/tasks").get("tasks", []) if t.get("title") == "Review README.md"), None)
    except Exception as exc:
        return fail("http_smoke_failed", str(exc), diagnostics)

    readme = workspace / "README.md"
    diagnostics["readme_path"] = str(readme)
    diagnostics["readme_exists"] = readme.exists()
    if readme.exists():
        diagnostics["readme_preview"] = readme.read_text(encoding="utf-8", errors="replace")[:500]

    tool_history = diagnostics["result_summary"].get("tool_history", [])
    if diagnostics["result_summary"].get("status") != "completed":
        return fail("runtime_not_completed", "Task did not complete", diagnostics)
    if not any(tool == "Write" and status == "completed" and ok for tool, status, ok in tool_history):
        return fail("write_not_completed", "Expected Write completed", diagnostics)
    if not diagnostics.get("updated_task") or diagnostics["updated_task"].get("status") != "completed":
        return fail("task_not_completed", "Expected TaskNode status completed", diagnostics)
    if not diagnostics["updated_task"].get("evidence"):
        return fail("task_evidence_missing", "Expected task evidence", diagnostics)
    if not any(artifact.get("path") == "README.md" for artifact in diagnostics.get("artifacts", [])):
        return fail("artifact_missing", "Expected README.md artifact", diagnostics)
    if not any(message.get("type") == "submit_artifact" for message in diagnostics.get("messages", [])):
        return fail("submit_artifact_missing", "Expected submit_artifact message", diagnostics)
    if not any(message.get("type") == "request_review" for message in diagnostics.get("messages", [])):
        return fail("request_review_missing", "Expected request_review message", diagnostics)
    if not diagnostics.get("review_task") or diagnostics["review_task"].get("status") != "pending":
        return fail("review_task_not_pending", "Expected Review README.md to remain pending", diagnostics)
    if not readme.exists():
        return fail("readme_missing", "Expected README.md", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def choose_write_task(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    for task in tasks:
        text = f"{task.get('title', '')} {task.get('objective', '')}".lower()
        if "readme" in text and ("create" in text or "crea" in text):
            return task
    raise RuntimeError("Could not find README write task")


def request_json(method: str, path: str, body: dict[str, Any] | None = None, *, timeout: int = 30, expect_json: bool = True) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Origin": "http://localhost"},
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
