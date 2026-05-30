"""Preview-only normalization of prepared external skill material to SkillSpec."""

from __future__ import annotations

import re
from typing import Any

from backend.apps.skills.import_adapters import select_skill_import_adapter
from backend.apps.skills.import_contract import build_empty_skill_import_contract, hash_source_text
from backend.apps.skills.models import SkillSpec

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
)
_DANGEROUS_TERMS = ("rm -rf", "curl | sh", "powershell -enc", "execute this script", "run this command")


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _frontmatter_value(frontmatter: Any, key: str, default: str = "") -> str:
    return str(frontmatter.get(key) or default) if isinstance(frontmatter, dict) else default


def _detect_risks(content: str) -> tuple[list[str], list[str]]:
    risks: list[str] = []
    warnings: list[str] = []
    if any(pattern.search(content or "") for pattern in _SECRET_PATTERNS):
        risks.append("possible_secret_material")
        warnings.append("Potential secret-like material detected in prepared content; review before candidate creation.")
    lowered = (content or "").lower()
    if any(term in lowered for term in _DANGEROUS_TERMS):
        risks.append("dangerous_execution_instruction")
        warnings.append("Potentially dangerous execution instruction detected; kept as inert preview content only.")
    return risks, warnings


def normalize_external_skill_to_skillspec_preview(input: dict[str, Any]) -> dict[str, Any]:
    """Normalize caller-prepared content into a SkillSpec preview only."""

    data = input or {}
    source_format = str(data.get("source_format") or "unknown")
    source_platform = str(data.get("source_platform") or "unknown")
    content = str(data.get("content") or "")
    frontmatter = data.get("frontmatter") if isinstance(data.get("frontmatter"), dict) else {}
    provenance_input = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}

    name = str(data.get("name") or _frontmatter_value(frontmatter, "name") or "Imported Skill Preview")
    description = str(data.get("description") or _frontmatter_value(frontmatter, "description") or "")
    required_tools = _as_list(data.get("required_tools") or frontmatter.get("required_tools"))
    required_mcp_servers = _as_list(data.get("required_mcp_servers") or frontmatter.get("required_mcp_servers"))
    adapter = str(data.get("import_adapter") or select_skill_import_adapter(source_format)["adapter_id"])

    risks, conversion_warnings = _detect_risks(content)
    unsupported_features = _as_list(data.get("unsupported_features"))
    if source_format == "unknown":
        conversion_warnings.append("Unknown source format; preview uses conservative metadata.")

    provenance = {
        "source_format": source_format,
        "source_platform": source_platform or "unknown",
        "source_url": str(data.get("source_url") or provenance_input.get("source_url") or "unknown"),
        "source_author": str(data.get("source_author") or provenance_input.get("source_author") or "unknown"),
        "source_license": str(data.get("source_license") or provenance_input.get("source_license") or "unknown"),
        "source_hash": str(data.get("source_hash") or hash_source_text(content) if content else data.get("source_hash") or "unknown"),
        "import_adapter": adapter,
        "preview_only": True,
    }
    provenance.update({k: v for k, v in provenance_input.items() if k not in provenance})

    skill_spec = SkillSpec(
        name=name,
        description=description,
        content=content,
        source_format=source_format,
        provenance=provenance,
        metadata_confidence=str(data.get("metadata_confidence") or "inferred"),
        required_tools=required_tools,
        required_mcp_servers=required_mcp_servers,
        risks=risks,
    )

    compatibility_score = 0.7 if content and source_format != "unknown" else 0.35 if content else 0.0
    contract = build_empty_skill_import_contract(
        source_format=source_format,
        source_platform=source_platform,
        source_url=str(data.get("source_url") or ""),
        source_author=str(data.get("source_author") or "unknown"),
        source_license=str(data.get("source_license") or "unknown"),
        source_hash=provenance["source_hash"] if provenance["source_hash"] != "unknown" else "",
        import_adapter=adapter,
        normalized_to="openswarm.skill.v1.preview",
        compatibility_score=compatibility_score,
        metadata_confidence=skill_spec.metadata_confidence,
        conversion_warnings=conversion_warnings,
        unsupported_features=unsupported_features,
        required_tools=required_tools,
        required_mcp_servers=required_mcp_servers,
        risks=risks,
        original_files=_as_list(data.get("original_files")),
        normalized_files=[{"path": "SkillSpec.preview.json", "role": "preview"}],
    )

    return {
        "ok": bool(content),
        "skill_spec_preview": skill_spec.model_dump(mode="json"),
        "import_contract": contract,
        "conversion_warnings": conversion_warnings,
        "unsupported_features": unsupported_features,
        "risks": risks,
        "can_create_candidate": False,
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }
