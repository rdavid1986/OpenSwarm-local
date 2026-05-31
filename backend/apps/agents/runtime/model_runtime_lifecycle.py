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


@dataclass(frozen=True)
class ModelContextBudget:
    context_limit: int | None = None
    context_limit_source: str = "unknown"
    output_limit: int | None = None
    output_limit_source: str = "unknown"
    reserved_output_tokens: int = 0
    reserved_tool_tokens: int = 0
    reserved_mcp_tokens: int = 0
    reserved_skill_tokens: int = 0
    reserved_handoff_tokens: int = 0
    reserved_evidence_tokens: int = 0
    reserved_memory_tokens: int = 0
    reserved_final_answer_tokens: int = 0
    reserved_recovery_tokens: int = 0
    available_input_tokens: int | None = None
    estimated_input_tokens: int | None = None
    estimated_total_tokens: int | None = None
    usage_ratio: float | None = None
    status: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextBudgetInput:
    resolution: ModelRuntimeResolution | dict[str, Any] | None = None
    estimated_input_tokens: int | None = None
    estimated_tool_tokens: int | None = None
    estimated_mcp_tokens: int | None = None
    estimated_skill_tokens: int | None = None
    estimated_handoff_tokens: int | None = None
    estimated_evidence_tokens: int | None = None
    estimated_memory_tokens: int | None = None
    requested_output_tokens: int | None = None
    task_type: str | None = None
    mode: str | None = None
    role_profile: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelLongTaskHealth:
    provider_id: str = "unknown"
    model_id: str = "auto"
    role_profile: str = "unknown"
    status: str = "unknown"
    provider_status: str = "unknown"
    context_status: str = "unknown"
    stream_status: str = "unknown"
    timeout_status: str = "unknown"
    output_status: str = "unknown"
    capability_status: str = "unknown"
    risks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_continue: bool = True
    should_pause: bool = False
    should_escalate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LongTaskHealthInput:
    resolution: ModelRuntimeResolution | dict[str, Any] | None = None
    context_budget: ModelContextBudget | dict[str, Any] | None = None
    provider_health: dict[str, Any] | None = None
    elapsed_ms: int | None = None
    timeout_ms: int | None = None
    stream_last_event_ms_ago: int | None = None
    output_truncated: bool | None = None
    missing_capabilities: list[str] = field(default_factory=list)
    retry_count: int = 0
    task_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelRuntimeEscalationDecision:
    decision: str = "continue_current_model"
    reason: str = "healthy"
    current_provider_id: str = "unknown"
    current_model_id: str = "auto"
    suggested_provider_id: str | None = None
    suggested_model_id: str | None = None
    suggested_role_profile: str | None = None
    requires_user_approval: bool = False
    allowed_without_approval: bool = True
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    source_chain: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeEscalationInput:
    resolution: ModelRuntimeResolution | dict[str, Any] | None = None
    health: ModelLongTaskHealth | dict[str, Any] | None = None
    context_budget: ModelContextBudget | dict[str, Any] | None = None
    available_models: list[dict[str, Any]] | None = None
    preferred_models: dict[str, Any] | None = None
    role_profile: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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



def _dump_dataclass_or_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "__dataclass_fields__"):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return _safe(deepcopy(value))
    return {}


def _resolution_data(resolution: ModelRuntimeResolution | dict[str, Any] | None) -> dict[str, Any]:
    return dump_model_runtime_resolution(resolution) if isinstance(resolution, (ModelRuntimeResolution, dict)) else {}


def _coerce_context_budget_input(value: ContextBudgetInput | dict[str, Any]) -> ContextBudgetInput:
    if isinstance(value, ContextBudgetInput):
        return value
    data = dict(value or {}) if isinstance(value, dict) else {}
    return ContextBudgetInput(
        resolution=data.get("resolution"),
        estimated_input_tokens=_int_or_none(data.get("estimated_input_tokens")),
        estimated_tool_tokens=_int_or_none(data.get("estimated_tool_tokens")),
        estimated_mcp_tokens=_int_or_none(data.get("estimated_mcp_tokens")),
        estimated_skill_tokens=_int_or_none(data.get("estimated_skill_tokens")),
        estimated_handoff_tokens=_int_or_none(data.get("estimated_handoff_tokens")),
        estimated_evidence_tokens=_int_or_none(data.get("estimated_evidence_tokens")),
        estimated_memory_tokens=_int_or_none(data.get("estimated_memory_tokens")),
        requested_output_tokens=_int_or_none(data.get("requested_output_tokens")),
        task_type=data.get("task_type"),
        mode=data.get("mode"),
        role_profile=data.get("role_profile"),
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )


