"""Controlled JSON store for explicit skill effectiveness records."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.config.paths import DATA_ROOT

DEFAULT_SKILL_METRICS_DIR = Path(DATA_ROOT) / "skill_metrics"


def _safe_ref(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-")
    if not safe:
        raise ValueError("skill_ref is required")
    return safe


class SkillMetricsStore:
    def __init__(self, root: Path | str = DEFAULT_SKILL_METRICS_DIR):
        self.root = Path(root)

    def _dir(self, skill_ref: str) -> Path:
        return self.root / _safe_ref(skill_ref)

    def _path(self, skill_ref: str, record_id: str) -> Path:
        return self._dir(skill_ref) / f"{_safe_ref(record_id)}.json"

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        path = self._path(str(record.get("skill_ref") or ""), str(record.get("record_id") or ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        return record

    def list(self, skill_ref: str) -> list[dict[str, Any]]:
        folder = self._dir(skill_ref)
        if not folder.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(folder.glob("*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return records
