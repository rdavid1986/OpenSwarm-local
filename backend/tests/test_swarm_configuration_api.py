from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.swarms import swarms as swarms_module


def _client(monkeypatch, tmp_path: Path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)

    import backend.apps.configuration.store as config_store

    monkeypatch.setattr(config_store, "GLOBAL_CONFIG_FILE", str(tmp_path / "settings" / "global_config.json"))
    monkeypatch.setattr(config_store, "PROJECT_CONFIG_ROOT", str(tmp_path / "projects"))

    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    return TestClient(app), store


def _create(client: TestClient, *, dashboard_id: str | None = None) -> str:
    response = client.post("/api/swarms/create", json={"user_prompt": "Crear README", "dashboard_id": dashboard_id})
    assert response.status_code == 200
    return response.json()["id"]


def test_get_swarm_configuration_returns_safe_defaults(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id = _create(client)

    response = client.get(f"/api/swarms/{swarm_id}/configuration")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["configuration"]["swarm_id"] == swarm_id
    assert body["configuration"]["preferred_models"]["primary"] == "auto"
    assert body["configuration"]["mcp_policy"]["activate_from_config_load"] is False


def test_post_swarm_configuration_persists_in_swarm_state(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id = _create(client)

    response = client.post(
        f"/api/swarms/{swarm_id}/configuration",
        json={"swarm_id": swarm_id, "orchestration_style": "balanced", "planning_depth": "deep"},
    )

    assert response.status_code == 200
    stored = store.load(swarm_id)
    assert stored.configuration["orchestration_style"] == "balanced"
    assert stored.configuration["planning_depth"] == "deep"


def test_post_swarm_configuration_rejects_mismatched_swarm_id(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id = _create(client)

    response = client.post(f"/api/swarms/{swarm_id}/configuration", json={"swarm_id": "other"})

    assert response.status_code == 400
    assert "swarm_id" in response.json()["detail"]


def test_post_swarm_configuration_removes_secrets_and_mcp_activation(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id = _create(client)

    response = client.post(
        f"/api/swarms/{swarm_id}/configuration",
        json={
            "api_key": "sk-test",
            "token": "t",
            "password": "p",
            "credential": "c",
            "private_key": "k",
            "mcp_policy": {"active_mcps": ["gmail"], "activate_from_config_load": True},
        },
    )

    assert response.status_code == 200
    stored_text = (store.root / swarm_id / "swarm.json").read_text(encoding="utf-8")
    assert "api_key" not in stored_text
    assert "token" not in stored_text
    assert "password" not in stored_text
    assert "credential" not in stored_text
    assert "private_key" not in stored_text
    assert "active_mcps" not in stored_text
    assert "activate_from_config_load" not in store.load(swarm_id).configuration.get("mcp_policy", {})


def test_swarm_effective_preserves_swarm_source_and_updates_state(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id = _create(client)
    client.post(f"/api/swarms/{swarm_id}/configuration", json={"orchestration_style": "balanced"})

    response = client.get(f"/api/swarms/{swarm_id}/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["orchestration_style"] == "balanced"
    assert body["source_map"]["orchestration_style"] == "swarm_config"
    assert isinstance(body["blocked_entries"], list)
    assert isinstance(body["required_user_actions"], list)
    assert body["effective_config_hash"]
    stored = store.load(swarm_id)
    assert stored.effective_configuration["orchestration_style"] == "balanced"
    assert stored.configuration_sources["orchestration_style"] == "swarm_config"
    assert isinstance(stored.configuration_conflicts, list)


def test_swarm_effective_project_config_wins_over_user_global_when_no_swarm_override(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id = _create(client, dashboard_id="project-a")

    import backend.apps.configuration.store as config_store

    config_store.save_global_config({"default_language": "es"})
    config_store.save_project_config("project-a", {"default_language": "pt"})

    response = client.get(f"/api/swarms/{swarm_id}/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["default_language"] == "pt"
    assert body["source_map"]["default_language"] == "project_config"


def test_swarm_effective_uses_user_global_when_no_project_config(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id = _create(client, dashboard_id="project-missing")

    import backend.apps.configuration.store as config_store

    config_store.save_global_config({"default_language": "es"})

    response = client.get(f"/api/swarms/{swarm_id}/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["default_language"] == "es"
    assert body["source_map"]["default_language"] == "user_global"


def test_swarm_override_wins_over_project_config(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id = _create(client, dashboard_id="project-a")

    import backend.apps.configuration.store as config_store

    config_store.save_project_config("project-a", {"planning_depth": "shallow"})
    client.post(f"/api/swarms/{swarm_id}/configuration", json={"planning_depth": "deep"})

    response = client.get(f"/api/swarms/{swarm_id}/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["planning_depth"] == "deep"
    assert body["source_map"]["planning_depth"] == "swarm_config"


def test_swarm_effective_hash_changes_when_swarm_config_changes(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id = _create(client)

    first = client.get(f"/api/swarms/{swarm_id}/configuration/effective").json()["effective_config_hash"]
    client.post(f"/api/swarms/{swarm_id}/configuration", json={"orchestration_style": "balanced"})
    second = client.get(f"/api/swarms/{swarm_id}/configuration/effective").json()["effective_config_hash"]

    assert first != second


def test_swarm_effective_does_not_persist_default_configuration_as_explicit(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id = _create(client, dashboard_id="project-a")

    assert store.load(swarm_id).configuration == {}

    response = client.get(f"/api/swarms/{swarm_id}/configuration/effective")

    assert response.status_code == 200
    stored = store.load(swarm_id)
    assert stored.configuration == {}
    assert stored.effective_configuration
    assert stored.configuration_sources
