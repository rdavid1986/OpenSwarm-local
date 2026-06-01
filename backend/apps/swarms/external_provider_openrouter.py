"""Side-effect-free OpenRouter external provider contracts.

This module models optional OpenRouter provider configuration, catalog,
routing, privacy/ZDR, and structured-output compatibility without performing
HTTP requests, loading API keys, calling models, executing tools, or mutating
runtime state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

OPENROUTER_CONTRACT_VERSION = "openswarm.external_provider_openrouter.v1"
OPENROUTER_PROVIDER_ID = "openrouter"
SENSITIVE_MARKERS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}
SENSITIVE_PAYLOAD_MARKERS = SENSITIVE_MARKERS | {
    "chain_of_thought",
    "private_reasoning",
    "raw_prompt",
    "internal_prompt",
    "workspace_file",
    "full_code",
}
VALID_SCOPES = {"global", "project", "dashboard", "swarm", "agent"}
STRUCTURED_OUTPUT_DOMAINS = {
    "dag_planner",
    "skill_spec_candidate",
    "app_builder_plan",
    "debug_diagnosis",
    "model_routing_decision",
    "web_research_summary",
    "evaluation_report",
    "generic",
}


def _text(value: Any, fallback: str = "", limit: int = 600) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text[:limit].rstrip() + ("..." if len(text) > limit else "")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _dedupe(values: list[Any], *, limit: int = 80) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value, limit=240)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _is_sensitive_key(key: Any) -> bool:
    lowered = _text(key, limit=120).lower().replace("-", "_")
    return any(marker in lowered for marker in SENSITIVE_MARKERS)


def _contains_sensitive_text(value: Any) -> bool:
    lowered = _text(value, limit=2000).lower().replace("-", "_")
    return any(marker in lowered for marker in SENSITIVE_PAYLOAD_MARKERS)


def _safe_value(value: Any, *, limit: int = 320) -> Any:
    if isinstance(value, dict):
        return _safe_metadata(value)
    if isinstance(value, list):
        return [_safe_value(item, limit=limit) for item in value[:50]]
    if isinstance(value, bool) or isinstance(value, int | float) or value is None:
        return value
    text = _text(value, limit=limit)
    return "[redacted]" if _contains_sensitive_text(text) else text


def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, raw in value.items():
        key_text = _text(key, limit=120)
        if _is_sensitive_key(key_text):
            safe[key_text] = "[redacted]"
        elif isinstance(raw, dict):
            safe[key_text] = _safe_metadata(raw)
        elif isinstance(raw, list):
            safe[key_text] = [_safe_value(item, limit=160) for item in raw[:20]]
        else:
            safe[key_text] = _safe_value(raw, limit=240)
    return safe


def dump_openrouter_contract(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return _safe_metadata(value)
    return {}


@dataclass(frozen=True)
class OpenRouterCredentialReference:
    credential_kind: str = "openrouter_credential_reference"
    provider_id: str = OPENROUTER_PROVIDER_ID
    api_key_reference: str = ""
    raw_api_key_provided: bool = False
    can_call_provider: bool = False
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterProviderPolicy:
    policy_kind: str = "openrouter_provider_policy"
    provider_id: str = OPENROUTER_PROVIDER_ID
    scopes: list[str] = field(default_factory=list)
    zdr_required: bool = True
    allowed_model_ids: list[str] = field(default_factory=list)
    blocked_model_ids: list[str] = field(default_factory=list)
    allowed_provider_ids: list[str] = field(default_factory=list)
    disabled_server_tools: list[str] = field(default_factory=lambda: ["web_search", "web_fetch", "fusion", "apply_patch"])
    budget_cap_usd: float | None = None
    usage_cap_tokens: int | None = None
    allow_web_search: bool = False
    allow_web_fetch: bool = False
    allow_fusion: bool = False
    allow_apply_patch: bool = False
    can_call_provider: bool = False
    can_use_server_tools: bool = False
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterProviderConfig:
    source_kind: str = "openrouter_provider_config"
    config_kind: str = "openrouter_provider_config"
    contract_version: str = OPENROUTER_CONTRACT_VERSION
    provider_id: str = OPENROUTER_PROVIDER_ID
    enabled: bool = False
    api_key_reference: str = ""
    credential: dict[str, Any] = field(default_factory=dict)
    policy: dict[str, Any] = field(default_factory=dict)
    can_call_provider: bool = False
    can_execute: bool = False
    can_use_server_tools: bool = False
    external_call_performed: bool = False
    server_tools_disabled: bool = True
    apply_patch_blocked: bool = True
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterModelCapabilitySummary:
    capability_kind: str = "openrouter_model_capability_summary"
    supports_tool_calling: bool = False
    supports_structured_outputs: bool = False
    supports_reasoning: bool = False
    supports_vision: bool = False
    supports_zdr: bool = False
    can_call_provider: bool = False


@dataclass(frozen=True)
class OpenRouterModelCatalogEntry:
    entry_kind: str = "openrouter_model_catalog_entry"
    source_kind: str = "openrouter_model_catalog"
    model_id: str = ""
    display_name: str = ""
    provider_id: str = OPENROUTER_PROVIDER_ID
    context_length: int | None = None
    input_modalities: list[str] = field(default_factory=list)
    output_modalities: list[str] = field(default_factory=list)
    supported_parameters: list[str] = field(default_factory=list)
    supports_tool_calling: bool = False
    supports_structured_outputs: bool = False
    supports_reasoning: bool = False
    supports_vision: bool = False
    supports_zdr: bool = False
    pricing_prompt: float | None = None
    pricing_completion: float | None = None
    pricing_request: float | None = None
    last_seen_at: str = ""
    stale_after: str = ""
    source: str = "openrouter_catalog"
    can_call_provider: bool = False
    external_call_performed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterModelCatalogSnapshot:
    snapshot_kind: str = "openrouter_model_catalog_snapshot"
    source_kind: str = "openrouter_model_catalog"
    provider_id: str = OPENROUTER_PROVIDER_ID
    entries: list[dict[str, Any]] = field(default_factory=list)
    entry_count: int = 0
    stale_after: str = ""
    source: str = "openrouter_catalog"
    can_call_provider: bool = False
    external_call_performed: bool = False
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterRoutingPolicy:
    routing_policy_kind: str = "openrouter_routing_policy"
    local_first: bool = True
    require_user_approval: bool = True
    require_privacy_gate: bool = True
    require_budget_gate: bool = True
    require_zdr: bool = True
    allow_external_candidate: bool = False
    can_call_provider: bool = False


@dataclass(frozen=True)
class OpenRouterRoutingInput:
    routing_input_kind: str = "openrouter_routing_input"
    task_kind: str = "unknown"
    requires_cloud_capability: bool = False
    local_model_available: bool = True
    local_model_sufficient: bool = True
    requested_model_id: str = ""
    estimated_tokens: int | None = None
    estimated_cost_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterExternalRoutingDecision:
    source_kind: str = "openrouter_routing_decision"
    decision_kind: str = "openrouter_routing_decision"
    provider_id: str = OPENROUTER_PROVIDER_ID
    routing_status: str = "blocked"
    local_first: bool = True
    external_allowed: bool = False
    selected_provider: str = "local"
    selected_model_id: str = ""
    reason: str = ""
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    privacy_required: bool = True
    budget_required: bool = True
    user_approval_required: bool = True
    can_call_provider: bool = False
    external_call_performed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterZdrDecision:
    zdr_kind: str = "openrouter_zdr_decision"
    zdr_required: bool = True
    zdr_allowed: bool = False
    decision: str = "blocked"
    required_actions: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OpenRouterRedactionReport:
    redaction_kind: str = "openrouter_redaction_report"
    redaction_applied: bool = False
    secrets_redacted: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    safe_payload_preview: dict[str, Any] = field(default_factory=dict)
    required_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OpenRouterPrivacyGateResult:
    source_kind: str = "openrouter_privacy_gate"
    gate_kind: str = "openrouter_privacy_gate"
    provider_id: str = OPENROUTER_PROVIDER_ID
    gate_status: str = "blocked"
    zdr_required: bool = True
    zdr_allowed: bool = False
    redaction_applied: bool = False
    secrets_redacted: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    safe_payload_preview: dict[str, Any] = field(default_factory=dict)
    can_call_provider: bool = False
    external_call_performed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterStructuredOutputContract:
    structured_output_kind: str = "openrouter_structured_output_contract"
    source_kind: str = "openrouter_structured_output"
    response_format: str = "json_schema"
    schema_name: str = ""
    schema_version: str = ""
    strict: bool = True
    domain: str = "generic"
    schema: dict[str, Any] = field(default_factory=dict)
    can_call_provider: bool = False
    validation_required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenRouterResponseFormatDecision:
    response_format_kind: str = "openrouter_response_format_decision"
    source_kind: str = "openrouter_structured_output"
    response_format: str = "json_schema"
    fallback_mode: str = "none"
    supported_by_model: bool = False
    validation_required: bool = True
    can_call_provider: bool = False
    required_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OpenRouterSchemaCompatibilityReport:
    source_kind: str = "openrouter_structured_output"
    report_kind: str = "openrouter_schema_compatibility_report"
    schema_name: str = ""
    schema_version: str = ""
    strict: bool = True
    supported_by_model: bool = False
    fallback_mode: str = "json_object"
    validation_required: bool = True
    status: str = "blocked"
    compatible_domains: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_call_provider: bool = False
    external_call_performed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def build_openrouter_provider_config(
    *,
    enabled: bool = False,
    api_key_reference: str = "",
    raw_api_key: str = "",
    scopes: list[str] | None = None,
    zdr_required: bool = True,
    allowed_model_ids: list[str] | None = None,
    blocked_model_ids: list[str] | None = None,
    allowed_provider_ids: list[str] | None = None,
    budget_cap_usd: float | None = None,
    usage_cap_tokens: int | None = None,
    allow_web_search: bool = False,
    allow_web_fetch: bool = False,
    allow_fusion: bool = False,
    allow_apply_patch: bool = False,
    metadata: dict[str, Any] | None = None,
) -> OpenRouterProviderConfig:
    raw_key_provided = bool(_text(raw_api_key)) or _text(api_key_reference).startswith(("sk-", "sk_or_", "sk-or-"))
    safe_scopes = [scope for scope in (_text(item).lower() for item in _as_list(scopes or ["project"])) if scope in VALID_SCOPES]
    required = ["do_not_call_openrouter", "require_user_approval", "require_privacy_gate", "require_budget_gate"]
    notes = ["OpenRouter is optional and policy-gated; local/Ollama remains first priority."]
    if not enabled:
        required.append("enable_provider_explicitly")
    if raw_key_provided:
        required.append("replace_raw_api_key_with_reference")
        notes.append("Raw API keys are never stored in provider config contracts.")
    if not _text(api_key_reference) or raw_key_provided:
        required.append("provide_secret_store_reference")
    if allow_web_search or allow_web_fetch or allow_fusion:
        required.append("disable_openrouter_server_tools_by_default")
        notes.append("Server tools remain disabled until a later policy layer.")
    if allow_apply_patch:
        required.append("block_external_apply_patch")
    if not zdr_required:
        required.append("require_zdr_for_sensitive_tasks")

    credential = OpenRouterCredentialReference(
        api_key_reference="" if raw_key_provided else _text(api_key_reference, limit=300),
        raw_api_key_provided=raw_key_provided,
        required_actions=_dedupe(["provide_secret_store_reference"] if not api_key_reference or raw_key_provided else []),
        policy_notes=_dedupe(notes),
        metadata=_safe_metadata(metadata),
    )
    policy = OpenRouterProviderPolicy(
        scopes=_dedupe(safe_scopes) or ["project"],
        zdr_required=bool(zdr_required),
        allowed_model_ids=_dedupe(_as_list(allowed_model_ids)),
        blocked_model_ids=_dedupe(_as_list(blocked_model_ids)),
        allowed_provider_ids=_dedupe(_as_list(allowed_provider_ids)),
        budget_cap_usd=budget_cap_usd,
        usage_cap_tokens=usage_cap_tokens,
        allow_web_search=False,
        allow_web_fetch=False,
        allow_fusion=False,
        allow_apply_patch=False,
        required_actions=_dedupe(required),
        policy_notes=_dedupe(notes),
        metadata=_safe_metadata(metadata),
    )
    return OpenRouterProviderConfig(
        enabled=bool(enabled),
        api_key_reference="" if raw_key_provided else _text(api_key_reference, limit=300),
        credential=dump_openrouter_contract(credential),
        policy=dump_openrouter_contract(policy),
        required_actions=_dedupe(required),
        policy_notes=_dedupe(notes),
        metadata=_safe_metadata(metadata),
    )


def normalize_openrouter_model_catalog_entry(entry: dict[str, Any] | OpenRouterModelCatalogEntry) -> OpenRouterModelCatalogEntry:
    data = dump_openrouter_contract(entry)
    modalities_in = _dedupe(_as_list(data.get("input_modalities") or data.get("input_modalities_supported") or ["text"]))
    modalities_out = _dedupe(_as_list(data.get("output_modalities") or ["text"]))
    return OpenRouterModelCatalogEntry(
        model_id=_text(data.get("model_id") or data.get("id"), limit=240),
        display_name=_text(data.get("display_name") or data.get("name"), limit=240),
        provider_id=_text(data.get("provider_id"), OPENROUTER_PROVIDER_ID, limit=120),
        context_length=int(data["context_length"]) if str(data.get("context_length") or "").isdigit() else None,
        input_modalities=modalities_in,
        output_modalities=modalities_out,
        supported_parameters=_dedupe(_as_list(data.get("supported_parameters"))),
        supports_tool_calling=bool(data.get("supports_tool_calling")),
        supports_structured_outputs=bool(data.get("supports_structured_outputs")),
        supports_reasoning=bool(data.get("supports_reasoning")),
        supports_vision=bool(data.get("supports_vision") or "image" in modalities_in),
        supports_zdr=bool(data.get("supports_zdr")),
        pricing_prompt=data.get("pricing_prompt"),
        pricing_completion=data.get("pricing_completion"),
        pricing_request=data.get("pricing_request"),
        last_seen_at=_text(data.get("last_seen_at"), limit=80),
        stale_after=_text(data.get("stale_after"), limit=80),
        metadata=_safe_metadata(data.get("metadata") if isinstance(data.get("metadata"), dict) else {}),
    )


def build_openrouter_model_catalog_snapshot(entries: list[dict[str, Any] | OpenRouterModelCatalogEntry] | None = None, *, stale_after: str = "", metadata: dict[str, Any] | None = None) -> OpenRouterModelCatalogSnapshot:
    normalized = [dump_openrouter_contract(normalize_openrouter_model_catalog_entry(entry)) for entry in (entries or [])]
    return OpenRouterModelCatalogSnapshot(
        entries=normalized,
        entry_count=len(normalized),
        stale_after=_text(stale_after, limit=80),
        required_actions=_dedupe(["sync_catalog_out_of_band_before_routing"] if not normalized else ["review_catalog_staleness_before_use"]),
        policy_notes=["Catalog snapshot is caller-provided; this contract never calls OpenRouter."],
        metadata=_safe_metadata(metadata),
    )


def select_openrouter_catalog_candidates(snapshot: OpenRouterModelCatalogSnapshot | dict[str, Any], *, requires_structured_outputs: bool = False, requires_vision: bool = False, requires_zdr: bool = True, max_candidates: int = 5) -> list[dict[str, Any]]:
    data = dump_openrouter_contract(snapshot)
    candidates: list[dict[str, Any]] = []
    for raw in _as_list(data.get("entries")):
        if not isinstance(raw, dict):
            continue
        if requires_structured_outputs and not raw.get("supports_structured_outputs"):
            continue
        if requires_vision and not raw.get("supports_vision"):
            continue
        if requires_zdr and not raw.get("supports_zdr"):
            continue
        safe = dict(raw)
        safe["can_call_provider"] = False
        candidates.append(_safe_metadata(safe))
        if len(candidates) >= max_candidates:
            break
    return candidates


def decide_openrouter_external_routing(
    routing_input: OpenRouterRoutingInput | dict[str, Any] | None = None,
    *,
    provider_config: OpenRouterProviderConfig | dict[str, Any] | None = None,
    privacy_gate: OpenRouterPrivacyGateResult | dict[str, Any] | None = None,
    catalog_candidates: list[dict[str, Any]] | None = None,
    user_approved: bool = False,
    budget_approved: bool = False,
    metadata: dict[str, Any] | None = None,
) -> OpenRouterExternalRoutingDecision:
    request = dump_openrouter_contract(routing_input or OpenRouterRoutingInput())
    config = dump_openrouter_contract(provider_config or build_openrouter_provider_config())
    privacy = dump_openrouter_contract(privacy_gate or {})
    candidates = catalog_candidates or []
    blockers: list[str] = []
    required = ["prefer_local_model", "do_not_call_openrouter"]

    if request.get("local_model_available", True) and request.get("local_model_sufficient", True):
        blockers.append("local_model_sufficient")
    if not config.get("enabled"):
        blockers.append("provider_disabled")
        required.append("enable_provider_explicitly")
    if not user_approved:
        blockers.append("user_approval_missing")
        required.append("obtain_user_approval")
    if not budget_approved:
        blockers.append("budget_approval_missing")
        required.append("approve_external_budget")
    if privacy.get("gate_status") != "passed":
        blockers.append("privacy_gate_not_passed")
        required.append("pass_privacy_zdr_redaction_gate")
    if not request.get("requires_cloud_capability"):
        blockers.append("cloud_capability_not_required")
    if not candidates:
        blockers.append("no_catalog_candidate")
        required.append("select_catalog_candidate")

    external_candidate_allowed = not blockers or blockers == ["user_approval_missing"]
    status = "blocked" if any(item in blockers for item in {"provider_disabled", "privacy_gate_not_passed", "budget_approval_missing", "local_model_sufficient"}) else "needs_review" if blockers else "candidate"
    selected = _text(candidates[0].get("model_id") if candidates else request.get("requested_model_id"), limit=240)
    return OpenRouterExternalRoutingDecision(
        routing_status=status,
        local_first=True,
        external_allowed=False,
        selected_provider=OPENROUTER_PROVIDER_ID if external_candidate_allowed and selected else "local",
        selected_model_id=selected if external_candidate_allowed else "",
        reason="OpenRouter can only be recommended as a gated external candidate; no provider call is allowed in this phase.",
        blockers=_dedupe(blockers),
        required_actions=_dedupe(required),
        privacy_required=True,
        budget_required=True,
        user_approval_required=not user_approved,
        metadata=_safe_metadata(metadata),
    )


def evaluate_openrouter_privacy_gate(payload: dict[str, Any] | None = None, *, zdr_required: bool = True, zdr_allowed: bool = False, allow_workspace_files: bool = False, allow_full_code: bool = False, metadata: dict[str, Any] | None = None) -> OpenRouterPrivacyGateResult:
    raw = payload if isinstance(payload, dict) else {}
    blocked: list[str] = []
    required = ["do_not_send_external_payload", "review_external_provider_privacy"]
    safe_preview: dict[str, Any] = {}
    redacted = False
    for key, value in raw.items():
        lowered = _text(key, limit=120).lower().replace("-", "_")
        sensitive = _is_sensitive_key(key) or _contains_sensitive_text(value) or lowered in {"prompt", "messages", "raw_prompt", "chain_of_thought", "private_reasoning"}
        if sensitive:
            safe_preview[_text(key, limit=120)] = "[redacted]"
            redacted = True
            blocked.append(f"sensitive_payload:{lowered}")
        elif ("path" in lowered or "file" in lowered) and not allow_workspace_files:
            safe_preview[_text(key, limit=120)] = "[redacted]"
            redacted = True
            blocked.append(f"workspace_payload_requires_approval:{lowered}")
        elif "code" in lowered and not allow_full_code:
            safe_preview[_text(key, limit=120)] = "[redacted]"
            redacted = True
            blocked.append(f"code_payload_requires_approval:{lowered}")
        else:
            safe_preview[_text(key, limit=120)] = _safe_value(value, limit=240)
    if zdr_required and not zdr_allowed:
        blocked.append("zdr_required_not_allowed")
        required.append("select_zdr_capable_route")
    status = "blocked" if blocked else "passed"
    return OpenRouterPrivacyGateResult(
        gate_status=status,
        zdr_required=bool(zdr_required),
        zdr_allowed=bool(zdr_allowed),
        redaction_applied=redacted,
        secrets_redacted=redacted,
        blocked_reasons=_dedupe(blocked),
        required_actions=_dedupe(required + (["remove_or_redact_sensitive_payload"] if redacted else [])),
        safe_payload_preview=safe_preview,
        metadata=_safe_metadata(metadata),
    )


def build_openrouter_structured_output_contract(*, response_format: str = "json_schema", schema_name: str = "", schema_version: str = "", strict: bool = True, domain: str = "generic", schema: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> OpenRouterStructuredOutputContract:
    fmt = _text(response_format, "json_schema").lower()
    if fmt not in {"json_schema", "json_object"}:
        fmt = "json_schema"
    normalized_domain = _text(domain, "generic").lower()
    if normalized_domain not in STRUCTURED_OUTPUT_DOMAINS:
        normalized_domain = "generic"
    return OpenRouterStructuredOutputContract(
        response_format=fmt,
        schema_name=_text(schema_name, limit=120),
        schema_version=_text(schema_version, limit=80),
        strict=bool(strict),
        domain=normalized_domain,
        schema=_safe_metadata(schema or {}),
        metadata=_safe_metadata(metadata),
    )


def decide_openrouter_response_format(contract: OpenRouterStructuredOutputContract | dict[str, Any], model_entry: OpenRouterModelCatalogEntry | dict[str, Any] | None = None) -> OpenRouterResponseFormatDecision:
    data = dump_openrouter_contract(contract)
    model = dump_openrouter_contract(model_entry or {})
    requested = _text(data.get("response_format"), "json_schema").lower()
    supports_structured = bool(model.get("supports_structured_outputs"))
    fallback = "none" if supports_structured else "json_object" if requested == "json_schema" else "text_with_validation"
    required = ["validate_structured_output_locally", "do_not_call_openrouter"]
    if not supports_structured:
        required.append("use_structured_output_fallback")
    return OpenRouterResponseFormatDecision(
        response_format=requested if requested in {"json_schema", "json_object"} else "json_schema",
        fallback_mode=fallback,
        supported_by_model=supports_structured,
        validation_required=True,
        required_actions=_dedupe(required),
    )


def build_openrouter_schema_compatibility_report(contract: OpenRouterStructuredOutputContract | dict[str, Any], model_entry: OpenRouterModelCatalogEntry | dict[str, Any] | None = None) -> OpenRouterSchemaCompatibilityReport:
    data = dump_openrouter_contract(contract)
    decision = decide_openrouter_response_format(data, model_entry)
    supported = decision.supported_by_model
    return OpenRouterSchemaCompatibilityReport(
        schema_name=_text(data.get("schema_name"), limit=120),
        schema_version=_text(data.get("schema_version"), limit=80),
        strict=bool(data.get("strict", True)),
        supported_by_model=supported,
        fallback_mode=decision.fallback_mode,
        validation_required=True,
        status="completed" if supported else "warning",
        compatible_domains=sorted(STRUCTURED_OUTPUT_DOMAINS),
        required_actions=decision.required_actions,
        metadata=_safe_metadata(data.get("metadata") if isinstance(data.get("metadata"), dict) else {}),
    )
