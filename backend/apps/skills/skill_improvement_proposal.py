"""Read-only skill improvement proposal builder.

This module converts a skill quality review into a structured proposal.
It never mutates candidates, writes files, installs skills, approves installs,
activates tools, activates MCP, or performs web research.
"""

from __future__ import annotations

from typing import Any

from backend.apps.skills.models import SkillSpec, SkillSpecCandidate
from backend.apps.skills.skill_reviewer import review_skill_candidate, review_skill_spec


PROPOSAL_KIND = "skill_improvement_proposal"


def _proposal_item(source: str, item: dict[str, Any]) -> dict[str, Any]:
    code = str(item.get("code") or "unknown")
    title = str(item.get("title") or item.get("message") or code)
    section = str(item.get("suggested_section") or "SKILL.md")
    severity = str(item.get("severity") or "low")

    return {
        "source": source,
        "code": code,
        "severity": severity,
        "title": title,
        "target_section": section,
        "rationale": str(item.get("reason") or item.get("message") or ""),
        "proposed_change": str(item.get("message") or title),
        "auto_apply_supported": False,
    }


def build_skill_improvement_proposal_from_review(
    review: dict[str, Any],
    *,
    candidate_id: str | None = None,
    skill_name: str = "",
) -> dict[str, Any]:
    """Build a JSON-safe improvement proposal from an existing review."""

    proposal_items: list[dict[str, Any]] = []
    for source, key in (
        ("quality_gap", "quality_gap_items"),
        ("openswarm_adaptation", "openswarm_adaptation_items"),
        ("profile_gap", "profile_gap_items"),
        ("examples_gap", "examples_gap_items"),
        ("research_gap", "research_gap_items"),
    ):
        for item in review.get(key, []) or []:
            if isinstance(item, dict):
                proposal_items.append(_proposal_item(source, item))

    requires_web_research = any(item["source"] == "research_gap" for item in proposal_items)
    requires_user_approval = bool(proposal_items)

    return {
        "proposal_kind": PROPOSAL_KIND,
        "candidate_id": candidate_id,
        "skill_name": skill_name or str(review.get("skill_name") or ""),
        "review_kind": review.get("review_kind"),
        "status": "proposal_ready" if proposal_items else "no_changes_recommended",
        "summary": (
            "Review found structured improvements that can be turned into a future diff."
            if proposal_items
            else "Review did not find improvement items."
        ),
        "proposal_items": proposal_items,
        "item_count": len(proposal_items),
        "requires_user_approval": requires_user_approval,
        "requires_web_research": requires_web_research,
        "safe_to_auto_apply": False,
        "can_generate_diff": False,
        "can_update_candidate": False,
        "next_step": (
            "Generate a reviewable diff in a later phase after explicit approval."
            if proposal_items
            else "No proposal action is needed."
        ),
        "guardrails": [
            "This proposal is read-only.",
            "It does not modify the candidate.",
            "It does not install or approve the skill.",
            "It does not activate tools, MCP, or permissions.",
            "It does not browse the web.",
        ],
    }


def build_skill_improvement_proposal(spec: SkillSpec) -> dict[str, Any]:
    review = review_skill_spec(spec)
    return build_skill_improvement_proposal_from_review(
        review,
        candidate_id=None,
        skill_name=spec.name,
    )


def build_skill_candidate_improvement_proposal(candidate: SkillSpecCandidate) -> dict[str, Any]:
    review = review_skill_candidate(candidate)
    return build_skill_improvement_proposal_from_review(
        review,
        candidate_id=candidate.candidate_id,
        skill_name=candidate.skill_spec.name,
    )
