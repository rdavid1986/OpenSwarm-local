"""HTTP smoke for Worker -> Reviewer -> deterministic final consolidation."""

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
    missing = [
        name for name in (
            "OPENSWARM_EXPERIMENTAL_MINI_RUNTIME",
            "OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME",
            "OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME",
            "OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME",
        )
        if os.environ.get(name) != "1"
    ]
    if missing:
        return fail("feature_flag_missing", f"Set flags: {', '.join(missing)}")

    workspace = Path(os.environ.get("OPENSWARM_SMOKE_WORKSPACE", tempfile.mkdtemp(prefix="openswarm-consolidate-"))).resolve()
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
        chain = request_json("POST", f"/api/swarms/{swarm_id}/experimental/run-worker-review", payload, timeout=240)
        if not chain.get("ok"):
            diagnostics["chain"] = chain
            return fail("worker_review_failed", "Worker+Reviewer did not complete", diagnostics)
        consolidated = request_json("POST", f"/api/swarms/{swarm_id}/experimental/consolidate-final", {}, timeout=60)
        final_state = request_json("GET", f"/api/swarms/{swarm_id}")
    except Exception as exc:
        return fail("http_smoke_failed", str(exc), diagnostics)

    diagnostics["result_summary"] = {
        "ok": consolidated.get("ok"),
        "status": consolidated.get("status"),
        "final_result": consolidated.get("final_result"),
        "final_evidence_count": len(consolidated.get("final_evidence") or []),
    }
    diagnostics["tasks"] = [{"title": t.get("title"), "status": t.get("status")} for t in consolidated.get("tasks", [])]
    diagnostics["artifact_count"] = len(consolidated.get("artifacts") or [])
    diagnostics["message_count"] = len(consolidated.get("messages") or [])
    diagnostics["tool_history_count"] = len(final_state.get("tool_history") or [])
    readme = workspace / "README.md"
    diagnostics["readme_path"] = str(readme)
    diagnostics["readme_exists"] = readme.exists()
    if readme.exists():
        diagnostics["readme_preview"] = readme.read_text(encoding="utf-8", errors="replace")[:500]

    if consolidated.get("status") != "completed" or not consolidated.get("ok"):
        return fail("not_completed", "Expected consolidation completed", diagnostics)
    if task_status(consolidated, "Create README.md") != "completed":
        return fail("worker_not_completed", "Expected Worker completed", diagnostics)
    if task_status(consolidated, "Review README.md") != "completed":
        return fail("reviewer_not_completed", "Expected Reviewer completed", diagnostics)
    if task_status(consolidated, "Consolidate final evidence") != "completed":
        return fail("consolidate_not_completed", "Expected Consolidate completed", diagnostics)
    if not consolidated.get("final_evidence"):
        return fail("final_evidence_missing", "Expected final_evidence", diagnostics)
    if (consolidated.get("final_result") or {}).get("status") != "completed":
        return fail("final_result_missing", "Expected final_result completed", diagnostics)
    if not readme.exists():
        return fail("readme_missing", "Expected README.md", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


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


def task_status(body: dict, title: str) -> str | None:
    for task in body.get("tasks") or []:
        if task.get("title") == title:
            return task.get("status")
    return None


def fail(kind: str, message: str, diagnostics: dict[str, Any] | None = None) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics or {}}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
