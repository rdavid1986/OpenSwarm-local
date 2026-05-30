import json

import pytest

from backend.apps.agents import agents as agents_module


class _FakeSettings:
    anthropic_api_key = None
    openai_api_key = None
    google_api_key = None
    openrouter_api_key = None
    openswarm_bearer_token = None
    connection_mode = "own_key"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


_TAGS_PAYLOAD = {
    "models": [
        {
            "name": "qwen3.6:latest",
            "model": "qwen3.6:latest",
            "modified_at": "2026-05-20T10:00:00Z",
            "size": 1234567890,
            "digest": "sha256:abcdef1234567890",
            "details": {
                "format": "gguf",
                "family": "qwen3",
                "families": ["qwen3"],
                "parameter_size": "30B",
                "quantization_level": "Q4_K_M",
            },
        }
    ]
}


_SHOW_PAYLOAD = {
    "model_info": {
        "qwen3.context_length": 262144,
    },
    "parameters": None,
}


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        if url.endswith("/api/version"):
            return _FakeResponse({"version": "0.6.0"})
        if url.endswith("/api/tags"):
            return _FakeResponse(_TAGS_PAYLOAD)
        if url.endswith("/api/ps"):
            return _FakeResponse({"models": []})
        raise AssertionError(url)

    async def post(self, url, json=None):
        assert url.endswith("/api/show")
        assert json == {"model": "qwen3.6:latest", "verbose": True}
        return _FakeResponse(_SHOW_PAYLOAD)


@pytest.mark.asyncio
async def test_list_models_includes_real_ollama_tags_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENSWARM_LOCAL_MODEL_REGISTRY_PATH", str(tmp_path / "local_model_registry.json"))
    monkeypatch.setattr("backend.apps.settings.settings.load_settings", lambda: _FakeSettings())
    monkeypatch.setattr("backend.apps.nine_router.is_running", lambda: False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)

    response = await agents_module.list_models()

    ollama_models = response["models"]["Ollama Local"]
    model = ollama_models[0]
    assert model["value"] == "ollama/qwen3.6:latest"
    assert model["billing_kind"] == "free"
    assert model["input_cost_per_1m"] == 0.0
    assert model["output_cost_per_1m"] == 0.0
    assert model["metadata_source"] == "Ollama /api/tags + /api/show"
    assert model["local_model_name"] == "qwen3.6:latest"
    assert model["modified_at"] == "2026-05-20T10:00:00Z"
    assert model["size_bytes"] == 1234567890
    assert model["digest"] == "sha256:abcdef1234567890"
    assert model["format"] == "gguf"
    assert model["family"] == "qwen3"
    assert model["families"] == ["qwen3"]
    assert model["parameter_size"] == "30B"
    assert model["quantization_level"] == "Q4_K_M"
    assert model["context_window"] == 262144
    assert model["context_window_source"] == "configured"
    assert model["configured_context_window"] == 262144
    assert model["configured_context_source"] == "Ollama /api/show model_info qwen3.context_length"
    assert model["estimated_context_window"] == 128000

    registry = json.loads((tmp_path / "local_model_registry.json").read_text(encoding="utf-8"))
    assert registry["ollama/qwen3.6:latest"]["configured_context_window"] == 262144
    assert registry["ollama/qwen3.6:latest"]["digest"] == "sha256:abcdef1234567890"
    assert model["reasoning_source"] == "inferred"
    assert model["tiers_source"] == "estimated"
