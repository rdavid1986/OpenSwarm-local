"""Side-effect controlled persistence for SkillSpecCandidate records."""

from __future__ import annotations

import json
from pathlib import Path

from backend.apps.skills.models import SkillSpecCandidate
from backend.config.paths import DATA_ROOT


DEFAULT_SKILL_CANDIDATE_DIR = Path(DATA_ROOT) / "skill_candidates"


class SkillCandidateStore:
    """Small JSON store for reviewable skill candidates.

    This store persists candidates only. It does not install skills, approve
    candidates, validate evidence, or mutate the legacy skill registry.
    """

    def __init__(self, root: Path | str = DEFAULT_SKILL_CANDIDATE_DIR):
        self.root = Path(root)

    def _path(self, candidate_id: str) -> Path:
        safe_id = str(candidate_id or "").strip()
        if not safe_id:
            raise ValueError("candidate_id is required")
        return self.root / f"{safe_id}.json"

    def save(self, candidate: SkillSpecCandidate) -> SkillSpecCandidate:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(candidate.candidate_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(candidate.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(path)
        return candidate

    def load(self, candidate_id: str) -> SkillSpecCandidate:
        path = self._path(candidate_id)
        if not path.exists():
            raise FileNotFoundError(candidate_id)
        return SkillSpecCandidate(**json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[SkillSpecCandidate]:
        if not self.root.exists():
            return []
        candidates: list[SkillSpecCandidate] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                candidates.append(SkillSpecCandidate(**json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return candidates
