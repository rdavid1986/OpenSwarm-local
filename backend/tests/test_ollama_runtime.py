import pytest

from backend.apps.agents.providers.ollama_runtime import (
    build_model_picker_models_from_snapshot,
    build_modelcore_process_trace_item,
    fetch_ollama_capability_snapshot_async,
    fetch_ollama_embedding,
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        if url.endswith('/api/version'):
            return _FakeResponse({'version': '0.6.0'})
        if url.endswith('/api/tags'):
            return _FakeResponse({'models': [{'name': 'qwen3.6:latest', 'size': 123, 'digest': 'abc', 'modified_at': 'now'}]})
        if url.endswith('/api/ps'):
            return _FakeResponse({'models': [{'name': 'qwen3.6:latest', 'expires_at': 'soon'}]})
        raise AssertionError(url)

    async def post(self, url, json=None):
        if url.endswith('/api/show'):
            return _FakeResponse({
                'details': {'family': 'qwen35moe', 'families': ['qwen35moe'], 'format': 'gguf'},
                'model_info': {'qwen35moe.context_length': 262144},
                'capabilities': ['tools'],
            })
        if url.endswith('/api/embed'):
            return _FakeResponse({'embeddings': [[0.1, 0.2]], 'eval_count': 2, 'eval_duration': 1_000_000_000})
        raise AssertionError(url)


@pytest.mark.asyncio
async def test_async_snapshot_and_picker_models_use_native_ollama_payloads(monkeypatch):
    monkeypatch.setattr('httpx.AsyncClient', _FakeAsyncClient)

    snapshot = await fetch_ollama_capability_snapshot_async(base_url='http://ollama.local')
    models, registry, changed = build_model_picker_models_from_snapshot(snapshot, {})

    model = models[0]
    assert snapshot['health'] == 'available'
    assert snapshot['version'] == '0.6.0'
    assert model['value'] == 'ollama/qwen3.6:latest'
    assert model['configured_context_window'] == 262144
    assert model['supports_tools'] is True
    assert model['capability_source']['tools'] == 'reported'
    assert model['supports_thinking'] is True
    assert model['reasoning_source'] == 'inferred'
    assert model['running'] is True
    assert model['loaded'] is True
    assert registry['ollama/qwen3.6:latest']['configured_context_window'] == 262144
    assert changed is True


@pytest.mark.asyncio
async def test_embedding_bridge_returns_safe_metadata_without_requiring_real_ollama(monkeypatch):
    monkeypatch.setattr('httpx.AsyncClient', _FakeAsyncClient)

    result = await fetch_ollama_embedding(model='ollama/nomic-embed-text:latest', input_text='x' * 200)

    assert result['ok'] is True
    assert result['metadata']['input_length'] == 200
    assert len(result['metadata']['input_preview']) == 160
    assert result['metadata']['dimensions'] == 2
    assert result['result']['source'] == 'Ollama /api/embed'


def test_modelcore_trace_item_is_safe_and_model_scoped():
    item = build_modelcore_process_trace_item(
        {'model': 'qwen3.6:latest', 'running': True, 'capabilities': {'tools': {'supported': True, 'source': 'reported'}}},
        health={'status': 'available', 'base_url': 'http://localhost:11434'},
    )

    assert item['subsystem'] == 'ModelCore'
    assert item['details']['model'] == 'qwen3.6:latest'
    assert item['details']['running'] is True
    assert 'capabilities' in item['details']
