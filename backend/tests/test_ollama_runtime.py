import pytest

from backend.apps.agents.providers.ollama_runtime import (
    build_effective_ollama_request_options,
    build_ollama_runtime_metadata,
    build_ollama_runtime_trace_sources,
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


def test_runtime_metadata_maps_metrics_reasoning_tools_and_structured_output_safely():
    request = build_effective_ollama_request_options(
        requested_effort='high',
        supports_thinking=True,
        structured_output={'requested': True, 'json_mode': True},
        config_source='test',
    )
    request.update({'model': 'qwen3.6:latest', 'messages': [{'role': 'user', 'content': 'secret prompt'}]})
    response = {
        'model': 'qwen3.6:latest',
        'message': {
            'content': '{"answer":"ok"}',
            'thinking': 'private reasoning',
            'tool_calls': [
                {'id': 'call_1', 'function': {'name': 'read_file', 'arguments': '{"path":"a.py","token":"secret"}'}},
            ],
        },
        'total_duration': 2_000_000_000,
        'load_duration': 100_000_000,
        'prompt_eval_count': 5,
        'prompt_eval_duration': 500_000_000,
        'eval_count': 10,
        'eval_duration': 1_000_000_000,
    }

    metadata = build_ollama_runtime_metadata(response_payload=response, request_payload=request, model='qwen3.6:latest')
    sources = build_ollama_runtime_trace_sources(metadata)

    assert metadata['metrics']['tokens_per_second'] == 10.0
    assert metadata['metrics']['cold_start_likely'] is True
    assert metadata['reasoning_effort']['requested_effort'] == 'high'
    assert metadata['reasoning_effort']['provider_support'] == 'boolean_think'
    assert metadata['tool_calls'][0]['tool_name'] == 'read_file'
    assert metadata['tool_calls'][0]['arguments']['token'] == '[redacted]'
    assert metadata['tool_calls'][0]['executed'] is False
    assert metadata['structured_output']['validation_status'] == 'valid'
    assert metadata['thinking']['thinking_redacted'] is True
    assert 'secret prompt' not in str(metadata)
    assert any(source.get('source_kind') == 'runtime_timer' for source in sources)
    assert any(source.get('source_kind') == 'tool_trace' for source in sources)
    assert any(source.get('source_kind') == 'validation_trace' for source in sources)


def test_runtime_metadata_handles_missing_metrics_and_invalid_structured_output():
    request = build_effective_ollama_request_options(
        requested_effort='off',
        supports_thinking=True,
        structured_output={'requested': True, 'json_mode': True},
    )
    response = {'message': {'content': 'not json'}}

    metadata = build_ollama_runtime_metadata(response_payload=response, request_payload=request, model='qwen')

    assert metadata['metrics']['status'] == 'not_reported'
    assert metadata['reasoning_effort']['payload_applied']['think'] is False
    assert metadata['structured_output']['validation_status'] == 'invalid'
    assert metadata['structured_output']['fallback_reason']
