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


def _parse_simple_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not str(content or "").startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    raw_frontmatter = content[3:end].strip()
    body = content[end + 3 :].strip()
    parsed: dict[str, str] = {}
    for line in raw_frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed, body


def _legacy_metadata(data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    meta_json = data.get("meta_json") if isinstance(data.get("meta_json"), dict) else {}
    merged = {**meta_json, **metadata}
    return merged


def _prepared_content_from_files(data: dict[str, Any]) -> str:
    files = data.get("files")
    if not isinstance(files, list):
        return ""
    for file in files:
        if not isinstance(file, dict):
            continue
        name = str(file.get("name") or file.get("path") or "").lower().replace("\\", "/")
        if name.endswith("skill.md") or name.endswith(".md"):
            content = str(file.get("content") or "")
            if content:
                return content
    return ""


def _normalize_prepared_legacy_or_skillspec_input(data: dict[str, Any]) -> dict[str, Any]:
    source_format = str(data.get("source_format") or "unknown")
    metadata = _legacy_metadata(data)
    content = str(data.get("content") or _prepared_content_from_files(data) or metadata.get("content") or "")
    name = str(data.get("name") or metadata.get("name") or metadata.get("title") or "Imported OpenSwarm Skill Preview")
    description = str(data.get("description") or metadata.get("description") or "")
    command = str(data.get("command") or metadata.get("command") or "")
    return {
        **data,
        "source_format": source_format,
        "source_platform": str(data.get("source_platform") or "openswarm"),
        "name": name,
        "description": description,
        "command": command,
        "content": content,
        "metadata_confidence": str(data.get("metadata_confidence") or "inferred"),
        "source_author": str(data.get("source_author") or metadata.get("author") or "unknown"),
        "source_license": str(data.get("source_license") or metadata.get("license") or "unknown"),
        "provenance": {
            **(data.get("provenance") if isinstance(data.get("provenance"), dict) else {}),
            "legacy_metadata_present": bool(metadata),
            "preview_only": True,
        },
    }


def _normalize_prepared_claude_skill_input(data: dict[str, Any]) -> dict[str, Any]:
    content = str(data.get("content") or _prepared_content_from_files(data) or "")
    parsed_frontmatter, body = _parse_simple_frontmatter(content)
    supplied_frontmatter = data.get("frontmatter") if isinstance(data.get("frontmatter"), dict) else {}
    frontmatter = {**parsed_frontmatter, **supplied_frontmatter}
    return {
        **data,
        "source_platform": str(data.get("source_platform") or "claude"),
        "frontmatter": frontmatter,
        "name": str(data.get("name") or frontmatter.get("name") or "Imported Claude Skill Preview"),
        "description": str(data.get("description") or frontmatter.get("description") or ""),
        "content": content,
        "metadata_confidence": str(data.get("metadata_confidence") or "inferred"),
        "provenance": {
            **(data.get("provenance") if isinstance(data.get("provenance"), dict) else {}),
            "frontmatter_present": bool(frontmatter),
            "body_preview": body[:240],
            "preview_only": True,
        },
    }


def _normalize_input_for_supported_adapter(data: dict[str, Any]) -> dict[str, Any]:
    source_format = str(data.get("source_format") or "unknown")
    if source_format in {"openswarm_legacy_skill", "openswarm_skillspec"}:
        return _normalize_prepared_legacy_or_skillspec_input(data)
    if source_format in {"anthropic_skill", "claude_skill"}:
        return _normalize_prepared_claude_skill_input(data)
    return data


def normalize_external_skill_to_skillspec_preview(input: dict[str, Any]) -> dict[str, Any]:
    """Normalize caller-prepared content into a SkillSpec preview only."""

    data = _normalize_input_for_supported_adapter(input or {})
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
        command=str(data.get("command") or ""),
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
