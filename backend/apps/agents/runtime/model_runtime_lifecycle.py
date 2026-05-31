"""Side-effect-free model runtime lifecycle contracts.

These helpers normalize provider/model selection metadata for local-first model
runtime work. They do not call providers, execute models, persist prompts, or
store responses.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from backend.apps.agents.providers.ollama_native import infer_ollama_capabilities
from backend.apps.agents.providers.ollama_runtime import (
    build_effective_ollama_request_options,
    estimate_ollama_context_window,
)
from backend.apps.agents.providers.provider_health import is_local_model, normalize_ollama_model_name

THINKING_LEVELS = {"inherit", "auto", "off", "minimal", "low", "medium", "high", "xhigh"}
ROLE_PROFILES = {
    "planner_model",
    "builder_model",
    "reviewer_model",
    "debug_model",
    "summary_model",
    "compaction_model",
    "vision_model",
}
SAFE_BLOCKED_KEYS = {
    "prompt",
    "raw_prompt",
    "response",
    "raw_response",
    "message",
    "messages",
    "content",
    "body",
    "text",
    "chain_of_thought",
    "cot",
    "secret",
    "token",
    "api_key",
    "apikey",
    "password",
    "credential",
    "authorization",
}


@dataclass(frozen=True)
class ModelRoleProfile:
    role_profile: str
    preferred_provider: str | None = None
    preferred_model: str | None = None
    thinking_level: str = "auto"
    requires_tools: bool = False
    requires_vision: bool = False
    requires_structured_output: bool = False
    min_context_limit: int | None = None
    max_output_limit: int | None = None
    fallback_role_profile: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelRuntimeRequest:
    requested_model: str | None = None
    requested_provider: str | None = None
    requested_thinking_level: str = "inherit"
    role_profile: str | ModelRoleProfile | dict[str, Any] | None = None
    variant: str | None = None
    effective_config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelRuntimeResolution:
    provider_id: str
    model_id: str
    local_model_name: str | None = None
    role_profile: ModelRoleProfile | None = None
    variant: str | None = None
    thinking_level: str = "auto"
    active_thinking: bool = False
    supports_thinking: bool | None = None
    supports_tools: bool | None = None
    supports_vision: bool | None = None
    supports_structured_output: bool | None = None
    supports_json: bool | None = None
    context_limit: int | None = None
    context_limit_source: str = "unknown"
    capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)
    capability_source: dict[str, str] = field(default_factory=dict)
    provider_health: dict[str, Any] = field(default_factory=dict)
    effective_options: dict[str, Any] = field(default_factory=dict)
    model_source: str = "request"
    source_chain: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    fallback_policy: dict[str, Any] = field(default_factory=dict)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized not in SAFE_BLOCKED_KEYS and not any(marker in normalized for marker in ("secret", "token", "password", "api_key", "credential", "authorization"))


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if _safe_key(k)}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return [_safe(v) for v in sorted(value, key=str)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def normalize_model_runtime_role_profile(value: Any) -> ModelRoleProfile | None:
    if value is None or value == "":
        return None
    if isinstance(value, ModelRoleProfile):
        return value
    profiles = build_default_model_role_profiles()
    if isinstance(value, str):
        normalized = value.strip().lower()
        return profiles.get(normalized) or ModelRoleProfile(role_profile=normalized or "custom_model")
    if isinstance(value, dict):
        name = _text(value.get("role_profile") or value.get("profile") or value.get("name") or value.get("id") or "custom_model").lower()
        base = profiles.get(name)
        payload = dict(value)
        payload["role_profile"] = name
        allowed = {field_name for field_name in ModelRoleProfile.__dataclass_fields__}
        clean = {key: payload[key] for key in payload if key in allowed}
        if base:
            merged = {**asdict(base), **clean}
            return ModelRoleProfile(**merged)
        return ModelRoleProfile(**clean)
    return None


def normalize_runtime_provider_id(model: Any = None, provider: Any = None) -> str:
    model_text = _text(model)
    provider_text = _text(provider).lower()
    if model_text.lower().startswith("ollama/"):
        return "ollama"
    if provider_text:
        return provider_text
    if model_text and is_local_model(model_text):
        return "ollama"
    return "unknown"


def normalize_runtime_thinking_level(value: Any) -> str:
    normalized = _text(value).lower() or "auto"
    return normalized if normalized in THINKING_LEVELS else "auto"


def normalize_runtime_model_id(model: Any = None, provider: Any = None) -> str:
    model_text = _text(model)
    provider_id = normalize_runtime_provider_id(model_text, provider)
    if not model_text or model_text == "auto":
        return "auto"
    if provider_id == "ollama":
        return f"ollama/{normalize_ollama_model_name(model_text)}"
    if "/" in model_text:
        return model_text
    return f"{provider_id}/{model_text}" if provider_id != "unknown" else model_text


def build_default_model_role_profiles() -> dict[str, ModelRoleProfile]:
    return {
        "planner_model": ModelRoleProfile("planner_model", preferred_provider="ollama", thinking_level="medium", requires_structured_output=True, min_context_limit=32_000, fallback_role_profile="builder_model"),
        "builder_model": ModelRoleProfile("builder_model", preferred_provider="ollama", thinking_level="medium", min_context_limit=32_000, fallback_role_profile="planner_model"),
        "reviewer_model": ModelRoleProfile("reviewer_model", preferred_provider="ollama", thinking_level="high", requires_structured_output=True, min_context_limit=32_000, fallback_role_profile="builder_model"),
        "debug_model": ModelRoleProfile("debug_model", preferred_provider="ollama", thinking_level="medium", min_context_limit=32_000, fallback_role_profile="builder_model"),
        "summary_model": ModelRoleProfile("summary_model", preferred_provider="ollama", thinking_level="low", max_output_limit=4_096, fallback_role_profile="builder_model"),
        "compaction_model": ModelRoleProfile("compaction_model", preferred_provider="ollama", thinking_level="low", min_context_limit=64_000, fallback_role_profile="summary_model"),
        "vision_model": ModelRoleProfile("vision_model", preferred_provider="ollama", thinking_level="auto", requires_vision=True, min_context_limit=16_000, fallback_role_profile="reviewer_model"),
    }


def resolve_model_role_profile(role_profile: Any, effective_config: dict[str, Any] | None = None) -> ModelRoleProfile | None:
    profile = normalize_model_runtime_role_profile(role_profile)
    if not profile:
        return None
    config = effective_config if isinstance(effective_config, dict) else {}
    preferred_models = config.get("preferred_models") if isinstance(config.get("preferred_models"), dict) else {}
    preferred_model = profile.preferred_model or preferred_models.get(profile.role_profile) or preferred_models.get(profile.role_profile.replace("_model", ""))
    thinking = profile.thinking_level
    if thinking == "inherit":
        thinking = normalize_runtime_thinking_level(config.get("thinking_level") or config.get("default_thinking_level") or "auto")
    return replace(profile, preferred_model=_text(preferred_model) or profile.preferred_model, thinking_level=normalize_runtime_thinking_level(thinking))


def _coerce_request(request: ModelRuntimeRequest | dict[str, Any]) -> ModelRuntimeRequest:
    if isinstance(request, ModelRuntimeRequest):
        return request
    data = dict(request or {}) if isinstance(request, dict) else {}
    return ModelRuntimeRequest(
        requested_model=data.get("requested_model") or data.get("model"),
        requested_provider=data.get("requested_provider") or data.get("provider"),
        requested_thinking_level=data.get("requested_thinking_level") or data.get("thinking_level") or "inherit",
        role_profile=data.get("role_profile"),
        variant=data.get("variant") or data.get("model_variant"),
        effective_config=data.get("effective_config") if isinstance(data.get("effective_config"), dict) else {},
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )


def _registry_candidates(registry: Any) -> list[dict[str, Any]]:
    if not isinstance(registry, dict):
        return []
    candidates: list[dict[str, Any]] = []
    for key, value in registry.items():
        if isinstance(value, dict) and key not in {"models", "items"}:
            candidates.append({"registry_key": key, **value})
    for collection_key in ("models", "items"):
        items = registry.get(collection_key)
        if isinstance(items, list):
            candidates.extend([item for item in items if isinstance(item, dict)])
    return candidates


def _registry_entry(registry: Any, local_model_name: str | None, model_id: str) -> dict[str, Any]:
    names = {model_id, _text(local_model_name), f"ollama/{_text(local_model_name)}"}
    names = {name for name in names if name}
    for entry in _registry_candidates(registry):
        entry_names = {_text(entry.get(key)) for key in ("registry_key", "value", "model", "name", "local_model_name", "id")}
        if names & {name for name in entry_names if name}:
            return entry
    return {}


def _capability_from_entry(entry: dict[str, Any], capabilities: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    direct_keys = [f"supports_{name}"] + (["supports_json"] if name == "json" else [])
    for key in direct_keys:
        if key in entry:
            return {"name": name, "supported": bool(entry.get(key)), "source": "registry", "reason": "registry"}
    nested = entry.get("capabilities") if isinstance(entry.get("capabilities"), dict) else {}
    item = nested.get(name) if isinstance(nested.get(name), dict) else None
    if item:
        return {"name": name, "supported": bool(item.get("supported")), "source": _text(item.get("source")) or "registry", "reason": _text(item.get("reason")) or "registry"}
    if name in nested and isinstance(nested.get(name), bool):
        return {"name": name, "supported": bool(nested.get(name)), "source": "registry", "reason": "registry"}
    return capabilities.get(name) or {"name": name, "supported": False, "source": "not_reported", "reason": "not_reported"}


def _context_limit(entry: dict[str, Any], local_model_name: str | None, provider_id: str) -> tuple[int | None, str]:
    for key in ("context_limit", "context_window", "configured_context_window", "loaded_context_window", "declared_context_window", "estimated_context_window"):
        parsed = _int_or_none(entry.get(key))
        if parsed:
            return parsed, "registry" if key != "estimated_context_window" else "inferred"
    if provider_id == "ollama" and local_model_name:
        return estimate_ollama_context_window(local_model_name), "inferred"
    return None, "unknown"


def _resolve_config_value(config: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = config.get(key)
        if value not in (None, "", "inherit"):
            return value
    return None


def resolve_model_runtime(request: ModelRuntimeRequest | dict[str, Any], local_registry: Any = None, provider_health: dict[str, Any] | None = None) -> ModelRuntimeResolution:
    req = _coerce_request(request)
    config = req.effective_config if isinstance(req.effective_config, dict) else {}
    role_profile = resolve_model_role_profile(req.role_profile, config)
    requested_model = _text(req.requested_model)
    model_source = "request" if requested_model and requested_model != "auto" else "auto_unresolved"
    model = requested_model if requested_model and requested_model != "auto" else ""
    if not model and role_profile and role_profile.preferred_model:
        model = role_profile.preferred_model
        model_source = "role_profile"
    if not model:
        model = _text(_resolve_config_value(config, "model", "default_model"))
        if model and model != "auto":
            model_source = "config_default_model"
    if not model or model == "auto":
        model = "auto"
        model_source = "auto_unresolved"

    provider = req.requested_provider or (role_profile.preferred_provider if role_profile else None) or _resolve_config_value(config, "provider")
    warnings: list[str] = []
    source_chain = [f"model_source:{model_source}"]
    if _text(req.requested_provider) and _text(model).lower().startswith("ollama/") and _text(req.requested_provider).lower() != "ollama":
        warnings.append("explicit_provider_conflicts_with_ollama_prefix")
        source_chain.append("provider_conflict:ollama_prefix_wins")
    provider_id = normalize_runtime_provider_id(model, provider)
    model_id = normalize_runtime_model_id(model, provider_id)
    local_model_name = normalize_ollama_model_name(model_id) if provider_id == "ollama" and model_id != "auto" else None
    entry = _registry_entry(local_registry, local_model_name, model_id)
    if entry:
        source_chain.append("registry:matched")

    inferred = infer_ollama_capabilities(local_model_name or model_id) if provider_id == "ollama" and model_id != "auto" else {}
    caps = {name: _capability_from_entry(entry, inferred, name) for name in ("thinking", "tools", "vision", "structured_output", "json")}
    capability_source = {name: _text(item.get("source")) or "unknown" for name, item in caps.items()}
    if any(source == "inferred" for source in capability_source.values()):
        source_chain.append("capabilities:inferred")
    if any(source == "not_reported" for source in capability_source.values()):
        source_chain.append("capabilities:not_reported")

    context_limit, context_source = _context_limit(entry, local_model_name, provider_id)
    if context_source == "inferred":
        source_chain.append("context_limit:inferred")

    thinking = normalize_runtime_thinking_level(req.requested_thinking_level)
    if thinking == "inherit":
        thinking = normalize_runtime_thinking_level(_resolve_config_value(config, "thinking_level", "default_thinking_level") or (role_profile.thinking_level if role_profile else "auto"))
    supports_thinking = bool(caps["thinking"].get("supported"))
    active_thinking = supports_thinking and thinking not in {"off", "auto"}
    if thinking not in {"off", "auto"} and not supports_thinking:
        warnings.append("thinking_requested_but_not_supported")
    if role_profile:
        if role_profile.requires_structured_output and not bool(caps["structured_output"].get("supported")):
            warnings.append("role_profile_requires_structured_output_not_reported")
        if role_profile.requires_vision and not bool(caps["vision"].get("supported")):
            warnings.append("role_profile_requires_vision_not_reported")
        if role_profile.min_context_limit and (not context_limit or context_limit < role_profile.min_context_limit):
            warnings.append("role_profile_min_context_not_met")

    effective_options: dict[str, Any] = {}
    if provider_id == "ollama" and model_id != "auto":
        effective_options = build_effective_ollama_request_options(
            requested_effort=thinking,
            supports_thinking=supports_thinking,
            supports_thinking_levels=False,
            structured_output={"requested": True} if role_profile and role_profile.requires_structured_output else None,
            config_source="model_runtime_lifecycle",
        )

    required_actions: list[str] = []
    if model_source == "auto_unresolved":
        required_actions.append("select_model")
    if warnings:
        required_actions.append("review_model_runtime_warnings")
    fallback_policy = {
        "requires_user_approval": bool(required_actions),
        "auto_switch_performed": False,
        "reason": "auto_unresolved" if model_source == "auto_unresolved" else (warnings[0] if warnings else "none"),
    }

    variant = req.variant or req.metadata.get("variant") or config.get("model_variant")
    return ModelRuntimeResolution(
        provider_id=provider_id,
        model_id=model_id,
        local_model_name=local_model_name,
        role_profile=role_profile,
        variant=_text(variant) or None,
        thinking_level=thinking,
        active_thinking=active_thinking,
        supports_thinking=supports_thinking,
        supports_tools=bool(caps["tools"].get("supported")),
        supports_vision=bool(caps["vision"].get("supported")),
        supports_structured_output=bool(caps["structured_output"].get("supported")),
        supports_json=bool(caps["json"].get("supported")),
        context_limit=context_limit,
        context_limit_source=context_source,
        capabilities=caps,
        capability_source=capability_source,
        provider_health=_safe(provider_health or {}),
        effective_options=_safe(effective_options),
        model_source=model_source,
        source_chain=source_chain,
        warnings=warnings,
        required_actions=required_actions,
        fallback_policy=fallback_policy,
    )


def dump_model_runtime_resolution(resolution: ModelRuntimeResolution | dict[str, Any]) -> dict[str, Any]:
    if isinstance(resolution, ModelRuntimeResolution):
        data = asdict(resolution)
    else:
        data = deepcopy(dict(resolution or {}))
    return _safe(data)


def build_model_runtime_trace_source(resolution: ModelRuntimeResolution | dict[str, Any]) -> dict[str, Any]:
    data = dump_model_runtime_resolution(resolution)
    return _safe({
        "source_kind": "model_runtime",
        "runtime_kind": "model_runtime_resolution",
        "provider_id": data.get("provider_id"),
        "model_id": data.get("model_id"),
        "local_model_name": data.get("local_model_name"),
        "role_profile": (data.get("role_profile") or {}).get("role_profile") if isinstance(data.get("role_profile"), dict) else None,
        "variant": data.get("variant"),
        "thinking_level": data.get("thinking_level"),
        "active_thinking": data.get("active_thinking"),
        "capability_source": data.get("capability_source"),
        "context_limit": data.get("context_limit"),
        "context_limit_source": data.get("context_limit_source"),
        "model_source": data.get("model_source"),
        "source_chain": data.get("source_chain"),
        "warnings": data.get("warnings"),
        "required_actions": data.get("required_actions"),
        "fallback_policy": data.get("fallback_policy"),
    })


def _attach_metadata(payload: Any, resolution: ModelRuntimeResolution | dict[str, Any]) -> Any:
    if not isinstance(payload, dict):
        return payload
    clone = deepcopy(payload)
    metadata = dict(clone.get("metadata") or {})
    metadata["model_runtime"] = dump_model_runtime_resolution(resolution)
    clone["metadata"] = metadata
    return clone


def attach_model_runtime_to_task_packet(task_packet: dict[str, Any], resolution: ModelRuntimeResolution | dict[str, Any]) -> dict[str, Any]:
    return _attach_metadata(task_packet, resolution)


def attach_model_runtime_to_handoff(handoff: dict[str, Any], resolution: ModelRuntimeResolution | dict[str, Any]) -> dict[str, Any]:
    return _attach_metadata(handoff, resolution)


def attach_model_runtime_to_process_trace_source(source: dict[str, Any], resolution: ModelRuntimeResolution | dict[str, Any]) -> dict[str, Any]:
    if not isinstance(source, dict):
        return source
    clone = deepcopy(source)
    clone["model_runtime"] = build_model_runtime_trace_source(resolution)
    return clone


def extract_model_runtime_from_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    runtime = metadata.get("model_runtime")
    return dump_model_runtime_resolution(runtime) if isinstance(runtime, dict) else None
