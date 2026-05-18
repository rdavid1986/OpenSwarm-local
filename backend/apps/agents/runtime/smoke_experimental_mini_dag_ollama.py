"""HTTP smoke for automatic experimental README mini-DAG with real Ollama."""

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
            "OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER",
        )
        if os.environ.get(name) != "1"
    ]
    if missing:
        return fail("feature_flag_missing", f"Set flags: {', '.join(missing)}")

    workspace = Path(os.environ.get("OPENSWARM_SMOKE_WORKSPACE", tempfile.mkdtemp(prefix="openswarm-mini-dag-"))).resolve()
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
        result = request_json("POST", f"/api/swarms/{swarm_id}/experimental/run-mini-dag", {
            "model": MODEL,
            "base_url": OLLAMA_BASE_URL,
            "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
            "max_turns": 8,
            "workspace_path": str(workspace),
        }, timeout=300)
    except Exception as exc:
        return fail("http_smoke_failed", str(exc), diagnostics)

    readme = workspace / "README.md"
    diagnostics["result_summary"] = {
        "ok": result.get("ok"),
        "status": result.get("status"),
        "final_result": result.get("final_result"),
        "final_evidence_count": len(result.get("final_evidence") or []),
        "tool_history": [(h.get("tool"), h.get("status"), h.get("ok")) for h in result.get("tool_history", [])],
    }
    diagnostics["tasks"] = [{"title": t.get("title"), "status": t.get("status")} for t in result.get("tasks", [])]
    diagnostics["artifact_count"] = len(result.get("artifacts") or [])
    diagnostics["message_count"] = len(result.get("messages") or [])
    diagnostics["readme_path"] = str(readme)
    diagnostics["readme_exists"] = readme.exists()
    if readme.exists():
        diagnostics["readme_preview"] = readme.read_text(encoding="utf-8", errors="replace")[:500]

    if result.get("status") != "completed" or not result.get("ok"):
        return fail("not_completed", "Expected mini DAG completed", diagnostics)
    for title in ("Create README.md", "Review README.md", "Consolidate final evidence"):
        if task_status(result, title) != "completed":
            return fail("task_not_completed", f"Expected {title} completed", diagnostics)
    if not readme.exists():
        return fail("readme_missing", "Expected README.md", diagnostics)
    if not any(a.get("path") == "README.md" for a in result.get("artifacts", [])):
        return fail("artifact_missing", "Expected README artifact", diagnostics)
    if not any(m.get("type") == "submit_artifact" for m in result.get("messages", [])):
        return fail("submit_artifact_missing", "Expected submit_artifact", diagnostics)
    if not any(m.get("type") == "request_review" for m in result.get("messages", [])):
        return fail("request_review_missing", "Expected request_review", diagnostics)
    if (result.get("final_result") or {}).get("status") != "completed" or not result.get("final_evidence"):
        return fail("final_missing", "Expected final_result and final_evidence", diagnostics)
    tools = [(h.get("tool"), h.get("ok")) for h in result.get("tool_history", [])]
    if ("Write", True) not in tools or ("Read", True) not in tools:
        return fail("tool_history_missing", "Expected Write and Read in tool_history", diagnostics)

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


def task_status(body: dict[str, Any], title: str) -> str | None:
    for task in body.get("tasks") or []:
        if task.get("title") == title:
            return task.get("status")
    return None


def fail(kind: str, message: str, diagnostics: dict[str, Any] | None = None) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics or {}}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
