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


def test_get_agent_configuration_returns_safe_defaults(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)

    response = client.get(f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["configuration"]["agent_id"] == agent_id
    assert body["configuration"]["swarm_id"] == swarm_id
    assert body["configuration"]["mcp_policy"]["activate_from_config_load"] is False


def test_post_agent_configuration_persists_in_agent_contract(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)

    response = client.post(
        f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration",
        json={"agent_id": agent_id, "model": "qwen2.5-coder:32b", "thinking_level": "high"},
    )

    assert response.status_code == 200
    stored = store.load(swarm_id)
    agent = next(contract for contract in stored.contracts if contract.id == agent_id)
    assert agent.configuration["model"] == "qwen2.5-coder:32b"
    assert agent.configuration["thinking_level"] == "high"


def test_post_agent_configuration_rejects_mismatched_agent_id(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)

    response = client.post(f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration", json={"agent_id": "other"})

    assert response.status_code == 400
    assert "agent_id" in response.json()["detail"]


def test_post_agent_configuration_removes_secrets_and_mcp_activation(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)

    response = client.post(
        f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration",
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


def test_agent_effective_preserves_agent_source_and_updates_contract(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)
    client.post(f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration", json={"model": "qwen2.5-coder:32b"})

    response = client.get(f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["model"] == "qwen2.5-coder:32b"
    assert body["source_map"]["model"] == "agent_config"
    stored = store.load(swarm_id)
    agent = next(contract for contract in stored.contracts if contract.id == agent_id)
    assert agent.effective_configuration["model"] == "qwen2.5-coder:32b"
    assert agent.configuration_sources["model"] == "agent_config"


def test_agent_effective_swarm_config_wins_when_no_agent_override(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)

    client.post(f"/api/swarms/{swarm_id}/configuration", json={"planning_depth": "deep"})

    response = client.get(f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["planning_depth"] == "deep"
    assert body["source_map"]["planning_depth"] == "swarm_config"


def test_agent_effective_project_config_wins_when_no_swarm_or_agent_override(monkeypatch, tmp_path: Path):
    client, _ = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client, dashboard_id="project-a")

    import backend.apps.configuration.store as config_store

    config_store.save_project_config("project-a", {"default_language": "pt"})

    response = client.get(f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration/effective")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_config"]["default_language"] == "pt"
    assert body["source_map"]["default_language"] == "project_config"


def test_agent_effective_does_not_persist_default_configuration_as_explicit(monkeypatch, tmp_path: Path):
    client, store = _client(monkeypatch, tmp_path)
    swarm_id, agent_id = _create(client)

    stored_before = store.load(swarm_id)
    agent_before = next(contract for contract in stored_before.contracts if contract.id == agent_id)
    assert agent_before.configuration == {}

    response = client.get(f"/api/swarms/{swarm_id}/agents/{agent_id}/configuration/effective")

    assert response.status_code == 200
    stored_after = store.load(swarm_id)
    agent_after = next(contract for contract in stored_after.contracts if contract.id == agent_id)
    assert agent_after.configuration == {}
    assert agent_after.effective_configuration
    assert agent_after.configuration_sources
