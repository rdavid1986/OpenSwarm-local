"""Read-only research contract for skill creation and improvement.

This module decides whether a skill candidate appears to need external research.
It never browses the web, fetches URLs, installs skills, approves candidates,
activates tools, activates MCP, or mutates candidate records.
"""

from __future__ import annotations

from typing import Any

from backend.apps.skills.models import SkillSpec, SkillSpecCandidate
from backend.apps.skills.skill_reviewer import review_skill_candidate, review_skill_spec


CONTRACT_KIND = "skill_research_contract"

CURRENT_INFO_CODES = {"web_research_recommended"}

CURRENT_INFO_TERMS = (
    "api",
    "sdk",
    "mcp",
    "model",
    "provider",
    "version",
    "latest",
    "current",
    "documentation",
    "docs",
    "browser",
    "web",
    "framework",
    "library",
    "playwright",
    "react",
    "unity",
    "blender",
    "photoshop",
)


def _normalized(value: str) -> str:
    return " ".join(str(value or "").lower().replace("_", " ").replace("-", " ").split())


def _suggest_queries(spec: SkillSpec) -> list[str]:
    name = str(spec.name or "").strip()
    description = str(spec.description or "").strip()
    content = str(spec.content or "").strip()
    combined = _normalized(f"{name}\n{description}\n{content}")

    queries: list[str] = []
    base = name or spec.command or "skill"

    if any(term in combined for term in ("api", "sdk", "documentation", "docs")):
        queries.append(f"{base} official documentation")
    if "mcp" in combined:
        queries.append(f"{base} Model Context Protocol official documentation")
    if any(term in combined for term in ("react", "frontend", "web")):
        queries.append(f"{base} frontend implementation current best practices")
    if any(term in combined for term in ("unity", "blender", "photoshop")):
        queries.append(f"{base} official integration documentation")
    if any(term in combined for term in ("model", "provider", "ollama", "openai", "anthropic", "qwen")):
        queries.append(f"{base} model provider compatibility documentation")

    if not queries and any(term in combined for term in CURRENT_INFO_TERMS):
        queries.append(f"{base} current official documentation")

    deduped: list[str] = []
    for query in queries:
        if query not in deduped:
            deduped.append(query)
    return deduped[:5]


def _expected_source_types(spec: SkillSpec, requires_research: bool) -> list[str]:
    if not requires_research:
        return []

    combined = _normalized(f"{spec.name}\n{spec.description}\n{spec.content}")
    source_types = ["official documentation"]

    if any(term in combined for term in ("api", "sdk", "mcp", "tool")):
        source_types.append("API or protocol reference")
    if any(term in combined for term in ("version", "latest", "current", "model", "provider")):
        source_types.append("versioned release notes or model documentation")
    if any(term in combined for term in ("security", "permissions", "oauth", "credential")):
        source_types.append("security or permission documentation")
    if any(term in combined for term in ("framework", "library", "react", "playwright")):
        source_types.append("framework documentation")

    return list(dict.fromkeys(source_types))


def build_skill_research_contract_from_review(
    spec: SkillSpec,
    review: dict[str, Any],
    *,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    research_items = [item for item in review.get("research_gap_items", []) or [] if isinstance(item, dict)]
    research_codes = {str(item.get("code") or "") for item in research_items}

    combined = _normalized(f"{spec.name}\n{spec.description}\n{spec.content}")
    term_triggered = any(term in combined for term in CURRENT_INFO_TERMS)
    requires_research = bool(research_codes & CURRENT_INFO_CODES) or term_triggered

    queries = _suggest_queries(spec) if requires_research else []
    expected_source_types = _expected_source_types(spec, requires_research)

    return {
        "contract_kind": CONTRACT_KIND,
        "candidate_id": candidate_id,
        "skill_name": spec.name,
        "requires_web_research": requires_research,
        "research_allowed": False,
        "web_research_executed": False,
        "can_mutate_candidate": False,
        "can_install_skill": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
        "research_queries": queries,
        "expected_source_types": expected_source_types,
        "research_gap_items": research_items,
        "summary": (
            "This skill appears to need current external documentation before finalizing."
            if requires_research
            else "No current-information dependency was detected by the read-only contract."
        ),
        "next_step": (
            "Request an explicit research workflow before browsing or citing sources."
            if requires_research
            else "Continue without web research unless the user requests current-source grounding."
        ),
        "guardrails": [
            "This contract is read-only.",
            "It does not browse the web.",
            "It does not fetch URLs.",
            "It does not modify the candidate.",
            "It does not install or approve the skill.",
            "It does not activate tools, MCP, or permissions.",
            "Research sources must be attached later as evidence/provenance before they affect candidate content.",
        ],
    }


def build_skill_research_contract(spec: SkillSpec) -> dict[str, Any]:
    review = review_skill_spec(spec)
    return build_skill_research_contract_from_review(spec, review)


def build_skill_candidate_research_contract(candidate: SkillSpecCandidate) -> dict[str, Any]:
    review = review_skill_candidate(candidate)
    return build_skill_research_contract_from_review(
        candidate.skill_spec,
        review,
        candidate_id=candidate.candidate_id,
    )
