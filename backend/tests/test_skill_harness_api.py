from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_module, "skill_candidate_store", SkillCandidateStore(root=tmp_path / "skill_candidates"))
    monkeypatch.setattr(skills_module, "SKILLS_DIR", str(tmp_path / "legacy_skills"))
    monkeypatch.setattr(skills_module, "INDEX_PATH", str(tmp_path / "legacy_skills" / ".skills_index.json"))
    app = FastAPI()
    app.include_router(skills_module.skills.router, prefix="/api/skills")
    return TestClient(app)


def _payload():
    return {
        "skill_spec": {
            "name": "Harness Skill",
            "description": "Validate harness flows.",
            "command": "harness-skill",
            "content": "# Harness Skill\nReview safely.",
            "validation_plan": {"checks": [{"title": "Check behavior", "required_evidence": ["ev1"]}]},
            "evidence_contract": {"required_evidence": ["ev1"]},
        },
        "source": "skill_builder",
        "evidence_refs": ["ev1"],
        "policy_refs": ["policy1"],
    }


def _created_candidate_id(client):
    created = client.post("/api/skills/candidates/create", json=_payload())
    assert created.status_code == 200
    return created.json()["candidate"]["candidate_id"]


def test_harness_full_api_is_read_only(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _created_candidate_id(client)
    before = client.get(f"/api/skills/candidates/{candidate_id}").json()

    response = client.get(f"/api/skills/candidates/{candidate_id}/harness/full")

    assert response.status_code == 200
    body = response.json()
    assert body["harness_kind"] == "skill_harness_full_report"
    assert body["test_contract"]["contract_kind"] == "skill_test_case_contract"
    assert body["dry_run"]["executed"] is False
    assert body["dry_run"]["tool_calls_executed"] is False
    assert body["dry_run"]["mcp_activated"] is False
    assert body["dry_run"]["install_performed"] is False
    assert body["promotion_gate"]["can_install_skill"] is False

    after = client.get(f"/api/skills/candidates/{candidate_id}").json()
    assert after == before


def test_harness_individual_endpoints(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _created_candidate_id(client)

    endpoints = {
        "test-contract": "contract_kind",
        "dry-run": "report_kind",
        "runtime-validation": "report_kind",
        "regression-suite": "suite_kind",
        "evidence-quality": "report_kind",
        "promotion-gate": "gate_kind",
    }
    for endpoint, marker in endpoints.items():
        response = client.get(f"/api/skills/candidates/{candidate_id}/harness/{endpoint}")
        assert response.status_code == 200
        body = response.json()
        assert marker in body
        assert body["can_install_skill"] is False
        assert body["can_execute_source"] is False
        assert body["can_activate_tools"] is False
        assert body["can_activate_mcp"] is False


def test_harness_missing_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing/harness/full")

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"


def test_harness_promotion_gate_does_not_enable_install(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    candidate_id = _created_candidate_id(client)

    gate = client.get(f"/api/skills/candidates/{candidate_id}/harness/promotion-gate").json()
    installed = client.post(f"/api/skills/candidates/{candidate_id}/install")

    assert gate["can_request_install_approval"] in {True, False}
    assert gate["can_install_skill"] is False
    assert installed.status_code == 409
    assert installed.json()["detail"] == "Skill candidate is not approved for install"
