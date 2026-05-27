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
    def raise_for_status(self):
        return None

    def json(self):
        return {
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


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        assert url.endswith("/api/tags")
        return _FakeResponse()


@pytest.mark.asyncio
async def test_list_models_includes_real_ollama_tags_metadata(monkeypatch):
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
    assert model["metadata_source"] == "Ollama /api/tags"
    assert model["local_model_name"] == "qwen3.6:latest"
    assert model["modified_at"] == "2026-05-20T10:00:00Z"
    assert model["size_bytes"] == 1234567890
    assert model["digest"] == "sha256:abcdef1234567890"
    assert model["format"] == "gguf"
    assert model["family"] == "qwen3"
    assert model["families"] == ["qwen3"]
    assert model["parameter_size"] == "30B"
    assert model["quantization_level"] == "Q4_K_M"
    assert model["context_window_source"] == "estimated"
    assert model["reasoning_source"] == "estimated"
    assert model["tiers_source"] == "estimated"
