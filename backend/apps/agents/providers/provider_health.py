"""Reusable local model provider health checks.

This module is intentionally small and side-effect free: it never starts
Ollama, installs models, or retries in loops. Callers can use it as a fast
preflight before model-dependent flows.
"""

from __future__ import annotations

import copy
import json
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_REQUIRED_ACTION = (
    "Abrí Ollama o ejecutá `ollama serve`, verificá que el modelo esté instalado con `ollama list`."
)
DEFAULT_PROVIDER_HEALTH_CACHE_TTL_SECONDS = 5.0
_PROVIDER_HEALTH_CACHE: dict[tuple[str, str | None], tuple[float, dict[str, Any]]] = {}


def _normalize_base_url(base_url: str | None) -> str:
    return (base_url or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def normalize_ollama_model_name(model: str | None) -> str | None:
    """Return the Ollama-native model name, if provided."""

    value = str(model or "").strip()
    if not value:
        return None
    if value.startswith("ollama/"):
        value = value[len("ollama/") :]
    return value or None


def is_local_model(model: str | None) -> bool:
    """Best-effort detection for local/Ollama model identifiers.

    The backend paths using this helper are already local-provider paths; this
    function deliberately remains conservative for global routing while still
    recognizing bare Ollama model names used by OpenSwarm defaults.
    """

    value = str(model or "").strip().lower()
    if not value:
        return False
    if value.startswith("ollama/"):
        return True
    if "/" in value:
        return False
    if ":" in value:
        return True
    return value.startswith(("qwen", "codellama", "llama", "mistral", "deepseek", "phi", "gemma"))


def ollama_unavailable_message(base_url: str | None) -> str:
    return f"Ollama no está corriendo o no responde en {_normalize_base_url(base_url)}"


def _result(
    *,
    ok: bool,
    base_url: str,
    model: str | None,
    status: str,
    reason: str,
    available_models: list[str] | None = None,
    error_detail: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "provider": "ollama",
        "base_url": base_url,
        "model": model,
        "status": status,
        "reason": reason,
        "available_models": available_models or [],
        "error_detail": error_detail or "",
        "required_action": OLLAMA_REQUIRED_ACTION,
    }


def _available_model_names(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    models = payload.get("models")
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for item in models:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _cache_and_return(
    cache_key: tuple[str, str | None],
    health: dict[str, Any],
    *,
    cache_ttl_seconds: float,
    use_cache: bool,
) -> dict[str, Any]:
    if use_cache and cache_ttl_seconds > 0:
        _PROVIDER_HEALTH_CACHE[cache_key] = (time.monotonic(), copy.deepcopy(health))
    return health


def clear_provider_health_cache() -> None:
    _PROVIDER_HEALTH_CACHE.clear()


def check_local_model_provider_health(
    model: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 2.0,
    cache_ttl_seconds: float = DEFAULT_PROVIDER_HEALTH_CACHE_TTL_SECONDS,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Check Ollama availability via GET /api/tags and normalize the result.

    A short in-memory TTL avoids repeated /api/tags calls when multiple
    model-dependent steps run in the same local action sequence.
    """

    resolved_base_url = _normalize_base_url(base_url)
    normalized_model = normalize_ollama_model_name(model)
    cache_key = (resolved_base_url, normalized_model)
    now = time.monotonic()
    if use_cache and cache_ttl_seconds > 0:
        cached = _PROVIDER_HEALTH_CACHE.get(cache_key)
        if cached:
            cached_at, cached_health = cached
            if now - cached_at <= cache_ttl_seconds:
                return copy.deepcopy(cached_health)

    req = urllib.request.Request(f"{resolved_base_url}/api/tags", method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status_code = int(getattr(resp, "status", None) or getattr(resp, "code", None) or 200)
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        return _cache_and_return(cache_key, _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=f"HTTP {exc.code}: {detail}",
        ), cache_ttl_seconds=cache_ttl_seconds, use_cache=use_cache)
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return _cache_and_return(cache_key, _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=str(exc),
        ), cache_ttl_seconds=cache_ttl_seconds, use_cache=use_cache)
    except Exception as exc:
        return _cache_and_return(cache_key, _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=str(exc),
        ), cache_ttl_seconds=cache_ttl_seconds, use_cache=use_cache)

    if status_code != 200:
        return _cache_and_return(cache_key, _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=f"HTTP {status_code}",
        ), cache_ttl_seconds=cache_ttl_seconds, use_cache=use_cache)

    try:
        payload = json.loads(raw)
    except Exception as exc:
        return _cache_and_return(cache_key, _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=f"Invalid JSON from Ollama /api/tags: {exc}",
        ), cache_ttl_seconds=cache_ttl_seconds, use_cache=use_cache)

    available_models = _available_model_names(payload)
    if normalized_model and normalized_model not in available_models:
        return _cache_and_return(cache_key, _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="model_missing",
            reason=f"El modelo Ollama '{normalized_model}' no está instalado en {resolved_base_url}",
            available_models=available_models,
            error_detail="Model not found in /api/tags.",
        ), cache_ttl_seconds=cache_ttl_seconds, use_cache=use_cache)

    return _cache_and_return(cache_key, _result(
        ok=True,
        base_url=resolved_base_url,
        model=normalized_model,
        status="available",
        reason="Ollama está disponible.",
        available_models=available_models,
    ), cache_ttl_seconds=cache_ttl_seconds, use_cache=use_cache)
