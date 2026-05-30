"""Read-only contracts for external skill import preview.

Importing external skill material is not trust, installation, execution, or
candidate creation. This module only builds and summarizes inert metadata.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

CONTRACT_KIND = "skill_import_contract"
CONTRACT_VERSION = "openswarm.skill_import.v1"

SOURCE_FORMATS = {
    "openswarm_legacy_skill",
    "openswarm_skillspec",
    "anthropic_skill",
    "claude_skill",
    "cursor_rule",
    "windsurf_rule",
    "copilot_instruction",
    "codex_instruction",
    "gemini_cli_config",
    "qwen_code_config",
    "kiro_spec",
    "mcp_tool_instruction",
    "markdown_prompt_pack",
    "skill_pack",
    "repo",
    "zip",
    "folder",
    "unknown",
}


def _safe_source_format(value: str | None) -> str:
    normalized = str(value or "unknown").strip() or "unknown"
    return normalized if normalized in SOURCE_FORMATS else "unknown"


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def build_empty_skill_import_contract(
    *,
    source_format: str = "unknown",
    source_platform: str = "unknown",
    source_version: str = "unknown",
    source_url: str = "",
    source_author: str = "unknown",
    source_license: str = "unknown",
    source_hash: str = "",
    source_trust_level: str = "untrusted",
    import_adapter: str = "unknown_fallback_adapter",
    adapter_version: str = "openswarm.import_adapter.v1",
    imported_at: str | None = None,
    imported_by: str = "unknown",
    normalized_to: str = "openswarm.skill.v1.preview",
    compatibility_score: float = 0.0,
    metadata_confidence: str = "unknown",
    conversion_warnings: list[str] | None = None,
    unsupported_features: list[str] | None = None,
    required_tools: list[str] | None = None,
    required_mcp_servers: list[str] | None = None,
    required_model_capabilities: list[str] | None = None,
    validation_results: list[dict[str, Any]] | None = None,
    policy_decision: str = "preview_only",
    evidence_refs: list[str] | None = None,
    original_files: list[dict[str, Any]] | None = None,
    normalized_files: list[dict[str, Any]] | None = None,
    risks: list[str] | None = None,
) -> dict[str, Any]:
    """Build a safe, read-only external import contract."""

    return {
        "contract_kind": CONTRACT_KIND,
        "contract_version": CONTRACT_VERSION,
        "source_format": _safe_source_format(source_format),
        "source_platform": source_platform or "unknown",
        "source_version": source_version or "unknown",
        "source_url": source_url or "",
        "source_author": source_author or "unknown",
        "source_license": source_license or "unknown",
        "source_hash": source_hash or "",
        "source_trust_level": source_trust_level or "untrusted",
        "import_adapter": import_adapter or "unknown_fallback_adapter",
        "adapter_version": adapter_version or "openswarm.import_adapter.v1",
        "imported_at": imported_at or datetime.now(timezone.utc).isoformat(),
        "imported_by": imported_by or "unknown",
        "normalized_to": normalized_to or "openswarm.skill.v1.preview",
        "compatibility_score": max(0.0, min(1.0, float(compatibility_score or 0.0))),
        "metadata_confidence": metadata_confidence or "unknown",
        "conversion_warnings": _list(conversion_warnings),
        "unsupported_features": _list(unsupported_features),
        "required_tools": _list(required_tools),
        "required_mcp_servers": _list(required_mcp_servers),
        "required_model_capabilities": _list(required_model_capabilities),
        "validation_results": _list(validation_results),
        "policy_decision": policy_decision or "preview_only",
        "evidence_refs": _list(evidence_refs),
        "original_files": _list(original_files),
        "normalized_files": _list(normalized_files),
        "risks": _list(risks),
        "safe_to_install": False,
        "can_create_candidate": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }


def summarize_skill_import_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Return a compact summary without mutating the contract."""

    snapshot = deepcopy(contract)
    source_format = snapshot.get("source_format") or "unknown"
    warnings = _list(snapshot.get("conversion_warnings"))
    unsupported = _list(snapshot.get("unsupported_features"))
    risks = _list(snapshot.get("risks"))
    return {
        "contract_kind": "skill_import_contract_summary",
        "source_format": source_format,
        "import_adapter": snapshot.get("import_adapter") or "unknown_fallback_adapter",
        "metadata_confidence": snapshot.get("metadata_confidence") or "unknown",
        "compatibility_score": snapshot.get("compatibility_score", 0.0),
        "warning_count": len(warnings),
        "unsupported_feature_count": len(unsupported),
        "risk_count": len(risks),
        "policy_decision": snapshot.get("policy_decision") or "preview_only",
        "safe_to_install": False,
        "can_create_candidate": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }


def hash_source_text(text: str) -> str:
    """Hash already-provided source text; does not read files."""

    return sha256(str(text or "").encode("utf-8")).hexdigest()
