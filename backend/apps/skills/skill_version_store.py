"""Controlled JSON store for skill version snapshots."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.config.paths import DATA_ROOT

DEFAULT_SKILL_VERSION_DIR = Path(DATA_ROOT) / "skill_versions"


def _safe_ref(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-")
    if not safe:
        raise ValueError("skill_ref is required")
    return safe


class SkillVersionStore:
    def __init__(self, root: Path | str = DEFAULT_SKILL_VERSION_DIR):
        self.root = Path(root)

    def _dir(self, skill_ref: str) -> Path:
        return self.root / _safe_ref(skill_ref)

    def _path(self, skill_ref: str, snapshot_id: str) -> Path:
        safe_id = _safe_ref(snapshot_id)
        return self._dir(skill_ref) / f"{safe_id}.json"

    def save(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        skill_ref = str(snapshot.get("skill_ref") or "")
        snapshot_id = str(snapshot.get("snapshot_id") or "")
        path = self._path(skill_ref, snapshot_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        return snapshot

    def list(self, skill_ref: str) -> list[dict[str, Any]]:
        folder = self._dir(skill_ref)
        if not folder.exists():
            return []
        snapshots: list[dict[str, Any]] = []
        for path in sorted(folder.glob("*.json")):
            try:
                snapshots.append(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return snapshots

    def load(self, skill_ref: str, snapshot_id: str) -> dict[str, Any]:
        path = self._path(skill_ref, snapshot_id)
        if not path.exists():
            raise FileNotFoundError(snapshot_id)
        return json.loads(path.read_text(encoding="utf-8"))
