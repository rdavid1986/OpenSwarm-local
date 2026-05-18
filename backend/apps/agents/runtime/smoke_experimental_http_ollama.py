"""HTTP smoke for the experimental MiniRuntime + real Ollama endpoint.

Requires a running backend started with OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
and a local Ollama model. Defaults target qwen2.5-coder:14b.
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
FLAG_NAME = "OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"


def main() -> int:
    if os.environ.get(FLAG_NAME) != "1":
        return fail("feature_flag_missing", f"Set {FLAG_NAME}=1 before running this smoke.")

    workspace = Path(os.environ.get("OPENSWARM_SMOKE_WORKSPACE", tempfile.mkdtemp(prefix="openswarm-http-ollama-"))).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    diagnostics: dict[str, Any] = {
        "backend_url": BACKEND_URL,
        "model": MODEL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "workspace_path": str(workspace),
    }

    try:
        health = request_json("GET", "/api/health/check", expect_json=False)
        diagnostics["health"] = health
    except Exception as exc:
        return fail("backend_health_failed", str(exc), diagnostics)

    try:
        swarm = request_json("POST", "/api/swarms/create", {
            "user_prompt": "HTTP smoke experimental Ollama MiniRuntime",
            "workspace_path": str(workspace),
        })
        swarm_id = swarm["id"]
        diagnostics["swarm_id"] = swarm_id
    except Exception as exc:
        return fail("create_swarm_failed", str(exc), diagnostics)

    payload = {
        "model": MODEL,
        "task": "Crea un README.md en el workspace usando la tool de escritura. Luego responde con evidencia del archivo creado.",
        "workspace_path": str(workspace),
        "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
        "base_url": OLLAMA_BASE_URL,
        "max_turns": 8,
    }
    diagnostics["run_payload"] = payload

    try:
        result = request_json("POST", f"/api/swarms/{swarm_id}/experimental/run-task", payload, timeout=180)
    except Exception as exc:
        return fail("experimental_run_task_failed", str(exc), diagnostics)

    diagnostics["result_summary"] = {
        "ok": result.get("ok"),
        "status": result.get("status"),
        "turns": result.get("turns"),
        "persisted": result.get("persisted"),
        "tool_history": [(h.get("tool"), h.get("status"), h.get("ok")) for h in result.get("tool_history", [])],
        "errors": result.get("errors", []),
    }

    readme = Path(result.get("workspace_path") or workspace) / "README.md"
    diagnostics["readme_path"] = str(readme)
    diagnostics["readme_exists"] = readme.exists()
    if readme.exists():
        diagnostics["readme_preview"] = readme.read_text(encoding="utf-8", errors="replace")[:500]

    tool_history = result.get("tool_history") or []
    write_completed = any(h.get("tool") == "Write" and h.get("status") == "completed" and h.get("ok") for h in tool_history)
    if result.get("status") != "completed":
        return fail("runtime_not_completed", "Experimental task did not complete.", diagnostics)
    if int(result.get("turns") or 0) < 1:
        return fail("turns_invalid", "Expected turns >= 1.", diagnostics)
    if not write_completed:
        return fail("write_not_completed", "Expected Write completed in tool_history.", diagnostics)
    if not result.get("persisted"):
        return fail("not_persisted", "Expected persisted=true.", diagnostics)
    if not readme.exists():
        return fail("readme_missing", "README.md was not created physically.", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


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
            if not expect_json:
                return raw
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {path}: {raw}") from exc


def fail(kind: str, message: str, diagnostics: dict[str, Any] | None = None) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics or {}}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
