import json

from backend.apps.agents import agent_manager
from backend.apps.agents.models import AgentSession


def test_load_session_data_normalizes_legacy_idle_status(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_manager, "SESSIONS_DIR", str(tmp_path))

    session_id = "legacy-idle-session"
    payload = {
        "id": session_id,
        "name": "Legacy idle session",
        "status": "idle",
        "provider": "ollama",
        "model": "ollama/qwen2.5-coder:14b",
        "mode": "agent",
        "messages": [],
    }
    (tmp_path / f"{session_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    data = agent_manager._load_session_data(session_id)

    assert data["status"] == "completed"
    AgentSession(**data)


def test_load_all_session_data_normalizes_legacy_idle_status(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_manager, "SESSIONS_DIR", str(tmp_path))

    payload = {
        "id": "legacy-idle-session",
        "name": "Legacy idle session",
        "status": "idle",
        "provider": "ollama",
        "model": "ollama/qwen2.5-coder:14b",
        "mode": "agent",
        "messages": [],
    }
    (tmp_path / "legacy-idle-session.json").write_text(json.dumps(payload), encoding="utf-8")

    sessions = dict(agent_manager._load_all_session_data())

    assert sessions["legacy-idle-session"]["status"] == "completed"
    AgentSession(**sessions["legacy-idle-session"])
