from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.import_ingestion_guard import (
    build_prepared_skill_import_ingestion_guard,
    sanitize_prepared_skill_import_files,
)
from backend.apps.skills.import_preview import build_skill_import_preview_report
from backend.apps.skills.import_policy import evaluate_skill_import_policy


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_module, "skill_candidate_store", SkillCandidateStore(root=tmp_path / "skill_candidates"))
    monkeypatch.setattr(skills_module, "SKILLS_DIR", str(tmp_path / "legacy_skills"))
    monkeypatch.setattr(skills_module, "INDEX_PATH", str(tmp_path / "legacy_skills" / ".skills_index.json"))
    app = FastAPI()
    app.include_router(skills_module.skills.router, prefix="/api/skills")
    return TestClient(app)


def test_prepared_folder_files_are_sanitized_for_preview_only():
    payload = {
        "source_hint": "folder",
        "source_format": "folder",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/folder",
        "files": [
            {"path": "docs/SKILL.md", "content": "# Folder Skill\nWorkflow:\n- Validate."},
            {"path": "README.md", "content": "# Prompt pack"},
        ],
    }

    guard = build_prepared_skill_import_ingestion_guard(payload)
    sanitized = sanitize_prepared_skill_import_files(payload)

    assert guard["status"] == "allowed_preview"
    assert guard["accepted_file_count"] == 2
    assert guard["can_install_skill"] is False
    assert guard["can_execute_source"] is False
    assert all("content" not in item for item in guard["accepted_files"])
    assert sanitized[0]["content"].startswith("# Folder Skill")


def test_folder_preview_uses_sanitized_files_and_allows_candidate_preview():
    payload = {
        "source_format": "folder",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/folder",
        "files": [{"path": "docs/SKILL.md", "content": "# Folder Skill\nUse safe review steps."}],
    }
    guard = build_prepared_skill_import_ingestion_guard(payload)
    payload["prepared_ingestion_guard"] = guard
    payload["files"] = sanitize_prepared_skill_import_files(payload)

    report = build_skill_import_preview_report(payload)
    policy = evaluate_skill_import_policy(report)

    assert report["prepared_ingestion_guard"]["status"] == "allowed_preview"
    assert report["skill_spec_preview"]["content"].startswith("# Folder Skill")
    assert report["import_contract"]["original_files"][0]["path"] == "docs/SKILL.md"
    assert policy["decision"] == "allow_candidate_preview"
    assert policy["can_create_candidate"] is True


def test_unsafe_prepared_path_blocks_candidate_creation_and_sanitizes_content(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.post("/api/skills/import/preview", json={
        "source_hint": "folder",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/folder",
        "files": [{"path": "../SKILL.md", "content": "# Unsafe path content"}],
    })

    assert response.status_code == 200
    body = response.json()
    guard = body["prepared_ingestion_guard"]
    assert guard["status"] == "blocked"
    assert guard["rejected_files"][0]["code"] == "path_traversal"
    assert body["policy"]["decision"] == "blocked"
    assert body["can_create_candidate"] is False
    assert body["preview"]["skill_spec_preview"]["content"] == ""

    create_response = client.post("/api/skills/import/candidates/create", json={
        "source_hint": "folder",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/folder",
        "files": [{"path": "../SKILL.md", "content": "# Unsafe path content"}],
    })
    assert create_response.status_code == 409


def test_binary_or_unsupported_prepared_file_is_blocked():
    payload = {
        "source_hint": "zip",
        "files": [
            {"path": "bin/tool.exe", "content": "MZ", "mime_type": "application/octet-stream"},
            {"path": "docs/SKILL.md", "content": "# Safe"},
        ],
    }

    guard = build_prepared_skill_import_ingestion_guard(payload)

    codes = {item["code"] for item in guard["rejected_files"]}
    assert guard["status"] == "blocked"
    assert "unsupported_extension" in codes or "binary_mime_type" in codes
    assert guard["accepted_file_count"] == 1
    assert guard["extracted_archives"] is False
    assert guard["cloned_repositories"] is False