def estimate_runtime_token_count(value: Any, *, chars_per_token: int = 4) -> int:
    """Estimate tokens from safe synthetic values without provider calls."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        divisor = max(1, int(chars_per_token or 4))
        return max(1, (len(value) + divisor - 1) // divisor) if value else 0
    if isinstance(value, dict):
        return sum(estimate_runtime_token_count(k, chars_per_token=chars_per_token) + estimate_runtime_token_count(v, chars_per_token=chars_per_token) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return sum(estimate_runtime_token_count(item, chars_per_token=chars_per_token) for item in value)
    return estimate_runtime_token_count(str(value), chars_per_token=chars_per_token)


def build_context_window_budget(input: ContextBudgetInput | dict[str, Any]) -> ModelContextBudget:
    budget_input = _coerce_context_budget_input(input)
    resolution = _resolution_data(budget_input.resolution)
    context_limit = _int_or_none(resolution.get("context_limit"))
    context_limit_source = _text(resolution.get("context_limit_source")) or "unknown"
    role_profile = resolution.get("role_profile") if isinstance(resolution.get("role_profile"), dict) else {}
    requested_output = _int_or_none(budget_input.requested_output_tokens)
    profile_output = _int_or_none(role_profile.get("max_output_limit"))
    output_limit = requested_output or profile_output
    output_limit_source = "request" if requested_output else ("role_profile" if profile_output else "unknown")

    reserved_output = output_limit or 0
    reserved_tool = _int_or_none(budget_input.estimated_tool_tokens) or 0
    reserved_mcp = _int_or_none(budget_input.estimated_mcp_tokens) or 0
    reserved_skill = _int_or_none(budget_input.estimated_skill_tokens) or 0
    reserved_handoff = _int_or_none(budget_input.estimated_handoff_tokens) or 0
    reserved_evidence = _int_or_none(budget_input.estimated_evidence_tokens) or 0
    reserved_memory = _int_or_none(budget_input.estimated_memory_tokens) or 0
    reserved_final = min(max(reserved_output, 0), 4096) if reserved_output else 0
    reserved_recovery = max(256, int((context_limit or 4096) * 0.03)) if context_limit else 0
    reserves = reserved_output + reserved_tool + reserved_mcp + reserved_skill + reserved_handoff + reserved_evidence + reserved_memory + reserved_final + reserved_recovery
    available_input = max(0, context_limit - reserves) if context_limit else None
    estimated_input = _int_or_none(budget_input.estimated_input_tokens)
    estimated_total = (estimated_input or 0) + reserves if estimated_input is not None or reserves else None
    usage_ratio = round(estimated_total / context_limit, 4) if context_limit and estimated_total is not None else None

    warnings: list[str] = []
    required_actions: list[str] = []
    if not context_limit:
        status = "missing_context_limit"
        warnings.append("context_limit_missing")
        required_actions.append("review_context_budget")
    elif estimated_total is not None and estimated_total > context_limit:
        status = "over_limit"
        warnings.append("estimated_tokens_exceed_context_limit")
        required_actions.append("reduce_context_or_select_larger_model")
    elif usage_ratio is not None and usage_ratio >= 0.85:
        status = "near_limit"
        warnings.append("context_budget_near_limit")
        required_actions.append("review_context_budget")
    elif estimated_total is None:
        status = "unknown"
    else:
        status = "within_budget"

    return ModelContextBudget(
        context_limit=context_limit,
        context_limit_source=context_limit_source,
        output_limit=output_limit,
        output_limit_source=output_limit_source,
        reserved_output_tokens=reserved_output,
        reserved_tool_tokens=reserved_tool,
        reserved_mcp_tokens=reserved_mcp,
        reserved_skill_tokens=reserved_skill,
        reserved_handoff_tokens=reserved_handoff,
        reserved_evidence_tokens=reserved_evidence,
        reserved_memory_tokens=reserved_memory,
        reserved_final_answer_tokens=reserved_final,
        reserved_recovery_tokens=reserved_recovery,
        available_input_tokens=available_input,
        estimated_input_tokens=estimated_input,
        estimated_total_tokens=estimated_total,
        usage_ratio=usage_ratio,
        status=status,
        warnings=warnings,
        required_actions=required_actions,
        metadata=_safe({"task_type": budget_input.task_type, "mode": budget_input.mode, "role_profile": budget_input.role_profile, **budget_input.metadata}),
    )


def dump_model_context_budget(budget: ModelContextBudget | dict[str, Any]) -> dict[str, Any]:
    return _dump_dataclass_or_dict(budget)


def attach_context_budget_to_model_runtime(resolution: ModelRuntimeResolution | dict[str, Any], budget: ModelContextBudget | dict[str, Any]) -> dict[str, Any]:
    data = dump_model_runtime_resolution(resolution)
    data["context_budget"] = dump_model_context_budget(budget)
    return _safe(data)


def _coerce_long_task_health_input(value: LongTaskHealthInput | dict[str, Any]) -> LongTaskHealthInput:
    if isinstance(value, LongTaskHealthInput):
        return value
    data = dict(value or {}) if isinstance(value, dict) else {}
    return LongTaskHealthInput(
        resolution=data.get("resolution"),
        context_budget=data.get("context_budget"),
        provider_health=data.get("provider_health") if isinstance(data.get("provider_health"), dict) else None,
        elapsed_ms=_int_or_none(data.get("elapsed_ms")),
        timeout_ms=_int_or_none(data.get("timeout_ms")),
        stream_last_event_ms_ago=_int_or_none(data.get("stream_last_event_ms_ago")),
        output_truncated=data.get("output_truncated"),
        missing_capabilities=list(data.get("missing_capabilities") or []),
        retry_count=_int_or_none(data.get("retry_count")) or 0,
        task_type=data.get("task_type"),
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )


def evaluate_long_task_model_health(input: LongTaskHealthInput | dict[str, Any]) -> ModelLongTaskHealth:
    health_input = _coerce_long_task_health_input(input)
    resolution = _resolution_data(health_input.resolution)
    budget = dump_model_context_budget(health_input.context_budget) if isinstance(health_input.context_budget, (ModelContextBudget, dict)) else {}
    provider_health = health_input.provider_health if isinstance(health_input.provider_health, dict) else dict(resolution.get("provider_health") or {})
    provider_ok = provider_health.get("ok")
    provider_status = _text(provider_health.get("status")) or ("healthy" if provider_ok is True else "unmeasured")
    risks: list[str] = []
    warnings: list[str] = []
    required_actions: list[str] = []

    if provider_ok is False:
        provider_status = "provider_unavailable"
        risks.append("provider_unavailable")
        required_actions.append("pause_for_provider_recovery")
    if resolution.get("model_id") in (None, "", "auto"):
        risks.append("model_missing")
        required_actions.append("select_model")

    context_status = _text(budget.get("status")) or "unknown"
    if context_status == "over_limit":
        risks.append("context_over_limit")
        required_actions.append("reduce_context_or_select_larger_model")
    elif context_status == "missing_context_limit":
        warnings.append("context_limit_missing")

    stall_threshold = _int_or_none(health_input.metadata.get("stream_stall_threshold_ms")) or 30_000
    stream_status = "stream_stalled" if health_input.stream_last_event_ms_ago is not None and health_input.stream_last_event_ms_ago > stall_threshold else "healthy"
    if stream_status == "stream_stalled":
        risks.append("stream_stalled")
        warnings.append("stream_last_event_stale")
        required_actions.append("review_stream_state")

    timeout_status = "healthy"
    if health_input.elapsed_ms is not None and health_input.timeout_ms:
        if health_input.elapsed_ms >= health_input.timeout_ms:
            timeout_status = "timeout_risk"
            risks.append("timeout_risk")
            required_actions.append("review_timeout")
        elif health_input.elapsed_ms / health_input.timeout_ms >= 0.85:
            timeout_status = "timeout_risk"
            warnings.append("timeout_near_limit")

    output_status = "output_truncated" if health_input.output_truncated else "healthy"
    if output_status == "output_truncated":
        warnings.append("output_truncated")
        required_actions.append("review_output_truncation")

    missing_capabilities = [str(item) for item in health_input.missing_capabilities if str(item).strip()]
    capability_status = "missing_capability" if missing_capabilities else "healthy"
    if missing_capabilities:
        risks.append("missing_capability")
        required_actions.append("review_model_capabilities")

    should_pause = provider_ok is False or "context_over_limit" in risks or "model_missing" in risks or "stream_stalled" in risks
    should_escalate = provider_ok is False or bool(missing_capabilities) or bool(health_input.output_truncated) or "context_over_limit" in risks
    can_continue = not (provider_ok is False or "model_missing" in risks or "context_over_limit" in risks)
    if provider_ok is False:
        can_continue = False

    if provider_ok is False:
        status = "provider_unavailable"
    elif "model_missing" in risks:
        status = "model_missing"
    elif "context_over_limit" in risks:
        status = "context_over_limit"
    elif "stream_stalled" in risks:
        status = "stream_stalled"
    elif timeout_status == "timeout_risk" and "timeout_risk" in risks:
        status = "timeout_risk"
    elif output_status == "output_truncated":
        status = "output_truncated"
    elif missing_capabilities:
        status = "missing_capability"
    elif risks or warnings:
        status = "degraded"
    else:
        status = "healthy"

    return ModelLongTaskHealth(
        provider_id=_text(resolution.get("provider_id")) or "unknown",
        model_id=_text(resolution.get("model_id")) or "auto",
        role_profile=_text((resolution.get("role_profile") or {}).get("role_profile") if isinstance(resolution.get("role_profile"), dict) else None) or "unknown",
        status=status,
        provider_status=provider_status,
        context_status=context_status,
        stream_status=stream_status,
        timeout_status=timeout_status,
        output_status=output_status,
        capability_status=capability_status,
        risks=risks,
        warnings=warnings,
        required_actions=list(dict.fromkeys(required_actions)),
        can_continue=can_continue,
        should_pause=should_pause,
        should_escalate=should_escalate,
        metadata=_safe({"retry_count": health_input.retry_count, "task_type": health_input.task_type, "missing_capabilities": missing_capabilities, "provider_health": provider_health, **health_input.metadata}),
    )


def dump_long_task_model_health(health: ModelLongTaskHealth | dict[str, Any]) -> dict[str, Any]:
    return _dump_dataclass_or_dict(health)


def attach_long_task_health_to_model_runtime(resolution: ModelRuntimeResolution | dict[str, Any], health: ModelLongTaskHealth | dict[str, Any]) -> dict[str, Any]:
    data = dump_model_runtime_resolution(resolution)
    data["long_task_health"] = dump_long_task_model_health(health)
    return _safe(data)


def _coerce_runtime_escalation_input(value: RuntimeEscalationInput | dict[str, Any]) -> RuntimeEscalationInput:
    if isinstance(value, RuntimeEscalationInput):
        return value
    data = dict(value or {}) if isinstance(value, dict) else {}
    return RuntimeEscalationInput(
        resolution=data.get("resolution"),
        health=data.get("health"),
        context_budget=data.get("context_budget"),
        available_models=data.get("available_models") if isinstance(data.get("available_models"), list) else None,
        preferred_models=data.get("preferred_models") if isinstance(data.get("preferred_models"), dict) else None,
        role_profile=data.get("role_profile"),
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )


def _model_context_limit(model: dict[str, Any]) -> int | None:
    for key in ("context_limit", "context_window", "configured_context_window", "loaded_context_window", "declared_context_window"):
        parsed = _int_or_none(model.get(key))
        if parsed:
            return parsed
    return None


def _model_supports_missing(model: dict[str, Any], missing: list[str]) -> bool:
    for cap in missing:
        normalized = str(cap).strip().lower().replace("supports_", "")
        if not normalized:
            continue
        if model.get(f"supports_{normalized}") is True:
            continue
        caps = model.get("capabilities") if isinstance(model.get("capabilities"), dict) else {}
        item = caps.get(normalized)
        if isinstance(item, dict) and item.get("supported") is True:
            continue
        if item is True:
            continue
        return False
    return True


def _find_safe_alternative(current_model_id: str, context_budget: dict[str, Any], health: dict[str, Any], available_models: list[dict[str, Any]]) -> dict[str, Any] | None:
    current_limit = _int_or_none(context_budget.get("context_limit")) or 0
    missing = []
    if health.get("capability_status") == "missing_capability":
        metadata = health.get("metadata") if isinstance(health.get("metadata"), dict) else {}
        missing = [str(item) for item in metadata.get("missing_capabilities") or [] if str(item).strip()]
    for model in available_models:
        if not isinstance(model, dict):
            continue
        model_id = _text(model.get("model_id") or model.get("value") or model.get("model") or model.get("name"))
        if not model_id or model_id == current_model_id:
            continue
        candidate_limit = _model_context_limit(model) or 0
        better_context = candidate_limit > current_limit and context_budget.get("status") in {"over_limit", "near_limit", "missing_context_limit"}
        better_capability = bool(missing) and _model_supports_missing(model, missing)
        if better_context or better_capability or model.get("safe_fallback") is True:
            provider_id = _text(model.get("provider_id") or model.get("provider") or ("ollama" if is_local_model(model_id) else "unknown"))
            return {**model, "model_id": normalize_runtime_model_id(model_id, provider_id), "provider_id": normalize_runtime_provider_id(model_id, provider_id)}
    return None


def build_runtime_escalation_decision(input: RuntimeEscalationInput | dict[str, Any]) -> ModelRuntimeEscalationDecision:
    escalation_input = _coerce_runtime_escalation_input(input)
    resolution = _resolution_data(escalation_input.resolution)
    health = dump_long_task_model_health(escalation_input.health) if isinstance(escalation_input.health, (ModelLongTaskHealth, dict)) else {}
    budget = dump_model_context_budget(escalation_input.context_budget) if isinstance(escalation_input.context_budget, (ModelContextBudget, dict)) else {}
    current_provider = _text(resolution.get("provider_id")) or "unknown"
    current_model = _text(resolution.get("model_id")) or "auto"
    source_chain = ["runtime_escalation:side_effect_free"]
    warnings: list[str] = []
    required_actions: list[str] = []
    blocked_reasons: list[str] = []

    healthy = health.get("status") in {"", None, "healthy"} and budget.get("status") in {"", None, "within_budget", "unknown"} and current_model != "auto"
    if healthy:
        return ModelRuntimeEscalationDecision(
            decision="continue_current_model",
            reason="healthy",
            current_provider_id=current_provider,
            current_model_id=current_model,
            requires_user_approval=False,
            allowed_without_approval=True,
            source_chain=source_chain,
            metadata=_safe(escalation_input.metadata),
        )

    available = [item for item in (escalation_input.available_models or []) if isinstance(item, dict)]
    alternative = _find_safe_alternative(current_model, budget, health, available)
    if alternative:
        required_actions.append("request_user_approval_for_model_change")
        warnings.append("model_change_suggestion_not_applied")
        return ModelRuntimeEscalationDecision(
            decision="suggest_installed_model",
            reason=health.get("status") or budget.get("status") or "degraded",
            current_provider_id=current_provider,
            current_model_id=current_model,
            suggested_provider_id=alternative.get("provider_id"),
            suggested_model_id=alternative.get("model_id"),
            suggested_role_profile=escalation_input.role_profile,
            requires_user_approval=True,
            allowed_without_approval=False,
            warnings=warnings,
            required_actions=required_actions,
            source_chain=source_chain + ["available_models:explicit"],
            metadata=_safe({"suggestion_source": "available_models", **escalation_input.metadata}),
        )

    if health.get("should_pause") or health.get("should_escalate") or budget.get("status") in {"over_limit", "missing_context_limit"}:
        blocked_reasons = [health.get("status") or "degraded"]
        if budget.get("status") in {"over_limit", "missing_context_limit"}:
            blocked_reasons.append(budget.get("status"))
        required_actions.append("pause_for_user_approval")
        return ModelRuntimeEscalationDecision(
            decision="blocked_no_safe_fallback",
            reason=blocked_reasons[0],
            current_provider_id=current_provider,
            current_model_id=current_model,
            requires_user_approval=True,
            allowed_without_approval=False,
            blocked_reasons=list(dict.fromkeys([str(item) for item in blocked_reasons if item])),
            warnings=["no_safe_installed_fallback"],
            required_actions=required_actions,
            source_chain=source_chain + ["available_models:none_safe"],
            metadata=_safe(escalation_input.metadata),
        )

    return ModelRuntimeEscalationDecision(
        decision="pause_for_user_approval",
        reason=health.get("status") or budget.get("status") or "degraded",
        current_provider_id=current_provider,
        current_model_id=current_model,
        requires_user_approval=True,
        allowed_without_approval=False,
        warnings=["manual_review_required"],
        required_actions=["pause_for_user_approval"],
        source_chain=source_chain,
        metadata=_safe(escalation_input.metadata),
    )


def dump_runtime_escalation_decision(decision: ModelRuntimeEscalationDecision | dict[str, Any]) -> dict[str, Any]:
    data = _dump_dataclass_or_dict(decision)
    if data.get("decision") != "continue_current_model":
        data["allowed_without_approval"] = False
        data["requires_user_approval"] = True
    return _safe(data)


def attach_escalation_to_model_runtime(resolution: ModelRuntimeResolution | dict[str, Any], decision: ModelRuntimeEscalationDecision | dict[str, Any]) -> dict[str, Any]:
    data = dump_model_runtime_resolution(resolution)
    data["escalation_decision"] = dump_runtime_escalation_decision(decision)
    return _safe(data)

def dump_model_runtime_resolution(resolution: ModelRuntimeResolution | dict[str, Any]) -> dict[str, Any]:
    if isinstance(resolution, ModelRuntimeResolution):
        data = asdict(resolution)
    else:
        data = deepcopy(dict(resolution or {}))
    return _safe(data)


def _budget_summary(budget: Any) -> dict[str, Any] | None:
    data = dump_model_context_budget(budget) if isinstance(budget, (ModelContextBudget, dict)) else {}
    if not data:
        return None
    return _safe({
        "status": data.get("status"),
        "context_limit": data.get("context_limit"),
        "estimated_total_tokens": data.get("estimated_total_tokens"),
        "available_input_tokens": data.get("available_input_tokens"),
        "usage_ratio": data.get("usage_ratio"),
        "warnings": data.get("warnings") or [],
        "required_actions": data.get("required_actions") or [],
    })


def _health_summary(health: Any) -> dict[str, Any] | None:
    data = dump_long_task_model_health(health) if isinstance(health, (ModelLongTaskHealth, dict)) else {}
    if not data:
        return None
    return _safe({
        "status": data.get("status"),
        "provider_status": data.get("provider_status"),
        "context_status": data.get("context_status"),
        "stream_status": data.get("stream_status"),
        "timeout_status": data.get("timeout_status"),
        "output_status": data.get("output_status"),
        "capability_status": data.get("capability_status"),
        "can_continue": data.get("can_continue"),
        "should_pause": data.get("should_pause"),
        "should_escalate": data.get("should_escalate"),
        "risks": data.get("risks") or [],
        "warnings": data.get("warnings") or [],
        "required_actions": data.get("required_actions") or [],
    })


def _escalation_summary(decision: Any) -> dict[str, Any] | None:
    data = dump_runtime_escalation_decision(decision) if isinstance(decision, (ModelRuntimeEscalationDecision, dict)) else {}
    if not data:
        return None
    return _safe({
        "decision": data.get("decision"),
        "reason": data.get("reason"),
        "suggested_provider_id": data.get("suggested_provider_id"),
        "suggested_model_id": data.get("suggested_model_id"),
        "suggested_role_profile": data.get("suggested_role_profile"),
        "requires_user_approval": data.get("requires_user_approval"),
        "allowed_without_approval": data.get("allowed_without_approval"),
        "blocked_reasons": data.get("blocked_reasons") or [],
        "warnings": data.get("warnings") or [],
        "required_actions": data.get("required_actions") or [],
    })


def build_model_runtime_trace_source(resolution: ModelRuntimeResolution | dict[str, Any]) -> dict[str, Any]:
    data = dump_model_runtime_resolution(resolution)
    context_budget = _budget_summary(data.get("context_budget"))
    long_task_health = _health_summary(data.get("long_task_health"))
    escalation_decision = _escalation_summary(data.get("escalation_decision"))
    warnings = list(data.get("warnings") or [])
    required_actions = list(data.get("required_actions") or [])
    for summary in (context_budget, long_task_health, escalation_decision):
        if isinstance(summary, dict):
            warnings.extend(summary.get("warnings") or [])
            required_actions.extend(summary.get("required_actions") or [])
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
        "warnings": list(dict.fromkeys(warnings)),
        "required_actions": list(dict.fromkeys(required_actions)),
        "fallback_policy": data.get("fallback_policy"),
        "context_budget": context_budget,
        "long_task_health": long_task_health,
        "escalation_decision": escalation_decision,
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
