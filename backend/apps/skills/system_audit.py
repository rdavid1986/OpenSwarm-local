"""Read-only Skill System audit for OpenSwarm.

This module summarizes current Skill Builder / Skill Reviewer / Registry
capabilities and the remaining roadmap gaps. It does not mutate candidates,
install skills, browse the web, call models, activate tools, or activate MCP.
"""

from __future__ import annotations

from typing import Any

from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


AUDIT_KIND = "skill_system_audit"
AUDIT_VERSION = "openswarm.skill_audit.v1"


def _field_names(model: type) -> list[str]:
    return list(getattr(model, "model_fields", {}).keys())


def build_skill_system_audit() -> dict[str, Any]:
    skill_spec_fields = _field_names(SkillSpec)
    candidate_fields = _field_names(SkillSpecCandidate)

    capabilities = {
        "skill_spec_contract": {
            "status": "implemented",
            "fields": skill_spec_fields,
            "notes": [
                "Portable SkillSpec contract exists.",
                "Required tools and MCP servers are declarative dependencies, not activation permissions.",
            ],
        },
        "candidate_lifecycle": {
            "status": "implemented",
            "states": [
                "candidate",
                "validated",
                "rejected",
                "approved_for_install",
                "installed",
            ],
            "guards": [
                "candidate creation is not approval",
                "validation cannot approve install",
                "gate blocks missing evidence/policy refs",
                "install requires approved_for_install and install_approved",
            ],
        },
        "reviewer": {
            "status": "implemented",
            "features": [
                "quality gap taxonomy",
                "OpenSwarm adaptation gap taxonomy",
                "profile gap taxonomy",
                "examples gap taxonomy",
                "research gap taxonomy",
                "skill profile classification",
                "human-readable summary and next steps",
            ],
        },
        "research_grounding": {
            "status": "implemented",
            "features": [
                "read-only research contract",
                "explicit research approval",
                "approval-gated web research execution",
                "research_evidence persistence",
                "research evidence integration into proposals",
                "UI run approved research",
            ],
            "guardrails": [
                "research approval is not install approval",
                "research execution does not mutate skill content",
                "research execution does not install",
                "research execution does not activate tools or MCP",
            ],
        },
        "improvement_proposals": {
            "status": "implemented",
            "features": [
                "read-only proposal",
                "preview diff",
                "explicit apply",
                "candidate update only after approval",
                "install approval reset after content update",
                "research_evidence can inform proposed_content and preview_diff",
            ],
        },
        "registry": {
            "status": "partial",
            "features": [
                "remote anthropics/skills registry cache",
                "search endpoint",
                "detail endpoint",
                "stats endpoint",
                "candidate creation from registry skill",
            ],
            "gaps": [
                "no universal import adapter layer yet",
                "no provenance-rich import preview/diff/risk report yet",
                "no compatibility score yet",
                "no Skill Pack install workflow yet",
            ],
        },
        "harness": {
            "status": "not_implemented",
            "gaps": [
                "no executable skill harness",
                "no skill performance runs",
                "no task fixtures",
                "no reviewer/writer comparison",
                "no model-specific skill evaluation",
            ],
        },
    }

    next_action_matrix = [
        {
            "phase": "SKILL-AUDIT.5",
            "priority": "current",
            "action": "Capture real system capability matrix and confirm remaining gaps.",
            "reason": "Needed before moving into import, harness, packs, or deeper registry work.",
            "safe_to_implement_now": True,
        },
        {
            "phase": "SKILL-IMPORT",
            "priority": "next_candidate",
            "action": "Universal Skill Import Compatibility Layer.",
            "reason": "Registry and external skills need adapters, provenance, risk report, preview/diff, and approval gate before install.",
            "safe_to_implement_now": True,
        },
        {
            "phase": "Skill Harness",
            "priority": "next_candidate",
            "action": "Build executable skill evaluation harness.",
            "reason": "Needed to measure skill quality beyond heuristic reviewer signals.",
            "safe_to_implement_now": True,
        },
        {
            "phase": "Skill Pack / Skill Collections",
            "priority": "later",
            "action": "Bundle compatible skills into installable packs.",
            "reason": "Should follow import contract and harness validation.",
            "safe_to_implement_now": False,
        },
        {
            "phase": "Cross-surface Skills-Actions-Modes Contract Map",
            "priority": "parallel_design",
            "action": "Formalize declarative requirements surfacing across Skills, Actions, and Modes.",
            "reason": "Prevents required_tools/required_mcp_servers from becoming implicit permissions.",
            "safe_to_implement_now": True,
        },
    ]

    return {
        "audit_kind": AUDIT_KIND,
        "audit_version": AUDIT_VERSION,
        "read_only": True,
        "can_mutate_candidate": False,
        "can_install_skill": False,
        "can_approve_install": False,
        "can_execute_web": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
        "capabilities": capabilities,
        "next_action_matrix": next_action_matrix,
        "recommended_next_phase": "SKILL-IMPORT or Skill Harness after closing SKILL-AUDIT.5",
        "guardrails": [
            "This audit is read-only.",
            "It does not browse the web.",
            "It does not call models.",
            "It does not mutate candidates.",
            "It does not install skills.",
            "It does not approve install.",
            "It does not activate tools, MCP, or permissions.",
        ],
    }
