from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[3]
PLANS_DIR = ROOT_DIR / "backend" / "data" / "plans"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    slug = slug.strip("-._")
    return slug[:80] or "plan"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _extract_plan_phases(content: str) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: str | None = None

    def flush_current():
        nonlocal current
        if current:
            for key, value in list(current.items()):
                if isinstance(value, list):
                    current[key] = "\n".join(str(v).strip() for v in value if str(v).strip()).strip()
            phases.append(current)
            current = None

    for raw_line in (content or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()
        is_phase = (
            lower.startswith("### fase ")
            or lower.startswith("## fase ")
            or lower.startswith("fase ")
            or re.match(r"^\d+[\.)]\s+", line)
        )

        if is_phase:
            flush_current()
            title = re.sub(r"^#+\s*", "", line)
            title = re.sub(r"^\d+[\.)]\s*", "", title).strip()
            current = {
                "title": title[:120] or f"Fase {len(phases) + 1}",
                "objective": "",
                "actions": "",
                "files": "",
                "validation": "",
                "expected_result": "",
            }
            current_key = None
            continue

        if current is None:
            continue

        key_map = {
            "objetivo": "objective",
            "acciones": "actions",
            "archivos": "files",
            "archivos involucrados": "files",
            "validación": "validation",
            "validacion": "validation",
            "resultado esperado": "expected_result",
            "rollback": "rollback",
        }

        matched = False
        for prefix, key in key_map.items():
            if lower.startswith(prefix + ":") or lower.startswith("- " + prefix + ":"):
                value = line.split(":", 1)[1].strip()
                current[key] = [value] if value else []
                current_key = key
                matched = True
                break

        if matched:
            continue

        if current_key:
            current.setdefault(current_key, [])
            if isinstance(current[current_key], list):
                current[current_key].append(line.lstrip("- ").strip())

    flush_current()
    return phases


def create_plan_from_text(
    title: str,
    content: str,
    *,
    session_id: str | None = None,
    created_by_session_id: str | None = None,
    dashboard_id: str | None = None,
    source_mode: str = "plan",
) -> dict[str, Any]:
    plan_id = f"{_safe_slug(title)}-{uuid4().hex[:8]}"
    plan_dir = PLANS_DIR / plan_id
    artifacts_dir = plan_dir / "artifacts"

    artifacts_dir.mkdir(parents=True, exist_ok=False)

    created_at = _now_iso()

    plan_md = f"""# {title}

{content}
"""

    parsed_phases = _extract_plan_phases(content)

    plan_json = {
        "id": plan_id,
        "title": title,
        "created_at": created_at,
        "updated_at": created_at,
        "session_id": session_id,
        "created_by_session_id": created_by_session_id,
        "dashboard_id": dashboard_id,
        "source_mode": source_mode,
        "status": "draft",
        "current_phase_index": 0,
        "phases": parsed_phases,
        "content": content,
    }

    execution_state = {
        "plan_id": plan_id,
        "status": "not_started",
        "current_phase_index": 0,
        "completed_phase_indexes": [],
        "failed_phase_indexes": [],
        "last_error": None,
        "updated_at": created_at,
    }

    decisions = {
        "plan_id": plan_id,
        "open_decisions": [],
        "resolved_decisions": [],
        "updated_at": created_at,
    }

    validation_log = {
        "plan_id": plan_id,
        "entries": [],
        "updated_at": created_at,
    }

    (plan_dir / "plan.md").write_text(plan_md, encoding="utf-8")
    _write_json(plan_dir / "plan.json", plan_json)
    _write_json(plan_dir / "execution_state.json", execution_state)
    _write_json(plan_dir / "decisions.json", decisions)
    _write_json(plan_dir / "validation_log.json", validation_log)

    return {
        "ok": True,
        "plan_id": plan_id,
        "path": str(plan_dir),
        "files": [
            "plan.md",
            "plan.json",
            "execution_state.json",
            "decisions.json",
            "validation_log.json",
        ],
    }


def get_plan(plan_id: str) -> dict[str, Any]:
    plan_dir = PLANS_DIR / plan_id
    plan_json_path = plan_dir / "plan.json"

    if not plan_json_path.exists():
        return {"ok": False, "error": "Plan not found", "plan_id": plan_id}

    return {
        "ok": True,
        "plan_id": plan_id,
        "path": str(plan_dir),
        "plan": json.loads(plan_json_path.read_text(encoding="utf-8")),
    }


def list_plans(dashboard_id: str | None = None) -> dict[str, Any]:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    for plan_dir in sorted(PLANS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not plan_dir.is_dir():
            continue
        plan_json_path = plan_dir / "plan.json"
        if not plan_json_path.exists():
            continue
        try:
            data = json.loads(plan_json_path.read_text(encoding="utf-8"))
            if dashboard_id is not None and data.get("dashboard_id") != dashboard_id:
                continue

            plan_id = data.get("id")
            title = data.get("title") or plan_id or plan_dir.name
            items.append({
                "id": plan_id,
                "title": title,
                "status": data.get("status"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "path": str(plan_dir),
                "mode_label": "Plan",
                "display_label": f"Plan · {title}",
                "technical_id": plan_id,
                "dashboard_id": data.get("dashboard_id"),
            })
        except Exception as exc:
            items.append({
                "id": plan_dir.name,
                "title": plan_dir.name,
                "status": "error",
                "error": str(exc),
                "path": str(plan_dir),
                "mode_label": "Plan",
                "display_label": f"Plan · {plan_dir.name}",
                "technical_id": plan_dir.name,
            })

    return {"ok": True, "plans": items}


def append_validation_log(
    plan_id: str,
    event: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan_dir = PLANS_DIR / plan_id
    log_path = plan_dir / "validation_log.json"

    if not log_path.exists():
        return {"ok": False, "error": "Validation log not found", "plan_id": plan_id}

    log = json.loads(log_path.read_text(encoding="utf-8"))
    now = _now_iso()

    entry = {
        "event": event,
        "details": details or {},
        "timestamp": now,
    }

    entries = log.get("entries")
    if not isinstance(entries, list):
        entries = []

    entries.append(entry)
    log["entries"] = entries
    log["updated_at"] = now

    _write_json(log_path, log)

    return {
        "ok": True,
        "plan_id": plan_id,
        "entry": entry,
        "validation_log": log,
    }


def update_execution_state(plan_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    plan_dir = PLANS_DIR / plan_id
    state_path = plan_dir / "execution_state.json"
    plan_json_path = plan_dir / "plan.json"

    if not state_path.exists():
        return {"ok": False, "error": "Execution state not found", "plan_id": plan_id}

    state = json.loads(state_path.read_text(encoding="utf-8"))

    allowed_keys = {
        "status",
        "current_phase_index",
        "completed_phase_indexes",
        "failed_phase_indexes",
        "last_error",
        "last_execution_session_id",
    }

    for key, value in patch.items():
        if key in allowed_keys:
            state[key] = value

    updated_at = _now_iso()
    state["updated_at"] = updated_at
    _write_json(state_path, state)

    if plan_json_path.exists():
        plan = json.loads(plan_json_path.read_text(encoding="utf-8"))
        if "status" in patch:
            plan["status"] = state.get("status")
        if "current_phase_index" in patch:
            plan["current_phase_index"] = state.get("current_phase_index")
        if "completed_phase_indexes" in patch:
            plan["completed_phase_indexes"] = state.get("completed_phase_indexes")
        if "failed_phase_indexes" in patch:
            plan["failed_phase_indexes"] = state.get("failed_phase_indexes")
        if "last_error" in patch:
            plan["last_error"] = state.get("last_error")
        if "last_execution_session_id" in patch:
            plan["last_execution_session_id"] = state.get("last_execution_session_id")
        plan["updated_at"] = updated_at
        _write_json(plan_json_path, plan)

    return {
        "ok": True,
        "plan_id": plan_id,
        "execution_state": state,
    }
