import socket
import urllib.error

from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.providers.provider_health import (
    check_local_model_provider_health,
    normalize_ollama_model_name,
    ollama_unavailable_message,
)


class _FakeResponse:
    def __init__(self, body: str, *, status: int = 200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body.encode("utf-8")


def test_normalize_ollama_model_name_strips_provider_prefix():
    assert normalize_ollama_model_name("ollama/qwen2.5-coder:14b") == "qwen2.5-coder:14b"
    assert normalize_ollama_model_name("qwen2.5-coder:14b") == "qwen2.5-coder:14b"
    assert normalize_ollama_model_name(None) is None


def test_ollama_unavailable_message_uses_base_url():
    assert (
        ollama_unavailable_message("http://localhost:11434/")
        == "Ollama no está corriendo o no responde en http://localhost:11434"
    )


def test_check_local_model_provider_health_ok(monkeypatch):
    def fake_urlopen(req, timeout):
        assert req.full_url == "http://localhost:11434/api/tags"
        assert timeout == 2.0
        return _FakeResponse('{"models":[{"name":"qwen2.5-coder:14b"},{"name":"codellama:34b"}]}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    health = check_local_model_provider_health(model="ollama/qwen2.5-coder:14b")

    assert health["ok"] is True
    assert health["provider"] == "ollama"
    assert health["status"] == "available"
    assert health["model"] == "qwen2.5-coder:14b"
    assert health["available_models"] == ["qwen2.5-coder:14b", "codellama:34b"]


def test_check_local_model_provider_health_connection_refused(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    health = check_local_model_provider_health(model="qwen2.5-coder:14b", base_url="http://localhost:11434")

    assert health["ok"] is False
    assert health["status"] == "unavailable"
    assert health["reason"] == "Ollama no está corriendo o no responde en http://localhost:11434"
    assert "refused" in health["error_detail"]


def test_check_local_model_provider_health_timeout(monkeypatch):
    def fake_urlopen(req, timeout):
        raise socket.timeout("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    health = check_local_model_provider_health(base_url="http://127.0.0.1:11434")

    assert health["ok"] is False
    assert health["status"] == "unavailable"
    assert health["reason"] == "Ollama no está corriendo o no responde en http://127.0.0.1:11434"


def test_check_local_model_provider_health_model_missing(monkeypatch):
    def fake_urlopen(req, timeout):
        return _FakeResponse('{"models":[{"name":"codellama:34b"}]}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    health = check_local_model_provider_health(model="qwen2.5-coder:14b")

    assert health["ok"] is False
    assert health["status"] == "model_missing"
    assert health["available_models"] == ["codellama:34b"]
    assert "qwen2.5-coder:14b" in health["reason"]


def test_check_local_model_provider_health_invalid_json(monkeypatch):
    def fake_urlopen(req, timeout):
        return _FakeResponse("not json")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    health = check_local_model_provider_health()

    assert health["ok"] is False
    assert health["status"] == "unavailable"
    assert "Invalid JSON" in health["error_detail"]


def test_ollama_adapter_healthcheck_returns_normalized_and_compatible_fields(monkeypatch):
    def fake_urlopen(req, timeout):
        return _FakeResponse('{"models":[{"name":"qwen2.5-coder:14b"}]}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    health = OllamaAdapter(base_url="http://localhost:11434").healthcheck(model="ollama/qwen2.5-coder:14b")

    assert health["ok"] is True
    assert health["provider"] == "ollama"
    assert health["status"] == "available"
    assert health["available_models"] == ["qwen2.5-coder:14b"]
    assert health["models"] == [{"name": "qwen2.5-coder:14b"}]
    assert health["error"] == ""
