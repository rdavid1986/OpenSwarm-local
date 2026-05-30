"""Native Ollama capability and response contracts.

This module is deliberately side-effect-light. Pure normalizers are used by
tests and future runtime integrations without requiring Ollama to be running.
Network helpers are best-effort, bounded by short timeouts, and never start
Ollama, install models, execute tools, or persist prompts/responses.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any, Callable

from backend.apps.agents.providers.provider_health import normalize_ollama_model_name


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
REASONING_LEVELS = {"auto", "off", "minimal", "low", "medium", "high", "xhigh"}
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "password",
    "private_key",
    "prompt",
    "raw_prompt",
    "raw_response",
    "refresh_token",
    "response",
    "secret",
    "session",
    "token",
}


def normalize_base_url(base_url: str | None = None) -> str:
    return (base_url or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(
        marker in normalized
        for marker in ("api_key", "token", "password", "secret", "credential", "private_key", "authorization", "cookie")
    )


def redact_ollama_value(value: Any, *, max_text: int = 600) -> Any:
    """Return a bounded, redacted snapshot safe for metadata and tests."""

    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:60]:
            output[str(key)] = "[redacted]" if _is_sensitive_key(key) else redact_ollama_value(item, max_text=max_text)
        if len(value) > 60:
            output["__truncated__"] = f"+{len(value) - 60} more fields"
        return output
    if isinstance(value, list):
        visible = [redact_ollama_value(item, max_text=max_text) for item in value[:40]]
        return visible + ([f"+{len(value) - 40} more"] if len(value) > 40 else [])
    if isinstance(value, str):
        clean = value
        clean = clean[:max_text].rstrip() + ("..." if len(clean) > max_text else "")
        return clean
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:max_text]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _first_positive_int(*values: Any) -> int | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            parsed = int(float(value))
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


def _extract_context_window(show_payload: dict[str, Any]) -> tuple[int | None, str]:
    model_info = show_payload.get("model_info") if isinstance(show_payload.get("model_info"), dict) else {}
    for key in (
        "llama.context_length",
        "qwen2.context_length",
        "qwen3.context_length",
        "qwen35moe.context_length",
        "context_length",
        "num_ctx",
    ):
        parsed = _first_positive_int(model_info.get(key))
        if parsed:
            return parsed, f"Ollama /api/show model_info {key}"

    parameters = str(show_payload.get("parameters") or "")
    for line in parameters.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].lower() in {"num_ctx", "context_length"}:
            parsed = _first_positive_int(parts[1])
            if parsed:
                return parsed, "Ollama /api/show parameters"

    modelfile = str(show_payload.get("modelfile") or "")
    for line in modelfile.splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0].upper() == "PARAMETER" and parts[1].lower() == "num_ctx":
            parsed = _first_positive_int(parts[2])
            if parsed:
                return parsed, "Ollama /api/show Modelfile PARAMETER num_ctx"
    return None, "not_reported"


def _estimate_context_window(name: str, family: str | None) -> tuple[int, str]:
    lower = f"{name} {family or ''}".lower()
    if "qwen3" in lower or "qwen35" in lower:
        return 262_144, "inferred:name_or_family"
    if "qwen2" in lower or "llama3" in lower or "mistral" in lower:
        return 32_768, "inferred:name_or_family"
    if "codellama" in lower:
        return 16_384, "inferred:name_or_family"
    return 32_000, "inferred:default"


def _capability(name: str, supported: bool, source: str, reason: str = "") -> dict[str, Any]:
    return {"name": name, "supported": bool(supported), "source": source, "reason": reason or source}


def infer_ollama_capabilities(model_name: str, show_payload: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Normalize reported/inferred Ollama model capabilities without inventing certainty."""

    show = show_payload if isinstance(show_payload, dict) else {}
    details = show.get("details") if isinstance(show.get("details"), dict) else {}
    family = str(details.get("family") or "").lower()
    families = [str(item).lower() for item in _as_list(details.get("families"))]
    reported = {str(item).lower() for item in _as_list(show.get("capabilities"))}
    name = str(model_name or "").lower()
    blob = " ".join([name, family, *families])

    def has_reported(*tokens: str) -> bool:
        return any(token in reported for token in tokens)

    vision_inferred = any(token in blob for token in ("vision", "vl", "llava", "bakllava", "moondream"))
    embedding_inferred = any(token in blob for token in ("embed", "embedding", "nomic-embed", "bge", "all-minilm"))
    thinking_inferred = any(token in blob for token in ("qwen3", "deepseek-r1", "gpt-oss", "thinking"))
    tools_inferred = any(token in blob for token in ("qwen", "llama3", "mistral", "granite", "command-r"))

    return {
        "thinking": _capability(
            "thinking",
            has_reported("thinking") or thinking_inferred,
            "reported" if has_reported("thinking") else ("inferred" if thinking_inferred else "not_reported"),
        ),
        "tools": _capability(
            "tools",
            has_reported("tools", "tool") or tools_inferred,
            "reported" if has_reported("tools", "tool") else ("inferred" if tools_inferred else "not_reported"),
        ),
        "vision": _capability(
            "vision",
            has_reported("vision", "images") or vision_inferred,
            "reported" if has_reported("vision", "images") else ("inferred" if vision_inferred else "not_reported"),
        ),
        "embedding": _capability(
            "embedding",
            has_reported("embedding", "embeddings", "embed") or embedding_inferred,
            "reported" if has_reported("embedding", "embeddings", "embed") else ("inferred" if embedding_inferred else "not_reported"),
        ),
        "structured_output": _capability("structured_output", True, "ollama_native_option", "format=json or JSON Schema request option"),
        "json": _capability("json", True, "ollama_native_option", "format=json request option"),
        "keep_alive": _capability("keep_alive", True, "ollama_native_option", "keep_alive request option and /api/ps residency"),
    }


