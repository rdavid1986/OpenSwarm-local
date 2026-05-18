"""File-backed swarm state store.

Uses backend/data/swarms so it follows the same dev/packaged DATA_ROOT rules
as existing OpenSwarm state. This does not replace plans.py yet.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.apps.agents.orchestration.models import SwarmState, _now_iso
from backend.config.paths import DATA_ROOT


SWARMS_DIR = Path(DATA_ROOT) / "swarms"


class SwarmStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or SWARMS_DIR

    def _path(self, swarm_id: str) -> Path:
        safe = "".join(ch for ch in swarm_id if ch.isalnum() or ch in ("-", "_"))
        if not safe:
            raise ValueError("invalid swarm_id")
        return self.root / safe / "swarm.json"

    def save(self, swarm: SwarmState) -> SwarmState:
        swarm.updated_at = _now_iso()
        path = self._path(swarm.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(swarm.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
        return swarm

    def load(self, swarm_id: str) -> SwarmState:
        path = self._path(swarm_id)
        if not path.exists():
            raise FileNotFoundError(f"Swarm not found: {swarm_id}")
        return SwarmState(**json.loads(path.read_text(encoding="utf-8")))

    def list(self, *, dashboard_id: str | None = None) -> list[dict[str, Any]]:
        self.root.mkdir(parents=True, exist_ok=True)
        items: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*/swarm.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if dashboard_id is not None and data.get("dashboard_id") != dashboard_id:
                continue
            items.append(
                {
                    "id": data.get("id"),
                    "title": data.get("title"),
                    "status": data.get("status"),
                    "dashboard_id": data.get("dashboard_id"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "task_count": len(data.get("tasks") or []),
                    "contract_count": len(data.get("contracts") or []),
                }
            )
        return items


swarm_store = SwarmStore()
