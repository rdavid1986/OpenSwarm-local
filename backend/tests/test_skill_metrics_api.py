from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.skill_metrics_store import SkillMetricsStore


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_module, "skill_candidate_store", SkillCandidateStore(root=tmp_path / "candidates"))
    monkeypatch.setattr(skills_module, "skill_metrics_store", SkillMetricsStore(root=tmp_path / "metrics"))
    app = FastAPI()
    app.include_router(skills_module.skills.router, prefix="/api/skills")
    return TestClient(app)


def _candidate_id(client):
    res = client.post("/api/skills/candidates/create", json={"skill_spec": {"name": "MSkill", "content": "# MSkill"}, "source": "test"})
    assert res.status_code == 200
    return res.json()["candidate"]["candidate_id"]


def test_empty_metrics_summary_is_unmeasured(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _candidate_id(client)

    response = client.get(f"/api/skills/candidates/{candidate_id}/metrics/summary")

    assert response.status_code == 200
    assert response.json()["status"] == "unmeasured"
    assert response.json()["record_count"] == 0


def test_explicit_metric_record_is_persisted_and_summarized(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _candidate_id(client)

    created = client.post(f"/api/skills/candidates/{candidate_id}/metrics/record", json={"source": "user_feedback", "outcome": "success", "score": 0.9, "evidence_refs": ["ev1"], "measured": True})
    listed = client.get(f"/api/skills/candidates/{candidate_id}/metrics")

    assert created.status_code == 200
    assert created.json()["record"]["evidence_refs"] == ["ev1"]
    assert listed.json()["summary"]["average_score"] == 0.9
    assert listed.json()["summary"]["success_count"] == 1
    assert listed.json()["can_execute_source"] is False


def test_unknown_outcome_counted_separately(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _candidate_id(client)

    client.post(f"/api/skills/candidates/{candidate_id}/metrics/record", json={"outcome": "not_recorded"})
    summary = client.get(f"/api/skills/candidates/{candidate_id}/metrics/summary").json()

    assert summary["unknown_count"] == 1
    assert summary["average_score"] is None


def test_missing_candidate_metrics_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing/metrics")

    assert response.status_code == 404