def normalize_ollama_model_snapshot(
    model: dict[str, Any],
    *,
    show_payload: dict[str, Any] | None = None,
    running_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = str(model.get("name") or model.get("model") or "").strip()
    show = show_payload if isinstance(show_payload, dict) else {}
    details = show.get("details") if isinstance(show.get("details"), dict) else model.get("details") if isinstance(model.get("details"), dict) else {}
    running = running_payload if isinstance(running_payload, dict) else {}
    context_window, context_source = _extract_context_window(show)
    estimated_context, estimated_source = _estimate_context_window(name, details.get("family"))
    capabilities = infer_ollama_capabilities(name, show)
    reported_caps = _as_list(show.get("capabilities"))

    return {
        "provider": "ollama",
        "model": name,
        "name": name,
        "family": details.get("family") or "unknown",
        "families": details.get("families") or [],
        "parameter_size": details.get("parameter_size") or "unknown",
        "quantization_level": details.get("quantization_level") or "unknown",
        "format": details.get("format") or "unknown",
        "size": model.get("size") or show.get("size") or running.get("size") or None,
        "digest": model.get("digest") or show.get("digest") or running.get("digest") or "",
        "modified_at": model.get("modified_at") or show.get("modified_at") or "",
        "expires_at": running.get("expires_at") or "",
        "running": bool(running),
        "capabilities_reported": reported_caps,
        "capabilities": capabilities,
        "context_window": context_window or estimated_context,
        "context_window_source": context_source if context_window else estimated_source,
        "context_window_estimated": None if context_window else estimated_context,
        "supports_thinking": capabilities["thinking"]["supported"],
        "supports_tools": capabilities["tools"]["supported"],
        "supports_vision": capabilities["vision"]["supported"],
        "supports_embedding": capabilities["embedding"]["supported"],
        "supports_structured_output": capabilities["structured_output"]["supported"],
        "supports_json": capabilities["json"]["supported"],
        "supports_keep_alive": capabilities["keep_alive"]["supported"],
        "metadata_source": "Ollama /api/tags + /api/show",
        "availability_source": "Ollama /api/tags" + (" + /api/ps" if running else ""),
    }


def build_ollama_capability_snapshot_from_payloads(
    *,
    base_url: str | None = None,
    version_payload: dict[str, Any] | None = None,
    tags_payload: dict[str, Any] | None = None,
    show_payloads: dict[str, dict[str, Any]] | None = None,
    ps_payload: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    resolved_base_url = normalize_base_url(base_url)
    tag_models = _as_list((tags_payload or {}).get("models"))
    running_models_raw = _as_list((ps_payload or {}).get("models"))
    running_by_name = {
        str(item.get("name") or item.get("model") or ""): item
        for item in running_models_raw
        if isinstance(item, dict)
    }
    shows = show_payloads or {}
    models = [
        normalize_ollama_model_snapshot(
            item,
            show_payload=shows.get(str(item.get("name") or item.get("model") or "")),
            running_payload=running_by_name.get(str(item.get("name") or item.get("model") or "")),
        )
        for item in tag_models
        if isinstance(item, dict)
    ]

    health = "available" if version_payload or tag_models else "unknown"
    if errors and not (version_payload or tag_models):
        health = "unavailable"
    elif errors and (version_payload or tag_models):
        health = "degraded"

    return {
        "snapshot_kind": "ollama_native_capability_snapshot",
        "provider": "ollama",
        "base_url": resolved_base_url,
        "health": health,
        "version": (version_payload or {}).get("version") or "unknown",
        "models": models,
        "running_models": [redact_ollama_value(item) for item in running_models_raw if isinstance(item, dict)],
        "model_count": len(models),
        "running_model_count": len(running_by_name),
        "metadata_source": "Ollama /api/version + /api/tags + /api/show + /api/ps",
        "errors": errors or [],
        "warnings": [],
    }


def _request_json(url: str, *, method: str = "GET", body: dict[str, Any] | None = None, timeout_seconds: float = 2.0) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw or "{}")
    return parsed if isinstance(parsed, dict) else {}


def fetch_ollama_capability_snapshot(
    *,
    base_url: str | None = None,
    timeout_seconds: float = 2.0,
    request_json: Callable[..., dict[str, Any]] = _request_json,
) -> dict[str, Any]:
    resolved_base_url = normalize_base_url(base_url)
    errors: list[str] = []

    def get(path: str) -> dict[str, Any]:
        try:
            return request_json(f"{resolved_base_url}{path}", timeout_seconds=timeout_seconds)
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, OSError) as exc:
            errors.append(f"{path}: {exc}")
            return {}

    version = get("/api/version")
    tags = get("/api/tags")
    ps = get("/api/ps")
    shows: dict[str, dict[str, Any]] = {}
    for item in _as_list(tags.get("models")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if not name:
            continue
        try:
            shows[name] = request_json(f"{resolved_base_url}/api/show", method="POST", body={"model": name}, timeout_seconds=timeout_seconds)
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, OSError) as exc:
            errors.append(f"/api/show {name}: {exc}")

    snapshot = build_ollama_capability_snapshot_from_payloads(
        base_url=resolved_base_url,
        version_payload=version,
        tags_payload=tags,
        show_payloads=shows,
        ps_payload=ps,
        errors=errors,
    )
    if errors and not tags and not version:
        snapshot["health"] = "unavailable"
    elif errors:
        snapshot["health"] = "degraded"
    return snapshot


