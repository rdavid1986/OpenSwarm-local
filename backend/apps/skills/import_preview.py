"""Read-only import preview report for external skill material.

Builds preview/diff/risk information only. It does not create candidates,
install skills, execute source, browse, or activate tools/MCP.
"""

from __future__ import annotations

from copy import deepcopy
from difflib import unified_diff
from typing import Any

from backend.apps.skills.import_contract import hash_source_text
from backend.apps.skills.import_normalization import normalize_external_skill_to_skillspec_preview


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def _preview_id(normalized: dict[str, Any]) -> str:
    spec = normalized.get("skill_spec_preview") if isinstance(normalized.get("skill_spec_preview"), dict) else {}
    provenance = spec.get("provenance") if isinstance(spec.get("provenance"), dict) else {}
    source_hash = str(provenance.get("source_hash") or "").strip()
    if source_hash and source_hash != "unknown":
        return f"skill-import-preview-{source_hash[:16]}"
    content = str(spec.get("content") or "")
    return f"skill-import-preview-{hash_source_text(content)[:16]}"


def _content_diff(existing_content: str, preview_content: str) -> str:
    lines = unified_diff(
        existing_content.splitlines(),
        preview_content.splitlines(),
        fromfile="existing_skill_spec.content",
        tofile="import_preview.skill_spec.content",
        lineterm="",
    )
    diff = "\n".join(lines)
    return diff or "No content changes detected."


def _metadata_warnings(import_contract: dict[str, Any], skill_spec_preview: dict[str, Any]) -> list[str]:
    provenance = skill_spec_preview.get("provenance") if isinstance(skill_spec_preview.get("provenance"), dict) else {}
    checks = {
        "source_license": import_contract.get("source_license") or provenance.get("source_license"),
        "source_author": import_contract.get("source_author") or provenance.get("source_author"),
        "source_url": import_contract.get("source_url") or provenance.get("source_url"),
        "source_hash": import_contract.get("source_hash") or provenance.get("source_hash"),
    }
    warnings: list[str] = []
    for key, value in checks.items():
        normalized = str(value or "").strip().lower()
        if normalized in {"", "unknown"}:
            warnings.append(f"{key}_unknown")
    return warnings


def _risk_report(normalized: dict[str, Any]) -> dict[str, Any]:
    contract = normalized.get("import_contract") if isinstance(normalized.get("import_contract"), dict) else {}
    spec = normalized.get("skill_spec_preview") if isinstance(normalized.get("skill_spec_preview"), dict) else {}
    risks = [str(item) for item in _as_list(normalized.get("risks"))]
    warnings = [str(item) for item in _as_list(normalized.get("conversion_warnings"))]
    metadata_warnings = _metadata_warnings(contract, spec)
    required_tools = [str(item) for item in _as_list(contract.get("required_tools") or spec.get("required_tools"))]
    required_mcp_servers = [str(item) for item in _as_list(contract.get("required_mcp_servers") or spec.get("required_mcp_servers"))]

    return {
        "risk_kind": "skill_import_risk_report",
        "risks": risks,
        "warnings": warnings + metadata_warnings,
        "possible_secret_material": "possible_secret_material" in risks,
        "dangerous_execution_instruction": "dangerous_execution_instruction" in risks,
        "required_tools": required_tools,
        "required_mcp_servers": required_mcp_servers,
        "declarative_requirements_only": True,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }


def build_skill_import_preview_report(input: dict[str, Any]) -> dict[str, Any]:
    """Build a side-effect-free import preview report from prepared input."""

    data = deepcopy(input or {})
    normalized = normalize_external_skill_to_skillspec_preview(data)
    contract = normalized.get("import_contract") if isinstance(normalized.get("import_contract"), dict) else {}
    spec = normalized.get("skill_spec_preview") if isinstance(normalized.get("skill_spec_preview"), dict) else {}
    existing = data.get("existing_skill_spec") if isinstance(data.get("existing_skill_spec"), dict) else {}
    existing_content = str(existing.get("content") or "")
    preview_content = str(spec.get("content") or "")
    risk_report = _risk_report(normalized)

    return {
        "report_kind": "skill_import_preview_report",
        "preview_id": _preview_id(normalized),
        "detection": deepcopy(data.get("detection")) if isinstance(data.get("detection"), dict) else None,
        "import_contract": contract,
        "skill_spec_preview": spec,
        "preview_diff": _content_diff(existing_content, preview_content),
        "risk_report": risk_report,
        "unsupported_features": _as_list(normalized.get("unsupported_features")),
        "conversion_warnings": _as_list(normalized.get("conversion_warnings")),
        "required_tools": _as_list(contract.get("required_tools") or spec.get("required_tools")),
        "required_mcp_servers": _as_list(contract.get("required_mcp_servers") or spec.get("required_mcp_servers")),
        "source_format": _text(contract.get("source_format") or spec.get("source_format")),
        "import_adapter": _text(contract.get("import_adapter")),
        "can_create_candidate": False,
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }
