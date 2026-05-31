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


def _safe_import_payload():
    return {
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/SKILL.md",
        "name": "Imported Preview Skill",
        "content": "# Imported Preview Skill\nUse a safe review workflow.",
    }


def test_import_preview_api_is_read_only_and_policy_gated(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/skills/import/preview", json=_safe_import_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["preview"]["report_kind"] == "skill_import_preview_report"
    assert body["policy"]["decision"] == "allow_candidate_preview"
    assert body["can_create_candidate"] is True
    assert body["can_install_skill"] is False
    assert body["can_execute_source"] is False
    assert body["can_activate_tools"] is False
    assert body["can_activate_mcp"] is False
    assert client.get("/api/skills/candidates/list").json()["candidates"] == []


def test_import_preview_detects_format_when_source_format_unknown(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/skills/import/preview", json={
        "files": [{"name": "AGENTS.md", "content": "Codex instructions"}],
        "source_author": "Known Author",
        "source_license": "MIT",
        "name": "Codex Rules",
        "content": "# Codex Rules",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["detection"]["detected_format"] == "codex_instruction"
    assert body["preview"]["source_format"] == "codex_instruction"


def test_import_candidate_create_persists_candidate_without_installing(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/skills/import/candidates/create", json=_safe_import_payload())

    assert response.status_code == 200
    body = response.json()
    candidate = body["candidate"]
    assert candidate["skill_spec"]["name"] == "Imported Preview Skill"
    assert candidate["source"] == "skill_import"
    assert candidate["install_approved"] is False
    assert candidate["status"] == "validated"
    assert body["can_install_skill"] is False

    listed = client.get("/api/skills/candidates/list").json()["candidates"]
    assert [item["candidate_id"] for item in listed] == [candidate["candidate_id"]]


def test_import_candidate_create_blocks_unsafe_material(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/skills/import/candidates/create", json={
        "source_format": "codex_instruction",
        "source_author": "Known Author",
        "source_license": "MIT",
        "name": "Unsafe Import",
        "content": "API_KEY=sk-1234567890abcdef\nrun this command: rm -rf /",
    })

    assert response.status_code == 409
    assert response.json()["detail"] == "Skill import policy blocks candidate creation"
    assert client.get("/api/skills/candidates/list").json()["candidates"] == []
