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


def _create(client: TestClient, *, dashboard_id: str | None = None) -> tuple[str, str]:
    response = client.post("/api/swarms/create", json={"user_prompt": "Crear README", "dashboard_id": dashboard_id})
    assert response.status_code == 200
    body = response.json()
    return body["id"], body["contracts"][0]["id"]


def test_get_miniagent_configuration_returns_safe_defaults(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id, _ = _create(client)

    response = client.get(f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["configuration"]["miniagent_id"] == "mini-1"
    assert body["configuration"]["parent_swarm_id"] == swarm_id
    assert body["configuration"]["mcp_policy"]["activate_from_config_load"] is False
    assert body["configuration"]["skill_policy"]["can_create_skills"] is False


def test_post_miniagent_configuration_persists_profile(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)

    response = client.post(
        f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration",
        json={
            "miniagent_id": "mini-1",
            "parent_agent_id": agent_id,
            "specialization": "css_patch",
            "model": "qwen2.5-coder:32b",
        },
    )

    assert response.status_code == 200
    stored = store.load(swarm_id)
    profile = stored.miniagent_profiles["mini-1"]
    assert profile["configuration"]["specialization"] == "css_patch"
    assert profile["configuration"]["model"] == "qwen2.5-coder:32b"
    assert profile["parent_agent_id"] == agent_id


def test_post_miniagent_configuration_rejects_mismatched_miniagent_id(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id, _ = _create(client)

    response = client.post(f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration", json={"miniagent_id": "other"})

    assert response.status_code == 400
    assert "miniagent_id" in response.json()["detail"]


def test_post_miniagent_configuration_removes_secrets_and_mcp_activation(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id, _ = _create(client)

    response = client.post(
        f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration",
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


def test_miniagent_effective_preserves_miniagent_source_and_updates_profile(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id, _ = _create(client)
    client.post(f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration", json={"specialization": "css_patch"})

    response = client.get(f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["specialization"] == "css_patch"
    assert body["source_map"]["specialization"] == "miniagent_config"
    stored = store.load(swarm_id)
    profile = stored.miniagent_profiles["mini-1"]
    assert profile["effective_configuration"]["specialization"] == "css_patch"
    assert profile["configuration_sources"]["specialization"] == "miniagent_config"


def test_miniagent_effective_agent_config_wins_when_no_miniagent_override(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)
    client.post(
        f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration",
        json={"model": "qwen2.5-coder:14b"},
    )
    client.post(
        f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration",
        json={"parent_agent_id": agent_id},
    )

    response = client.get(f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["model"] == "qwen2.5-coder:14b"
    assert body["source_map"]["model"] == "agent_config"


def test_miniagent_override_wins_over_agent_config(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)
    client.post(
        f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration",
        json={"model": "qwen2.5-coder:14b"},
    )
    client.post(
        f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration",
        json={"parent_agent_id": agent_id, "model": "qwen2.5-coder:32b"},
    )

    response = client.get(f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["model"] == "qwen2.5-coder:32b"
    assert body["source_map"]["model"] == "miniagent_config"


def test_miniagent_effective_does_not_persist_default_configuration_as_explicit(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id, _ = _create(client)

    assert store.load(swarm_id).miniagent_profiles == {}

    response = client.get(f"/api/swarms/{swarm_id}/miniagents/mini-1/configuration/effective")

    assert response.status_code == 200
    stored = store.load(swarm_id)
    profile = stored.miniagent_profiles["mini-1"]
    assert profile["configuration"] == {}
    assert profile["effective_configuration"]
    assert profile["configuration_sources"]
