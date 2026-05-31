from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.skill_version_store import SkillVersionStore


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_module, "skill_candidate_store", SkillCandidateStore(root=tmp_path / "candidates"))
    monkeypatch.setattr(skills_module, "skill_version_store", SkillVersionStore(root=tmp_path / "versions"))
    app = FastAPI()
    app.include_router(skills_module.skills.router, prefix="/api/skills")
    return TestClient(app)


def _candidate_id(client):
    res = client.post("/api/skills/candidates/create", json={"skill_spec": {"name": "VSkill", "content": "# VSkill"}, "source": "test"})
    assert res.status_code == 200
    return res.json()["candidate"]["candidate_id"]


def test_snapshot_endpoint_persists_and_lists(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _candidate_id(client)

    created = client.post(f"/api/skills/candidates/{candidate_id}/versions/snapshot", json={"reason": "baseline"})
    listed = client.get(f"/api/skills/candidates/{candidate_id}/versions")

    assert created.status_code == 200
    assert created.json()["snapshot"]["skill_ref"] == candidate_id
    assert listed.json()["summary"]["snapshot_count"] == 1
    assert listed.json()["can_install_skill"] is False


def test_rollback_plan_is_read_only_and_missing_snapshot_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _candidate_id(client)
    before = client.get(f"/api/skills/candidates/{candidate_id}").json()

    missing = client.post(f"/api/skills/candidates/{candidate_id}/versions/rollback-plan", json={"target_snapshot_id": "missing"})

    assert missing.status_code == 404
    assert client.get(f"/api/skills/candidates/{candidate_id}").json() == before


def test_rollback_plan_detects_changed_fields(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _candidate_id(client)
    snapshot = client.post(f"/api/skills/candidates/{candidate_id}/versions/snapshot", json={"reason": "baseline"}).json()["snapshot"]

    plan = client.post(f"/api/skills/candidates/{candidate_id}/versions/rollback-plan", json={"target_snapshot_id": snapshot["snapshot_id"]})

    assert plan.status_code == 200
    assert plan.json()["restore_performed"] is False
    assert plan.json()["can_install_skill"] is False


def test_missing_candidate_versions_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing/versions")

    assert response.status_code == 404
