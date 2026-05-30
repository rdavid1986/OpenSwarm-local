"""Build in-memory SkillSpecCandidate objects from approved import previews.

This module does not persist candidates, install skills, approve install, execute
source material, or activate tools/MCP.
"""

from __future__ import annotations

from typing import Any

from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _source_ref(preview_report: dict[str, Any], spec: dict[str, Any]) -> str:
    provenance = spec.get("provenance") if isinstance(spec.get("provenance"), dict) else {}
    for value in (provenance.get("source_url"), provenance.get("source_hash"), preview_report.get("preview_id")):
        text = str(value or "").strip()
        if text and text != "unknown":
            return text
    return str(preview_report.get("preview_id") or "skill_import_preview")


def build_skill_candidate_from_import_preview(preview_report: dict[str, Any], policy_gate: dict[str, Any]) -> SkillSpecCandidate:
    """Convert an allowed preview report to an in-memory candidate only."""

    if not (policy_gate or {}).get("can_create_candidate"):
        raise ValueError("skill_import_policy_blocks_candidate_creation")

    spec_data = (preview_report or {}).get("skill_spec_preview")
    if not isinstance(spec_data, dict):
        raise ValueError("skill_import_preview_missing_skill_spec")

    skill_spec = SkillSpec(**spec_data)
    contract = preview_report.get("import_contract") if isinstance(preview_report.get("import_contract"), dict) else {}
    evidence_refs = _as_list(contract.get("evidence_refs"))
    policy_refs = []
    decision = str(policy_gate.get("decision") or "").strip()
    if decision:
        policy_refs.append(f"skill_import_policy:{decision}")

    return SkillSpecCandidate(
        skill_spec=skill_spec,
        status="candidate",
        source="skill_import",
        source_ref=_source_ref(preview_report, spec_data),
        evidence_refs=evidence_refs,
        policy_refs=policy_refs,
        install_approved=False,
        research_approved=False,
        research_evidence=[],
    )
