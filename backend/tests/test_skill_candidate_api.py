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


def test_get_missing_skill_candidate_requirements_contract_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing/requirements-contract")

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"


def test_get_skill_candidate_requirements_contract_is_read_only(monkeypatch, tmp_path):
    from backend.apps.modes.models import Mode
    from backend.apps.tools_lib.models import ToolDefinition
    from backend.apps.tools_lib import tools_lib as tools_module
    from backend.apps.modes import modes as modes_module

    client = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(tools_module, "_load_all", lambda: [ToolDefinition(name="CustomTool", description="Custom action")])
    monkeypatch.setattr(tools_module, "load_builtin_permissions", lambda: {})
    monkeypatch.setattr(modes_module, "_load_all", lambda: [Mode(id="review", name="Review", tools=["Read"])])

    payload = _candidate_payload()
    payload["skill_spec"]["required_tools"] = ["Read", "MissingTool", "CustomTool"]
    payload["skill_spec"]["required_mcp_servers"] = ["Missing MCP"]

    created = client.post("/api/skills/candidates/create", json=payload)
    assert created.status_code == 200
    candidate_id = created.json()["candidate"]["candidate_id"]
    before = client.get(f"/api/skills/candidates/{candidate_id}").json()

    response = client.get(f"/api/skills/candidates/{candidate_id}/requirements-contract")

    assert response.status_code == 200
    contract = response.json()
    assert contract["contract_kind"] == "skill_candidate_requirements_contract"
    assert contract["candidate_id"] == candidate_id
    assert contract["summary"]["declared_tool_count"] == 3
    assert contract["summary"]["missing_tool_count"] == 1
    assert contract["summary"]["declared_mcp_count"] == 1
    assert contract["summary"]["missing_mcp_count"] == 1
    assert {tool["name"]: tool["permission"] for tool in contract["tools"]}["MissingTool"] == "not_found"
    assert contract["mcp_servers"][0]["activation_state"] == "not_found"

    after = client.get(f"/api/skills/candidates/{candidate_id}").json()
    assert after == before
    assert after["install_approved"] is False

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

def test_approve_skill_candidate_requires_gate_pass(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    created = client.post("/api/skills/candidates/create", json=_candidate_payload())
    candidate_id = created.json()["candidate"]["candidate_id"]

    response = client.post(f"/api/skills/candidates/{candidate_id}/approval", json={"approved": True})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["candidate"]["install_approved"] is False
    assert body["candidate"]["status"] == "validated"
    assert body["candidate"]["warnings"][-1]["code"] == "skill_candidate_install_approval"


def test_approve_skill_candidate_can_mark_ready_candidate_without_installing(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    payload = _candidate_payload()
    payload["status"] = "validated"
    payload["evidence_refs"] = ["evidence-1"]
    payload["policy_refs"] = ["policy-1"]

    created = client.post("/api/skills/candidates/create", json=payload)
    candidate_id = created.json()["candidate"]["candidate_id"]

    response = client.post(f"/api/skills/candidates/{candidate_id}/approval", json={"approved": True})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["candidate"]["install_approved"] is True
    assert body["candidate"]["status"] == "approved_for_install"


def test_approve_missing_skill_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/skills/candidates/missing/approval", json={"approved": True})

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"

def test_install_skill_candidate_requires_approved_candidate(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    created = client.post("/api/skills/candidates/create", json=_candidate_payload())
    candidate_id = created.json()["candidate"]["candidate_id"]

    response = client.post(f"/api/skills/candidates/{candidate_id}/install")

    assert response.status_code == 409
    assert response.json()["detail"] == "Skill candidate is not approved for install"


def test_install_approved_skill_candidate_writes_legacy_skill_and_audit(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    payload = _candidate_payload()
    payload["skill_spec"]["command"] = "css-check"
    payload["evidence_refs"] = ["evidence-1"]
    payload["policy_refs"] = ["policy-1"]

    created = client.post("/api/skills/candidates/create", json=payload)
    candidate_id = created.json()["candidate"]["candidate_id"]

    approved = client.post(f"/api/skills/candidates/{candidate_id}/approval", json={"approved": True})
    assert approved.status_code == 200
    assert approved.json()["candidate"]["status"] == "approved_for_install"

    installed = client.post(f"/api/skills/candidates/{candidate_id}/install")

    assert installed.status_code == 200
    body = installed.json()
    assert body["ok"] is True
    assert body["skill"]["id"] == "css-check"
    assert body["candidate"]["status"] == "installed"
    assert body["audit"]["candidate_id"] == candidate_id
    assert body["audit"]["event"] == "skill_candidate_installed"

    listed = client.get("/api/skills/list")
    assert listed.status_code == 200
    assert any(skill["id"] == "css-check" for skill in listed.json()["skills"])


def test_install_missing_skill_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/skills/candidates/missing/install")

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"

def test_reject_skill_candidate_clears_install_approval(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    payload = _candidate_payload()
    payload["status"] = "validated"
    payload["evidence_refs"] = ["evidence-1"]
    payload["policy_refs"] = ["policy-1"]

    created = client.post("/api/skills/candidates/create", json=payload)
    candidate_id = created.json()["candidate"]["candidate_id"]
    approved = client.post(f"/api/skills/candidates/{candidate_id}/approval", json={"approved": True})
    assert approved.json()["candidate"]["install_approved"] is True

    rejected = client.post(f"/api/skills/candidates/{candidate_id}/reject")

    assert rejected.status_code == 200
    body = rejected.json()
    assert body["ok"] is True
    assert body["candidate"]["status"] == "rejected"
    assert body["candidate"]["install_approved"] is False


def test_install_rejected_skill_candidate_is_blocked(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    payload = _candidate_payload()
    payload["status"] = "validated"
    payload["evidence_refs"] = ["evidence-1"]
    payload["policy_refs"] = ["policy-1"]

    created = client.post("/api/skills/candidates/create", json=payload)
    candidate_id = created.json()["candidate"]["candidate_id"]
    rejected = client.post(f"/api/skills/candidates/{candidate_id}/reject")
    assert rejected.status_code == 200

    installed = client.post(f"/api/skills/candidates/{candidate_id}/install")

    assert installed.status_code == 409
    assert installed.json()["detail"] == "Skill candidate is not approved for install"


def test_delete_skill_candidate_removes_candidate(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    created = client.post("/api/skills/candidates/create", json=_candidate_payload())
    candidate_id = created.json()["candidate"]["candidate_id"]

    deleted = client.delete(f"/api/skills/candidates/{candidate_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    loaded = client.get(f"/api/skills/candidates/{candidate_id}")
    assert loaded.status_code == 404


def test_reject_and_delete_missing_skill_candidate_return_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    rejected = client.post("/api/skills/candidates/missing/reject")
    deleted = client.delete("/api/skills/candidates/missing")

    assert rejected.status_code == 404
    assert deleted.status_code == 404
