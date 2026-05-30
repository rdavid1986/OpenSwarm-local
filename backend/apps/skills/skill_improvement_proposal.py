"""Read-only skill improvement proposal builder.

This module converts a skill quality review into a structured proposal.
It never mutates candidates, writes files, installs skills, approves installs,
activates tools, activates MCP, or performs web research.
"""

from __future__ import annotations

from difflib import unified_diff
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


def _section_block(item: dict[str, Any]) -> str:
    title = str(item.get("target_section") or item.get("title") or "Improvement").strip()
    proposed_change = str(item.get("proposed_change") or "").strip()
    rationale = str(item.get("rationale") or "").strip()
    source = str(item.get("source") or "review").strip()
    code = str(item.get("code") or "unknown").strip()

    lines = [
        f"## {title}",
        "",
        f"Source: {source}",
        f"Code: {code}",
    ]
    if proposed_change:
        lines.extend(["", proposed_change])
    if rationale:
        lines.extend(["", f"Rationale: {rationale}"])
    return "\n".join(lines).strip()


def _build_proposed_content(current_content: str, proposal_items: list[dict[str, Any]]) -> str:
    base = str(current_content or "").rstrip()
    if not proposal_items:
        return base

    blocks = [_section_block(item) for item in proposal_items]
    appendix = "\n\n".join(block for block in blocks if block)
    if not appendix:
        return base

    prefix = "\n\n" if base else ""
    return f"{base}{prefix}# OpenSwarm proposed improvements\n\n{appendix}\n"


def _build_preview_diff(current_content: str, proposed_content: str) -> str:
    return "".join(
        unified_diff(
            str(current_content or "").splitlines(keepends=True),
            str(proposed_content or "").splitlines(keepends=True),
            fromfile="current/SKILL.md",
            tofile="proposed/SKILL.md",
        )
    )


def build_skill_improvement_proposal_from_review(
    review: dict[str, Any],
    *,
    candidate_id: str | None = None,
    skill_name: str = "",
    current_content: str = "",
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
    proposed_content = _build_proposed_content(current_content, proposal_items)
    preview_diff = _build_preview_diff(current_content, proposed_content)

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
        "can_generate_diff": bool(preview_diff),
        "can_update_candidate": False,
        "proposed_content": proposed_content,
        "preview_diff": preview_diff,
        "next_step": (
            "Review the generated diff, then request candidate update in a later approval-gated phase."
            if preview_diff
            else "No proposal action is needed."
        ),
        "guardrails": [
            "This proposal is read-only.",
            "It does not modify the candidate.",
            "It does not install or approve the skill.",
            "It does not activate tools, MCP, or permissions.",
            "It does not browse the web.",
            "The diff preview is not applied automatically.",
        ],
    }


def build_skill_improvement_proposal(spec: SkillSpec) -> dict[str, Any]:
    review = review_skill_spec(spec)
    return build_skill_improvement_proposal_from_review(
        review,
        candidate_id=None,
        skill_name=spec.name,
        current_content=spec.content,
    )


def build_skill_candidate_improvement_proposal(candidate: SkillSpecCandidate) -> dict[str, Any]:
    review = review_skill_candidate(candidate)
    return build_skill_improvement_proposal_from_review(
        review,
        candidate_id=candidate.candidate_id,
        skill_name=candidate.skill_spec.name,
        current_content=candidate.skill_spec.content,
    )
