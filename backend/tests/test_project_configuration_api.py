from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client_with_temp_stores(monkeypatch, tmp_path: Path):
    global_path = tmp_path / "settings" / "global_config.json"
    project_root = tmp_path / "projects"
    import backend.apps.configuration.store as store
    from backend.apps.configuration import api as api_module

    monkeypatch.setattr(store, "GLOBAL_CONFIG_FILE", str(global_path))
    monkeypatch.setattr(store, "PROJECT_CONFIG_ROOT", str(project_root))
    app = FastAPI()
    app.include_router(api_module.configuration.router, prefix="/api/configuration")
    return TestClient(app), global_path, project_root


def test_api_get_project_returns_valid_structure(monkeypatch, tmp_path: Path):
    client, _, project_root = _client_with_temp_stores(monkeypatch, tmp_path)

    response = client.get("/api/configuration/projects/project-a")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["config"]["schema_version"] == 1
    assert body["config"]["project_id"] == "project-a"
    assert body["config"]["preferred_models"]["primary"] == "auto"
    assert body["path"] == str(project_root / "project-a" / "config.json")


def test_api_post_project_persists_valid_structure(monkeypatch, tmp_path: Path):
    client, _, _ = _client_with_temp_stores(monkeypatch, tmp_path)

    response = client.post(
        "/api/configuration/projects/project-a",
        json={"project_id": "project-a", "project_name": "Project A", "project_instructions": "Use pytest."},
    )

    assert response.status_code == 200
    assert response.json()["config"]["project_name"] == "Project A"
    assert client.get("/api/configuration/projects/project-a").json()["config"]["project_instructions"] == "Use pytest."


def test_api_post_project_rejects_mismatched_body_project_id(monkeypatch, tmp_path: Path):
    client, _, _ = _client_with_temp_stores(monkeypatch, tmp_path)

    response = client.post("/api/configuration/projects/project-a", json={"project_id": "project-b"})

    assert response.status_code == 400
    assert "project_id" in response.json()["detail"]


def test_api_post_project_eliminates_secrets_and_mcp_activation(monkeypatch, tmp_path: Path):
    client, _, _ = _client_with_temp_stores(monkeypatch, tmp_path)

    response = client.post(
        "/api/configuration/projects/project-a",
        json={
            "api_key": "sk-test",
            "tool_policy": {"password": "secret", "never_assume_permissions": True},
            "mcp_policy": {"active_mcps": ["gmail"], "activation_requires_explicit_user_action": True},
        },
    )

    assert response.status_code == 200
    config = response.json()["config"]
    assert "api_key" not in config
    assert "password" not in config["tool_policy"]
    assert "active_mcps" not in config["mcp_policy"]
    assert config["mcp_policy"]["activation_requires_explicit_user_action"] is True


def test_api_get_project_effective_returns_resolution_payload(monkeypatch, tmp_path: Path):
    client, _, _ = _client_with_temp_stores(monkeypatch, tmp_path)
    client.post("/api/configuration/global", json={"default_language": "es", "default_model": "sonnet"})
    client.post("/api/configuration/projects/project-a", json={"project_instructions": "Use pytest.", "default_model": "auto"})

    response = client.get("/api/configuration/projects/project-a/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["effective_config"]["project_instructions"] == "Use pytest."
    assert body["source_map"]["project_instructions"] == "project_config"
    assert body["source_map"]["default_model"] == "project_config"
    assert isinstance(body["blocked_entries"], list)
    assert isinstance(body["required_user_actions"], list)
    assert body["effective_config_hash"]


def test_api_project_effective_uses_global_when_project_has_no_override(monkeypatch, tmp_path: Path):
    client, _, _ = _client_with_temp_stores(monkeypatch, tmp_path)
    client.post("/api/configuration/global", json={"default_language": "es"})

    response = client.get("/api/configuration/projects/project-a/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["default_language"] == "es"
    assert body["source_map"]["default_language"] == "user_global"


def test_api_project_override_changes_effective_hash(monkeypatch, tmp_path: Path):
    client, _, _ = _client_with_temp_stores(monkeypatch, tmp_path)
    first = client.get("/api/configuration/projects/project-a/effective").json()["effective_config_hash"]

    client.post("/api/configuration/projects/project-a", json={"project_instructions": "Run tests."})
    second = client.get("/api/configuration/projects/project-a/effective").json()["effective_config_hash"]

    assert first != second


def test_api_project_config_file_is_written_under_projects(monkeypatch, tmp_path: Path):
    client, _, project_root = _client_with_temp_stores(monkeypatch, tmp_path)

    response = client.post("/api/configuration/projects/Project One", json={"project_name": "Project One"})

    assert response.status_code == 200
    assert response.json()["path"] == str(project_root / "Project_One" / "config.json")
    assert (project_root / "Project_One" / "config.json").exists()
