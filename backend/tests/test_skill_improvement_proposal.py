from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate
from backend.apps.skills.skill_improvement_proposal import (
    apply_skill_candidate_improvement_proposal,
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



def test_apply_improvement_proposal_requires_explicit_approval():
    candidate = _candidate("Help with tasks using best practices.")

    try:
        apply_skill_candidate_improvement_proposal(candidate, approved=False)
    except ValueError as exc:
        assert str(exc) == "skill_improvement_proposal_requires_explicit_approval"
    else:
        raise AssertionError("expected explicit approval error")


def test_apply_improvement_proposal_updates_only_candidate_content_and_clears_install_approval():
    candidate = _candidate("Help with tasks using best practices.")
    approved_candidate = candidate.model_copy(update={"install_approved": True})
    before_candidate_id = approved_candidate.candidate_id

    updated, proposal = apply_skill_candidate_improvement_proposal(approved_candidate, approved=True)

    assert updated.candidate_id == before_candidate_id
    assert updated.skill_spec.content == proposal["proposed_content"]
    assert updated.skill_spec.content != approved_candidate.skill_spec.content
    assert updated.install_approved is False
    assert approved_candidate.install_approved is True


def test_apply_improvement_proposal_endpoint_requires_approval(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = client.post("/api/skills/candidates/create", json={
        "skill_spec": {
            "name": "Apply Proposal",
            "content": "Help with tasks using best practices.",
            "source_format": "unknown",
            "metadata_confidence": "unknown",
        },
        "source": "skill_builder",
    })
    candidate_id = created.json()["candidate"]["candidate_id"]

    response = client.post(f"/api/skills/candidates/{candidate_id}/improvement-proposal/apply", json={"approved": False})

    assert response.status_code == 409
    assert response.json()["detail"] == "Skill improvement proposal requires explicit approval"


def test_apply_improvement_proposal_endpoint_updates_candidate_without_installing(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = client.post("/api/skills/candidates/create", json={
        "skill_spec": {
            "name": "Apply Proposal",
            "content": "Help with tasks using best practices.",
            "source_format": "unknown",
            "metadata_confidence": "unknown",
        },
        "source": "skill_builder",
    })
    candidate_id = created.json()["candidate"]["candidate_id"]
    before = client.get(f"/api/skills/candidates/{candidate_id}").json()

    response = client.post(f"/api/skills/candidates/{candidate_id}/improvement-proposal/apply", json={"approved": True})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["audit"]["event"] == "skill_candidate_improvement_proposal_applied"
    assert body["candidate"]["candidate_id"] == candidate_id
    assert body["candidate"]["install_approved"] is False
    assert body["candidate"]["skill_spec"]["content"] != before["skill_spec"]["content"]
    assert "# OpenSwarm proposed improvements" in body["candidate"]["skill_spec"]["content"]
    assert body["proposal"]["can_update_candidate"] is False

    listed = client.get("/api/skills/list")
    assert listed.status_code == 200
    assert not any(skill["name"] == "Apply Proposal" for skill in listed.json()["skills"])


def test_apply_improvement_proposal_endpoint_missing_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/skills/candidates/missing/improvement-proposal/apply", json={"approved": True})

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"

def test_improvement_proposal_endpoint_missing_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing/improvement-proposal")

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"


def test_improvement_proposal_integrates_research_evidence_without_mutating_candidate():
    candidate = _candidate("Build Claude API apps using current SDK documentation.")
    candidate = candidate.model_copy(update={
        "research_approved": True,
        "research_evidence": [
            {
                "kind": "web_search_result",
                "query": "Claude API official documentation",
                "backend": "test",
                "results": "[1] Claude API Docs\n    https://docs.anthropic.com/en/api/overview",
                "urls": ["https://docs.anthropic.com/en/api/overview"],
                "executed_at": "2026-05-29T00:00:00+00:00",
            }
        ],
    })
    before = deepcopy(candidate.model_dump(mode="json"))

    proposal = build_skill_candidate_improvement_proposal(candidate)

    assert proposal["uses_research_evidence"] is True
    assert proposal["research_evidence_count"] == 1
    assert "research_evidence" in {item["source"] for item in proposal["proposal_items"]}
    assert "Research grounding" in proposal["proposed_content"]
    assert "https://docs.anthropic.com/en/api/overview" in proposal["proposed_content"]
    assert proposal["preview_diff"]
    assert candidate.model_dump(mode="json") == before


def test_apply_improvement_proposal_can_apply_research_grounded_diff_but_not_install():
    candidate = _candidate("Build Claude API apps using current SDK documentation.")
    candidate = candidate.model_copy(update={
        "research_approved": True,
        "install_approved": True,
        "research_evidence": [
            {
                "kind": "web_search_result",
                "query": "Claude API official documentation",
                "backend": "test",
                "results": "[1] Claude API Docs\n    https://docs.anthropic.com/en/api/overview",
                "urls": ["https://docs.anthropic.com/en/api/overview"],
                "executed_at": "2026-05-29T00:00:00+00:00",
            }
        ],
    })

    updated, proposal = apply_skill_candidate_improvement_proposal(candidate, approved=True)

    assert proposal["uses_research_evidence"] is True
    assert updated.skill_spec.content == proposal["proposed_content"]
    assert "Research grounding" in updated.skill_spec.content
    assert updated.install_approved is False
    assert updated.research_approved is True
    assert updated.research_evidence == candidate.research_evidence
