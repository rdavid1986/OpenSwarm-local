from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_module, "skill_candidate_store", SkillCandidateStore(root=tmp_path / "skill_candidates"))
    app = FastAPI()
    app.include_router(skills_module.skills.router, prefix="/api/skills")
    return TestClient(app)


def _candidate_payload(name: str = "CSS Validator"):
    return {
        "skill_spec": {
            "name": name,
            "content": "# CSS Validator\n",
            "source_format": "unknown",
            "metadata_confidence": "unknown",
        },
        "source": "skill_builder",
    }


def test_create_list_and_get_skill_candidate_without_installing(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    created = client.post("/api/skills/candidates/create", json=_candidate_payload())
    assert created.status_code == 200
    created_body = created.json()
    candidate_id = created_body["candidate"]["candidate_id"]

    assert created_body["ok"] is True
    assert created_body["candidate"]["status"] == "validated"
    assert created_body["candidate"]["install_approved"] is False
    gate_warning = created_body["candidate"]["warnings"][-1]
    assert gate_warning["code"] == "skill_candidate_gate"
    assert gate_warning["status"] == "blocked"
    assert {reason["code"] for reason in gate_warning["reasons"]} == {"evidence_refs_missing", "policy_refs_missing"}

    listed = client.get("/api/skills/candidates/list")
    assert listed.status_code == 200
    assert [item["candidate_id"] for item in listed.json()["candidates"]] == [candidate_id]

    loaded = client.get(f"/api/skills/candidates/{candidate_id}")
    assert loaded.status_code == 200
    assert loaded.json()["skill_spec"]["name"] == "CSS Validator"


def test_get_missing_skill_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"

def test_create_skill_candidate_persists_validation_errors(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    created = client.post("/api/skills/candidates/create", json=_candidate_payload(name=""))
    assert created.status_code == 200
    body = created.json()
    candidate_id = body["candidate"]["candidate_id"]

    assert body["candidate"]["status"] == "needs_validation"
    assert body["candidate"]["install_approved"] is False
    assert {reason["code"] for reason in body["candidate"]["validation_errors"]} == {"name_missing"}
    gate_warning = body["candidate"]["warnings"][-1]
    assert gate_warning["code"] == "skill_candidate_gate"
    assert gate_warning["status"] == "blocked"
    assert "validation_errors_present" in {reason["code"] for reason in gate_warning["reasons"]}

    loaded = client.get(f"/api/skills/candidates/{candidate_id}")
    assert loaded.status_code == 200
    assert loaded.json()["status"] == "needs_validation"
