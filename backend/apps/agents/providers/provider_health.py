"""Reusable local model provider health checks.

This module is intentionally small and side-effect free: it never starts
Ollama, installs models, or retries in loops. Callers can use it as a fast
preflight before model-dependent flows.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_REQUIRED_ACTION = (
    "Abrí Ollama o ejecutá `ollama serve`, verificá que el modelo esté instalado con `ollama list`."
)


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


def check_local_model_provider_health(
    model: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 2.0,
) -> dict[str, Any]:
    """Check Ollama availability via GET /api/tags and normalize the result."""

    resolved_base_url = _normalize_base_url(base_url)
    normalized_model = normalize_ollama_model_name(model)
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
        return _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=f"HTTP {exc.code}: {detail}",
        )
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        return _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=str(exc),
        )
    except Exception as exc:
        return _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=str(exc),
        )

    if status_code != 200:
        return _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=f"HTTP {status_code}",
        )

    try:
        payload = json.loads(raw)
    except Exception as exc:
        return _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="unavailable",
            reason=ollama_unavailable_message(resolved_base_url),
            error_detail=f"Invalid JSON from Ollama /api/tags: {exc}",
        )

    available_models = _available_model_names(payload)
    if normalized_model and normalized_model not in available_models:
        return _result(
            ok=False,
            base_url=resolved_base_url,
            model=normalized_model,
            status="model_missing",
            reason=f"El modelo Ollama '{normalized_model}' no está instalado en {resolved_base_url}",
            available_models=available_models,
            error_detail="Model not found in /api/tags.",
        )

    return _result(
        ok=True,
        base_url=resolved_base_url,
        model=normalized_model,
        status="available",
        reason="Ollama está disponible.",
        available_models=available_models,
    )