def normalize_reasoning_effort(
    requested_level: str | None,
    *,
    supports_thinking: bool,
    supports_levels: bool = False,
) -> dict[str, Any]:
    requested = str(requested_level or "auto").strip().lower()
    if requested not in REASONING_LEVELS:
        requested = "auto"
    if not supports_thinking:
        return {
            "requested_level": requested,
            "applied_level": "off",
            "ollama_think": False,
            "source": "fallback",
            "fallback_reason": "thinking unsupported",
        }
    if requested == "off":
        return {"requested_level": requested, "applied_level": "off", "ollama_think": False, "source": "requested", "fallback_reason": ""}
    if not supports_levels:
        applied = "minimal" if requested in {"minimal", "low", "auto"} else "medium"
        return {
            "requested_level": requested,
            "applied_level": applied,
            "ollama_think": True,
            "source": "degraded_to_boolean_think",
            "fallback_reason": "Ollama/model level-specific thinking not reported",
        }
    return {"requested_level": requested, "applied_level": requested, "ollama_think": requested != "off", "source": "reported", "fallback_reason": ""}


def build_ollama_chat_options(
    *,
    reasoning_effort: str | None = "auto",
    supports_thinking: bool = False,
    supports_thinking_levels: bool = False,
    keep_alive: str | None = None,
    structured_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effort = normalize_reasoning_effort(reasoning_effort, supports_thinking=supports_thinking, supports_levels=supports_thinking_levels)
    payload: dict[str, Any] = {"think": effort["ollama_think"], "metadata": {"reasoning_effort": effort}}
    if keep_alive:
        payload["keep_alive"] = keep_alive
    if structured_output:
        payload.update(build_structured_output_request(**structured_output))
    return payload


def normalize_ollama_stream_chunks(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    thinking_parts: list[str] = []
    content_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        message = chunk.get("message") if isinstance(chunk.get("message"), dict) else {}
        thinking = chunk.get("thinking") or message.get("thinking")
        content = message.get("content") if "message" in chunk else chunk.get("response") or chunk.get("content")
        if thinking:
            thinking_parts.append(str(thinking))
        if content:
            content_parts.append(str(content))
        tool_calls.extend(normalize_ollama_tool_calls(message.get("tool_calls") or chunk.get("tool_calls")))
        for key in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
            if key in chunk:
                metrics[key] = chunk[key]
    return {
        "thinking": "".join(thinking_parts),
        "content": "".join(content_parts),
        "tool_calls": tool_calls,
        "metrics": normalize_ollama_runtime_metrics(metrics) if metrics else {},
        "thinking_visible_to_user": False,
        "thinking_metadata": normalize_ollama_thinking_metadata("".join(thinking_parts)),
        "summary_source": "native_ollama_thinking" if thinking_parts else "fallback",
    }


def normalize_ollama_thinking_metadata(thinking: Any, *, safe_summary: str | None = None) -> dict[str, Any]:
    text = str(thinking or "")
    return {
        "has_native_thinking": bool(text),
        "thinking_available": bool(text),
        "thinking_redacted": bool(text),
        "thinking_summary": str(safe_summary or "")[:600],
        "fallback_reason": "" if text else "not_reported",
        "visible_to_user": False,
        "source": "ollama_native_thinking_metadata",
    }


def normalize_ollama_tool_calls(value: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for idx, call in enumerate(_as_list(value)):
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else call
        name = str(function.get("name") or call.get("name") or "unknown").strip() or "unknown"
        arguments = function.get("arguments") or call.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                parsed_arguments = json.loads(arguments)
                arguments = parsed_arguments if isinstance(parsed_arguments, dict) else {"value": arguments}
            except Exception:
                arguments = {"value": arguments}
        calls.append({
            "tool_call_id": call.get("id") or f"ollama_tool_call_{idx}",
            "tool_name": name,
            "arguments": redact_ollama_value(arguments),
            "arguments_redacted": True,
            "source": "ollama_native_tool_calls",
            "source_kind": "tool_trace",
            "status": "requested",
            "executed": False,
            "approved": False,
        })
    return calls


def normalize_ollama_runtime_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    total = _first_positive_int(payload.get("total_duration"))
    load = _first_positive_int(payload.get("load_duration"))
    eval_count = _first_positive_int(payload.get("eval_count")) or 0
    eval_duration = _first_positive_int(payload.get("eval_duration")) or 0
    throughput = (eval_count / (eval_duration / 1_000_000_000)) if eval_count and eval_duration else None
    return {
        "metric_kind": "ollama_runtime_metrics",
        "provider": "ollama",
        "model": payload.get("model") or "",
        "total_duration_ns": total,
        "load_duration_ns": load,
        "prompt_eval_count": _first_positive_int(payload.get("prompt_eval_count")),
        "prompt_eval_duration_ns": _first_positive_int(payload.get("prompt_eval_duration")),
        "eval_count": eval_count or None,
        "eval_duration_ns": eval_duration or None,
        "tokens_per_second": round(throughput, 3) if throughput else None,
        "cold_start_likely": bool(load and load > 0),
        "source": "ollama_response_metrics",
    }


def build_structured_output_request(
    *,
    requested: bool = True,
    schema: dict[str, Any] | None = None,
    json_mode: bool = True,
) -> dict[str, Any]:
    if not requested:
        return {"metadata": {"structured_output": {"requested": False, "applied": False, "fallback_reason": "not_requested"}}}
    if schema:
        return {"format": deepcopy(schema), "metadata": {"structured_output": {"requested": True, "applied": True, "schema_used": True}}}
    if json_mode:
        return {"format": "json", "metadata": {"structured_output": {"requested": True, "applied": True, "schema_used": False}}}
    return {"metadata": {"structured_output": {"requested": True, "applied": False, "fallback_reason": "json_mode_disabled"}}}


def validate_structured_output(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"validation_status": "valid", "value": redact_ollama_value(value), "error": ""}
    if not isinstance(value, str):
        return {"validation_status": "invalid", "value": None, "error": "not_json_text"}
    try:
        parsed = json.loads(value)
    except Exception as exc:
        return {"validation_status": "invalid", "value": None, "error": str(exc)}
    return {"validation_status": "valid" if isinstance(parsed, dict) else "warning", "value": redact_ollama_value(parsed), "error": ""}


def build_embedding_request(*, model: str, input_text: str, keep_alive: str | None = None, max_chars: int = 8000) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": normalize_ollama_model_name(model) or model, "input": str(input_text or "")[:max_chars]}
    if keep_alive:
        payload["keep_alive"] = keep_alive
    return payload


def normalize_embedding_response(payload: dict[str, Any], *, model: str) -> dict[str, Any]:
    embeddings = payload.get("embeddings") or payload.get("embedding") or []
    first = embeddings[0] if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list) else embeddings
    dimensions = len(first) if isinstance(first, list) else None
    return {
        "result_kind": "ollama_embedding_result",
        "provider": "ollama",
        "model": normalize_ollama_model_name(model) or model,
        "dimensions": dimensions,
        "embedding_count": len(embeddings) if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list) else (1 if isinstance(first, list) else 0),
        "source": "Ollama /api/embed",
        "metrics": normalize_ollama_runtime_metrics(payload),
    }


def normalize_vision_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    return {
        "attachment_kind": "ollama_vision_input",
        "mime_type": attachment.get("mime_type") or attachment.get("media_type") or "unknown",
        "size": attachment.get("size") or attachment.get("size_bytes"),
        "source": attachment.get("source") or "unavailable",
        "metadata": redact_ollama_value(attachment.get("metadata") if isinstance(attachment.get("metadata"), dict) else {}),
        "base64_present": bool(attachment.get("data") or attachment.get("base64")),
    }


def build_keep_alive_policy(value: str | None = None, *, running_model: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "policy_kind": "ollama_keep_alive_policy",
        "keep_alive": value or "default",
        "supports_keep_alive": True,
        "running": bool(running_model),
        "expires_at": (running_model or {}).get("expires_at") or "",
        "source": "Ollama request keep_alive + /api/ps",
    }


def build_modelfile_role_profile(role: str) -> dict[str, Any]:
    normalized = str(role or "Coder").strip() or "Coder"
    profile_notes = {
        "Planner": "Plan tasks and dependencies; do not execute tools.",
        "Coder": "Implement focused code changes with tests.",
        "Reviewer": "Review outputs and risks without mutating files.",
        "SkillBuilder": "Draft reusable skill instructions safely.",
        "VisionDebugger": "Analyze visual evidence when model supports vision.",
    }
    return {
        "profile_kind": "ollama_modelfile_role_profile",
        "role": normalized,
        "system": profile_notes.get(normalized, "Operate safely within OpenSwarm policy."),
        "template": "unavailable",
        "parameters": {},
        "messages": [],
        "license": "not_provided",
        "source": "openswarm_contract",
        "provenance": "generated_contract_only",
        "risk_notes": ["Does not run ollama create automatically.", "Requires explicit approval before creating models."],
    }


def normalize_openai_compatibility_adapter_metadata(*, native_snapshot: dict[str, Any] | None = None, used_compatibility: bool = False) -> dict[str, Any]:
    return {
        "adapter_kind": "ollama_openai_compatibility_metadata",
        "provider": "ollama",
        "api_mode": "openai-compatible" if used_compatibility else "native",
        "capability_source": "native_ollama_snapshot",
        "native_snapshot_available": bool(native_snapshot),
        "compatibility_is_primary_capability_source": False,
    }
