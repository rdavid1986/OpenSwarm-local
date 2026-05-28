from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client_with_temp_store(monkeypatch, tmp_path: Path):
    path = tmp_path / "settings" / "global_config.json"
    import backend.apps.configuration.store as store
    from backend.apps.configuration import api as api_module

    monkeypatch.setattr(store, "GLOBAL_CONFIG_FILE", str(path))
    app = FastAPI()
    app.include_router(api_module.configuration.router, prefix="/api/configuration")
    return TestClient(app), path


def test_api_get_global_returns_valid_structure(monkeypatch, tmp_path: Path):
    client, path = _client_with_temp_store(monkeypatch, tmp_path)

    response = client.get("/api/configuration/global")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["config"]["schema_version"] == 1
    assert body["config"]["default_model"] == "auto"
    assert body["path"] == str(path)


def test_api_post_global_persists_valid_structure(monkeypatch, tmp_path: Path):
    client, _ = _client_with_temp_store(monkeypatch, tmp_path)

    response = client.post("/api/configuration/global", json={"default_language": "en", "default_model": "opus"})

    assert response.status_code == 200
    assert response.json()["config"]["default_language"] == "en"
    assert client.get("/api/configuration/global").json()["config"]["default_model"] == "opus"


def test_api_post_global_eliminates_secrets_and_mcp_activation(monkeypatch, tmp_path: Path):
    client, _ = _client_with_temp_store(monkeypatch, tmp_path)

    response = client.post(
        "/api/configuration/global",
        json={
            "default_model": "sonnet",
            "api_key": "sk-test",
            "default_tool_policy": {"password": "secret", "never_assume_permissions": True},
            "default_mcp_policy": {"active_mcps": ["gmail"], "allow_configured_catalog_visibility": True},
        },
    )

    assert response.status_code == 200
    config = response.json()["config"]
    assert "api_key" not in config
    assert "password" not in config["default_tool_policy"]
    assert "active_mcps" not in config["default_mcp_policy"]
    assert config["default_mcp_policy"]["allow_configured_catalog_visibility"] is True


def test_api_get_effective_returns_resolution_payload(monkeypatch, tmp_path: Path):
    client, _ = _client_with_temp_store(monkeypatch, tmp_path)
    client.post("/api/configuration/global", json={"default_model": "opus"})

    response = client.get("/api/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["effective_config"]["default_model"] == "opus"
    assert body["source_map"]["default_model"] == "user_global"
    assert isinstance(body["blocked_entries"], list)
    assert isinstance(body["required_user_actions"], list)
    assert body["effective_config_hash"]


def test_api_get_effective_uses_defaults_without_existing_file(monkeypatch, tmp_path: Path):
    client, path = _client_with_temp_store(monkeypatch, tmp_path)

    response = client.get("/api/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["default_model"] == "auto"
    assert body["effective_config"]["default_commit_policy"] == "never_without_explicit_request"
    assert path.exists()


def test_api_global_override_changes_effective_hash(monkeypatch, tmp_path: Path):
    client, _ = _client_with_temp_store(monkeypatch, tmp_path)
    first = client.get("/api/configuration/effective").json()["effective_config_hash"]

    client.post("/api/configuration/global", json={"default_model": "opus"})
    second = client.get("/api/configuration/effective").json()["effective_config_hash"]

    assert first != second


def test_api_legacy_no_config_file_does_not_break(monkeypatch, tmp_path: Path):
    client, path = _client_with_temp_store(monkeypatch, tmp_path)
    assert not path.exists()

    response = client.get("/api/configuration/global")

    assert response.status_code == 200
    assert response.json()["config"]["schema_version"] == 1
