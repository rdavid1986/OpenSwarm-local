"""Runtime integration helpers for native Ollama metadata.

All network calls are optional and bounded. This module normalizes Ollama's
native endpoints for model picker/API surfaces without starting Ollama,
executing tools, or storing prompts/responses.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.apps.agents.providers.ollama_native import (
    build_embedding_request,
    build_ollama_capability_snapshot_from_payloads,
    build_keep_alive_policy,
    normalize_base_url,
    normalize_embedding_response,
    normalize_ollama_runtime_metrics,
    normalize_openai_compatibility_adapter_metadata,
    redact_ollama_value,
)
from backend.apps.agents.providers.provider_health import normalize_ollama_model_name


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_model_registry_path() -> Path:
    override = os.environ.get("OPENSWARM_LOCAL_MODEL_REGISTRY_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "data" / "models" / "local_model_registry.json"


def load_local_model_registry() -> dict[str, Any]:
    path = local_model_registry_path()
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_local_model_registry(registry: dict[str, Any]) -> None:
    path = local_model_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def ollama_label(model_name: str) -> str:
    clean = str(model_name or "").strip()
    display = clean.replace(":latest", "").replace("-", " ").replace("_", " ")
    return "Ollama " + " ".join(part.capitalize() for part in display.split())


def estimate_ollama_context_window(model_name: str) -> int:
    lower = str(model_name or "").lower()
    if "codellama" in lower:
        return 16_000
    if "qwen" in lower:
        return 128_000
    if "phi" in lower:
        return 16_000
    return 32_000


def ollama_tiers(model_name: str) -> list[int]:
    lower = str(model_name or "").lower()
    if "qwen3" in lower or "qwen2.5-coder:32" in lower or "34b" in lower or "36" in lower:
        return [3, 3, 1]
    if "14b" in lower:
        return [2, 4, 1]
    return [2, 3, 1]


def registry_entry_matches(entry: dict[str, Any] | None, model: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    return (
        entry.get("digest") == model.get("digest")
        and entry.get("modified_at") == model.get("modified_at")
        and entry.get("size_bytes") == model.get("size")
    )


def build_registry_entry_from_snapshot_model(model: dict[str, Any], *, previous: dict[str, Any] | None = None, now: str | None = None) -> dict[str, Any]:
    current_time = now or utc_now_iso()
    configured_window = model.get("context_window") if model.get("context_window_source", "").startswith("Ollama /api/show") else None
    return {
        "provider": "Ollama Local",
        "local_model_name": model.get("model"),
        "digest": model.get("digest"),
        "modified_at": model.get("modified_at"),
        "size_bytes": model.get("size"),
        "format": model.get("format"),
        "family": model.get("family"),
        "families": model.get("families"),
        "parameter_size": model.get("parameter_size"),
        "quantization_level": model.get("quantization_level"),
        "configured_context_window": configured_window,
        "configured_context_source": model.get("context_window_source") if configured_window else None,
        "declared_context_window": None,
        "declared_context_source": None,
        "loaded_context_window": None,
        "loaded_context_source": None,
        "official_metadata_status": "not_fetched",
        "official_metadata_fetched_at": None,
        "first_seen_at": previous.get("first_seen_at") if isinstance(previous, dict) and previous.get("first_seen_at") else current_time,
        "last_seen_at": current_time,
        "last_refreshed_at": current_time,
        "metadata_source": model.get("metadata_source") or "Ollama /api/tags + /api/show",
    }


def _capability_source(model: dict[str, Any], key: str) -> str:
    caps = model.get("capabilities") if isinstance(model.get("capabilities"), dict) else {}
    item = caps.get(key) if isinstance(caps.get(key), dict) else {}
    return str(item.get("source") or "not_reported")


def _capability_fields(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "supports_thinking": bool(model.get("supports_thinking")),
        "supports_tools": bool(model.get("supports_tools")),
        "supports_vision": bool(model.get("supports_vision")),
        "supports_embedding": bool(model.get("supports_embedding")),
        "supports_structured_output": bool(model.get("supports_structured_output")),
        "supports_json": bool(model.get("supports_json")),
        "supports_keep_alive": bool(model.get("supports_keep_alive")),
        "capability_source": {
            "thinking": _capability_source(model, "thinking"),
            "tools": _capability_source(model, "tools"),
            "vision": _capability_source(model, "vision"),
            "embedding": _capability_source(model, "embedding"),
            "structured_output": _capability_source(model, "structured_output"),
            "json": _capability_source(model, "json"),
            "keep_alive": _capability_source(model, "keep_alive"),
        },
    }


def build_model_picker_models_from_snapshot(snapshot: dict[str, Any], registry: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    registry_data = dict(registry or {})
    registry_changed = False
    models: list[dict[str, Any]] = []
    for model in snapshot.get("models") or []:
        if not isinstance(model, dict):
            continue
        name = str(model.get("model") or model.get("name") or "").strip()
        if not name:
            continue
        registry_key = f"ollama/{name}"
        previous = registry_data.get(registry_key) if isinstance(registry_data.get(registry_key), dict) else None
        if previous and registry_entry_matches(previous, model):
            previous = {**previous, "last_seen_at": utc_now_iso()}
            registry_data[registry_key] = previous
            registry_changed = True
            entry = previous
        else:
            entry = build_registry_entry_from_snapshot_model(model, previous=previous)
            registry_data[registry_key] = entry
            registry_changed = True

        estimated_context_window = estimate_ollama_context_window(name)
        configured_context_window = entry.get("configured_context_window")
        context_window = configured_context_window or model.get("context_window") or estimated_context_window
        context_window_source = "configured" if configured_context_window else (model.get("context_window_source") or "estimated")
        details = {
            "format": model.get("format"),
            "family": model.get("family"),
            "families": model.get("families"),
            "parameter_size": model.get("parameter_size"),
            "quantization_level": model.get("quantization_level"),
        }
        cap_fields = _capability_fields(model)
        local_metadata = {
            "source": "ollama_native_snapshot",
            "name": name,
            "model": name,
            "modified_at": model.get("modified_at"),
            "size": model.get("size"),
            "digest": model.get("digest"),
            "details": details,
            "registry": {
                "configured_context_window": configured_context_window,
                "configured_context_source": entry.get("configured_context_source"),
                "declared_context_window": entry.get("declared_context_window"),
                "declared_context_source": entry.get("declared_context_source"),
                "loaded_context_window": entry.get("loaded_context_window"),
                "loaded_context_source": entry.get("loaded_context_source"),
                "last_refreshed_at": entry.get("last_refreshed_at"),
            },
            "capabilities": model.get("capabilities"),
            "health": {
                "status": snapshot.get("health"),
                "base_url": snapshot.get("base_url"),
                "version": snapshot.get("version"),
                "errors": snapshot.get("errors") or [],
                "warnings": snapshot.get("warnings") or [],
            },
            "residency": build_keep_alive_policy(running_model=model if model.get("running") else None),
            "openai_compatibility": normalize_openai_compatibility_adapter_metadata(native_snapshot=snapshot, used_compatibility=False),
        }
        models.append({
            "value": registry_key,
            "label": ollama_label(name),
            "provider": "Ollama Local",
            "context_window": context_window,
            "context_window_source": context_window_source,
            "estimated_context_window": estimated_context_window,
            "estimated_context_source": "OpenSwarm estimate",
            "configured_context_window": configured_context_window,
            "configured_context_source": entry.get("configured_context_source"),
            "declared_context_window": entry.get("declared_context_window"),
            "declared_context_source": entry.get("declared_context_source"),
            "loaded_context_window": entry.get("loaded_context_window"),
            "loaded_context_source": entry.get("loaded_context_source"),
            "reasoning": bool(model.get("supports_thinking")),
            "reasoning_source": _capability_source(model, "thinking"),
            "reasoning_effort": {
                "provider_support": "boolean_think" if model.get("supports_thinking") else "unsupported",
                "config_source": "ollama_native_snapshot",
            },
            "tiers_source": "estimated",
            "input_cost_per_1m": 0.0,
            "output_cost_per_1m": 0.0,
            "is_free": True,
            "billing_kind": "free",
            "tiers": ollama_tiers(name),
            "local_metadata": local_metadata,
            "model_metadata": local_metadata,
            "metadata_source": model.get("metadata_source") or "Ollama /api/tags + /api/show",
            "name": name,
            "model": name,
            "local_model_name": name,
            "modified_at": model.get("modified_at"),
            "size_bytes": model.get("size"),
            "digest": model.get("digest"),
            "format": details.get("format"),
            "family": details.get("family"),
            "families": details.get("families"),
            "parameter_size": details.get("parameter_size"),
            "quantization_level": details.get("quantization_level"),
            "availability": "available" if snapshot.get("health") in {"available", "degraded"} else "unavailable",
            "availability_source": model.get("availability_source") or "Ollama native snapshot",
            "loaded": bool(model.get("running")),
            "running": bool(model.get("running")),
            "expires_at": model.get("expires_at") or "",
            "runtime_metrics": None,
            "eval_results": None,
            **cap_fields,
        })
    return models, registry_data, registry_changed


async def fetch_ollama_capability_snapshot_async(*, base_url: str | None = None, timeout_seconds: float = 2.0) -> dict[str, Any]:
    import httpx

    resolved = normalize_base_url(base_url)
    errors: list[str] = []
    warnings: list[str] = []

    async def get(client: Any, path: str) -> dict[str, Any]:
        try:
            response = await client.get(f"{resolved}{path}")
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            return {}

    async def show(client: Any, name: str) -> dict[str, Any]:
        try:
            response = await client.post(f"{resolved}/api/show", json={"model": name, "verbose": True})
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            warnings.append(f"/api/show {name}: {exc}")
            return {}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        version = await get(client, "/api/version")
        tags = await get(client, "/api/tags")
        ps = await get(client, "/api/ps")
        shows: dict[str, dict[str, Any]] = {}
        for item in tags.get("models", []) if isinstance(tags.get("models"), list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                shows[name] = await show(client, name)

    snapshot = build_ollama_capability_snapshot_from_payloads(
        base_url=resolved,
        version_payload=version,
        tags_payload=tags,
        show_payloads=shows,
        ps_payload=ps,
        errors=errors,
    )
    snapshot["warnings"] = warnings
    snapshot["checked_at"] = utc_now_iso()
    if errors and tags.get("models"):
        snapshot["health"] = "degraded"
    elif errors and not tags.get("models") and not version:
        snapshot["health"] = "unavailable"
    elif warnings:
        snapshot["health"] = "degraded"
    return snapshot


async def fetch_ollama_models_for_picker(*, base_url: str | None = None, timeout_seconds: float = 2.0) -> list[dict[str, Any]]:
    snapshot = await fetch_ollama_capability_snapshot_async(base_url=base_url, timeout_seconds=timeout_seconds)
    if snapshot.get("health") == "unavailable" and not snapshot.get("models"):
        return []
    registry = load_local_model_registry()
    models, updated, changed = build_model_picker_models_from_snapshot(snapshot, registry)
    if changed:
        try:
            save_local_model_registry(updated)
        except Exception:
            pass
    return models


async def fetch_ollama_embedding(*, model: str, input_text: str, base_url: str | None = None, timeout_seconds: float = 30.0, keep_alive: str | None = None) -> dict[str, Any]:
    import httpx

    resolved = normalize_base_url(base_url)
    native_model = normalize_ollama_model_name(model) or model
    request = build_embedding_request(model=native_model, input_text=input_text, keep_alive=keep_alive)
    metadata = {
        "provider": "ollama",
        "model": native_model,
        "input_length": len(str(input_text or "")),
        "input_preview": str(input_text or "")[:160],
        "source": "Ollama /api/embed",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(f"{resolved}/api/embed", json=request)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        return {"ok": False, "status": "unavailable", "error": str(exc), "metadata": metadata, "embedding": None}
    normalized = normalize_embedding_response(payload if isinstance(payload, dict) else {}, model=native_model)
    metrics = normalize_ollama_runtime_metrics(payload if isinstance(payload, dict) else {})
    embedding_value = None
    if isinstance(payload, dict):
        embeddings = payload.get("embeddings") or payload.get("embedding")
        embedding_value = embeddings
    return {
        "ok": True,
        "status": "available",
        "metadata": {**metadata, "dimensions": normalized.get("dimensions"), "embedding_count": normalized.get("embedding_count")},
        "result": normalized,
        "metrics": metrics,
        "embedding": embedding_value,
    }


def build_modelcore_process_trace_item(model: dict[str, Any], *, health: dict[str, Any] | None = None) -> dict[str, Any]:
    safe_model = redact_ollama_value(model)
    return {
        "kind": "model_snapshot",
        "subsystem": "ModelCore",
        "title": "Ollama model capability snapshot",
        "summary": f"ModelCore snapshot for {model.get('model') or model.get('name') or 'unknown'} via native Ollama metadata.",
        "status": "completed" if (health or {}).get("status") not in {"unavailable", "error"} else "warning",
        "badge": "ModelCore",
        "icon_id": "model-core",
        "details": {
            "provider": "ollama",
            "model": model.get("model") or model.get("name"),
            "capabilities": safe_model.get("capabilities"),
            "health": redact_ollama_value(health or {}),
            "loaded": bool(model.get("running") or model.get("loaded")),
            "running": bool(model.get("running")),
            "expires_at": model.get("expires_at") or "",
        },
        "metadata": {"provider": "ollama", "source_kind": "ollama_native_snapshot", "model": model.get("model") or model.get("name")},
    }
