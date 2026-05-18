"""HTTP smoke for experimental dependency-ordered README DAG with real Ollama."""

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
    flags = (
        "OPENSWARM_EXPERIMENTAL_MINI_RUNTIME",
        "OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME",
        "OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME",
        "OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME",
        "OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER",
        "OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER",
        "OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME",
    )
    missing = [name for name in flags if os.environ.get(name) != "1"]
    if missing:
        return fail("feature_flag_missing", f"Set flags: {', '.join(missing)}")

    workspace = Path(os.environ.get("OPENSWARM_SMOKE_WORKSPACE", tempfile.mkdtemp(prefix="openswarm-dag-deps-"))).resolve()
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
        payload = {
            "model": MODEL,
            "base_url": OLLAMA_BASE_URL,
            "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
            "max_turns": 8,
            "workspace_path": str(workspace),
        }
        result = request_json("POST", f"/api/swarms/{swarm_id}/experimental/run-dag-dependencies", payload, timeout=300)
        rerun = request_json("POST", f"/api/swarms/{swarm_id}/experimental/run-dag-dependencies", payload, timeout=120)
    except Exception as exc:
        return fail("http_smoke_failed", str(exc), diagnostics)

    readme = workspace / "README.md"
    diagnostics["result_summary"] = summarize(result)
    diagnostics["rerun_summary"] = summarize(rerun)
    diagnostics["readme_path"] = str(readme)
    diagnostics["readme_exists"] = readme.exists()
    if readme.exists():
        diagnostics["readme_preview"] = readme.read_text(encoding="utf-8", errors="replace")[:500]

    error = validate_result(result)
    if error:
        return fail(error[0], error[1], diagnostics)
    error = validate_result(rerun)
    if error:
        return fail(f"rerun_{error[0]}", error[1], diagnostics)
    if len(result.get("artifacts") or []) != len(rerun.get("artifacts") or []):
        return fail("artifact_duplicate", "Rerun changed artifact count", diagnostics)
    if len(result.get("messages") or []) != len(rerun.get("messages") or []):
        return fail("message_duplicate", "Rerun changed message count", diagnostics)
    if not all(item.get("action") == "skipped_completed" for item in rerun.get("execution_order", [])):
        return fail("rerun_not_skipped", "Expected rerun to skip completed tasks", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def validate_result(body: dict[str, Any]) -> tuple[str, str] | None:
    if body.get("status") != "completed" or not body.get("ok"):
        return ("not_completed", "Expected completed")
    for title in ("Plan task DAG", "Create README.md", "Review README.md", "Consolidate final evidence"):
        if task_status(body, title) != "completed":
            return ("task_not_completed", f"Expected {title} completed")
    if not task_has_evidence(body, "Plan task DAG", "planner_result"):
        return ("planner_evidence_missing", "Expected PlannerAgent evidence")
    if (body.get("final_result") or {}).get("status") != "completed" or not body.get("final_evidence"):
        return ("final_missing", "Expected final_result/final_evidence")
    if not any(a.get("path") == "README.md" for a in body.get("artifacts", [])):
        return ("artifact_missing", "Expected README artifact")
    if not any(m.get("type") == "submit_artifact" for m in body.get("messages", [])):
        return ("submit_artifact_missing", "Expected submit_artifact")
    if not any(m.get("type") == "request_review" for m in body.get("messages", [])):
        return ("request_review_missing", "Expected request_review")
    tools = [(h.get("tool"), h.get("ok")) for h in body.get("tool_history", [])]
    if ("Write", True) not in tools or ("Read", True) not in tools:
        return ("tool_history_missing", "Expected Write and Read")
    return None


def summarize(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": body.get("ok"),
        "status": body.get("status"),
        "execution_order": [(i.get("title"), i.get("type"), i.get("action")) for i in body.get("execution_order", [])],
        "tasks": [(t.get("title"), t.get("status")) for t in body.get("tasks", [])],
        "final_result": body.get("final_result"),
        "tool_history": [(h.get("tool"), h.get("status"), h.get("ok")) for h in body.get("tool_history", [])],
        "artifact_count": len(body.get("artifacts") or []),
        "message_count": len(body.get("messages") or []),
    }


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


def task_status(body: dict[str, Any], title: str) -> str | None:
    for task in body.get("tasks") or []:
        if task.get("title") == title:
            return task.get("status")
    return None


def task_has_evidence(body: dict[str, Any], title: str, kind: str) -> bool:
    for task in body.get("tasks") or []:
        if task.get("title") == title:
            return any(item.get("kind") == kind for item in task.get("evidence", []))
    return False


def fail(kind: str, message: str, diagnostics: dict[str, Any] | None = None) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics or {}}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
