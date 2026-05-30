from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate
from backend.apps.skills.research_contract import build_skill_candidate_research_contract


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_module, "skill_candidate_store", SkillCandidateStore(root=tmp_path / "skill_candidates"))
    monkeypatch.setattr(skills_module, "SKILLS_DIR", str(tmp_path / "legacy_skills"))
    monkeypatch.setattr(skills_module, "INDEX_PATH", str(tmp_path / "legacy_skills" / ".skills_index.json"))
    app = FastAPI()
    app.include_router(skills_module.skills.router, prefix="/api/skills")
    return TestClient(app)


def _candidate(content: str, name: str = "Research Candidate") -> SkillSpecCandidate:
    return SkillSpecCandidate(
        skill_spec=SkillSpec(name=name, content=content),
        status="validated",
        install_approved=False,
    )


def test_research_contract_is_read_only_and_never_executes_web():
    candidate = _candidate("Build Claude API apps using the current SDK documentation.")
    before = deepcopy(candidate.model_dump(mode="json"))

    contract = build_skill_candidate_research_contract(candidate)

    assert contract["contract_kind"] == "skill_research_contract"
    assert contract["candidate_id"] == candidate.candidate_id
    assert contract["requires_web_research"] is True
    assert contract["research_allowed"] is False
    assert contract["web_research_executed"] is False
    assert contract["can_mutate_candidate"] is False
    assert contract["can_install_skill"] is False
    assert contract["can_activate_tools"] is False
    assert contract["can_activate_mcp"] is False
    assert contract["research_queries"]
    assert candidate.model_dump(mode="json") == before


def test_research_contract_can_report_no_research_needed():
    contract = build_skill_candidate_research_contract(
        _candidate("Teach a repeatable writing workflow with role, methodology, validation, pitfalls, and boundaries.")
    )

    assert contract["requires_web_research"] is False
    assert contract["research_queries"] == []
    assert contract["expected_source_types"] == []


def test_research_contract_endpoint_returns_contract_without_mutating_candidate(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = client.post("/api/skills/candidates/create", json={
        "skill_spec": {
            "name": "Claude API Skill",
            "content": "Build Claude API apps using current SDK documentation.",
            "source_format": "unknown",
            "metadata_confidence": "unknown",
        },
        "source": "skill_builder",
    })
    assert created.status_code == 200
    candidate_id = created.json()["candidate"]["candidate_id"]
    before = client.get(f"/api/skills/candidates/{candidate_id}").json()

    response = client.get(f"/api/skills/candidates/{candidate_id}/research-contract")

    assert response.status_code == 200
    contract = response.json()
    assert contract["contract_kind"] == "skill_research_contract"
    assert contract["candidate_id"] == candidate_id
    assert contract["requires_web_research"] is True
    assert contract["web_research_executed"] is False
    assert contract["research_allowed"] is False

    after = client.get(f"/api/skills/candidates/{candidate_id}").json()
    assert after == before


def test_research_contract_endpoint_missing_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing/research-contract")

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"
