from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate
from backend.apps.skills.skill_improvement_proposal import (
    build_skill_candidate_improvement_proposal,
)


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_module, "skill_candidate_store", SkillCandidateStore(root=tmp_path / "skill_candidates"))
    monkeypatch.setattr(skills_module, "SKILLS_DIR", str(tmp_path / "legacy_skills"))
    monkeypatch.setattr(skills_module, "INDEX_PATH", str(tmp_path / "legacy_skills" / ".skills_index.json"))
    app = FastAPI()
    app.include_router(skills_module.skills.router, prefix="/api/skills")
    return TestClient(app)


def _candidate(content: str) -> SkillSpecCandidate:
    return SkillSpecCandidate(
        skill_spec=SkillSpec(name="Proposal Candidate", content=content),
        status="validated",
        install_approved=False,
    )


def test_improvement_proposal_is_read_only_and_not_auto_apply():
    candidate = _candidate("Help with tasks using best practices.")
    before = deepcopy(candidate.model_dump(mode="json"))

    proposal = build_skill_candidate_improvement_proposal(candidate)

    assert proposal["proposal_kind"] == "skill_improvement_proposal"
    assert proposal["candidate_id"] == candidate.candidate_id
    assert proposal["safe_to_auto_apply"] is False
    assert proposal["can_generate_diff"] is True
    assert proposal["can_update_candidate"] is False
    assert proposal["preview_diff"].startswith("--- current/SKILL.md")
    assert "# OpenSwarm proposed improvements" in proposal["proposed_content"]
    assert proposal["requires_user_approval"] is True
    assert proposal["proposal_items"]
    assert candidate.model_dump(mode="json") == before


def test_improvement_proposal_diff_preview_is_read_only():
    candidate = _candidate("# Tiny Skill\n\nHelp with tasks using best practices.")
    before = deepcopy(candidate.model_dump(mode="json"))

    proposal = build_skill_candidate_improvement_proposal(candidate)

    assert proposal["can_generate_diff"] is True
    assert proposal["can_update_candidate"] is False
    assert proposal["preview_diff"]
    assert "--- current/SKILL.md" in proposal["preview_diff"]
    assert "+++ proposed/SKILL.md" in proposal["preview_diff"]
    assert "# OpenSwarm proposed improvements" in proposal["proposed_content"]
    assert candidate.model_dump(mode="json") == before



def test_improvement_proposal_groups_review_taxonomy_sources():
    proposal = build_skill_candidate_improvement_proposal(_candidate("Help with tasks using best practices."))

    sources = {item["source"] for item in proposal["proposal_items"]}

    assert "quality_gap" in sources
    assert "openswarm_adaptation" in sources


def test_improvement_proposal_endpoint_returns_proposal_without_mutating_candidate(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    payload = {
        "skill_spec": {
            "name": "Generic Proposal",
            "content": "Help with tasks using best practices.",
            "source_format": "unknown",
            "metadata_confidence": "unknown",
        },
        "source": "skill_builder",
    }
    created = client.post("/api/skills/candidates/create", json=payload)
    assert created.status_code == 200
    candidate_id = created.json()["candidate"]["candidate_id"]
    before = client.get(f"/api/skills/candidates/{candidate_id}").json()

    response = client.get(f"/api/skills/candidates/{candidate_id}/improvement-proposal")

    assert response.status_code == 200
    proposal = response.json()
    assert proposal["proposal_kind"] == "skill_improvement_proposal"
    assert proposal["candidate_id"] == candidate_id
    assert proposal["safe_to_auto_apply"] is False
    assert proposal["can_update_candidate"] is False
    assert proposal["proposal_items"]

    after = client.get(f"/api/skills/candidates/{candidate_id}").json()
    assert after == before


def test_improvement_proposal_endpoint_missing_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing/improvement-proposal")

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"
