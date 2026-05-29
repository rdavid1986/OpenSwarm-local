"""Read-only skill quality reviewer for OpenSwarm SkillSpec records."""

from __future__ import annotations

import re
from typing import Any

from backend.apps.skills.knowledge_contract import build_skill_knowledge_contract
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


REVIEW_KIND = "skill_quality_review"

RECOMMENDED_SECTIONS = [
    "Role and scope",
    "Expert methodology",
    "Decision criteria",
    "Execution guidance",
    "Validation",
    "Pitfalls",
    "Boundaries",
]


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _has_examples(content: str) -> bool:
    normalized = _normalized(content)
    return any(token in normalized for token in ("## examples", "## ejemplos", "example:", "for example", "por ejemplo"))


def _item(
    code: str,
    severity: str,
    title: str,
    message: str,
    suggested_section: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "message": message,
        "suggested_section": suggested_section,
        "reason": reason,
        "auto_apply_supported": False,
    }


def _human_item_label(item: dict[str, Any]) -> str:
    code = str(item.get("code") or "")
    labels = {
        "add_expert_role": "Define the expert role",
        "add_methodology": "Explain the expert methodology",
        "add_decision_criteria": "Add decision criteria",
        "add_validation_guidance": "Add validation criteria",
        "add_pitfalls": "Add pitfalls and anti-patterns",
        "add_boundaries": "Clarify scope and boundaries",
        "clarify_skill_not_action": "Clarify that this skill does not activate tools or permissions",
        "clarify_required_tools_are_declarative": "Clarify that declared tools/MCP are requirements only",
        "add_domain_specific_examples": "Add domain-specific examples",
        "web_research_recommended": "Add research notes for current information",
    }
    return labels.get(code, str(item.get("title") or "Improve this skill"))


def _human_strengths(quality_contract: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    if quality_contract.get("has_role_definition"):
        strengths.append("Clear expert perspective or domain-specialist guidance.")
    if quality_contract.get("has_expert_methodology"):
        strengths.append("Includes a repeatable methodology, framework, guidelines, or workflow.")
    if quality_contract.get("has_decision_criteria"):
        strengths.append("Includes criteria, tradeoffs, constraints, or heuristics for decisions.")
    if quality_contract.get("has_validation_guidance"):
        strengths.append("Includes quality, validation, review, or acceptance guidance.")
    if quality_contract.get("has_pitfalls"):
        strengths.append("Calls out mistakes, anti-patterns, risks, or things to avoid.")
    if quality_contract.get("has_operational_boundaries"):
        strengths.append("Defines scope, constraints, assumptions, or operating boundaries.")
    if quality_contract.get("has_action_boundary_statement"):
        strengths.append("Clarifies the Skill/Action boundary and permissions model.")
    return strengths


QUALITY_GAP_CODES = {
    "add_expert_role",
    "add_methodology",
    "add_decision_criteria",
    "add_validation_guidance",
    "add_pitfalls",
    "add_boundaries",
}

OPENSWARM_ADAPTATION_CODES = {
    "clarify_skill_not_action",
    "clarify_required_tools_are_declarative",
}

EXAMPLES_GAP_CODES = {
    "add_domain_specific_examples",
}


def _split_improvement_items(improvement_items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    quality_gap_items: list[dict[str, Any]] = []
    openswarm_adaptation_items: list[dict[str, Any]] = []
    examples_gap_items: list[dict[str, Any]] = []
    research_gap_items: list[dict[str, Any]] = []

    for item in improvement_items:
        code = str(item.get("code") or "")
        if code in QUALITY_GAP_CODES:
            quality_gap_items.append(item)
        elif code in OPENSWARM_ADAPTATION_CODES:
            openswarm_adaptation_items.append(item)
        elif code in EXAMPLES_GAP_CODES:
            examples_gap_items.append(item)
        elif code == "web_research_recommended":
            research_gap_items.append(item)
        else:
            quality_gap_items.append(item)

    return {
        "quality_gap_items": quality_gap_items,
        "openswarm_adaptation_items": openswarm_adaptation_items,
        "examples_gap_items": examples_gap_items,
        "research_gap_items": research_gap_items,
    }


def _skill_profile(spec: SkillSpec, quality_contract: dict[str, Any]) -> str:
    text = _normalized(f"{spec.name}\n{spec.description}\n{spec.content}")
    if any(token in text for token in ("docx", ".docx", "word document", "pptx", ".pptx", "pdf", ".pdf", "xlsx", "spreadsheet")):
        return "document_workflow"
    if any(token in text for token in ("frontend", "design", "aesthetics", "typography", "motion", "visual")):
        return "design_creation"
    if any(token in text for token in ("communication", "comms", "newsletter", "status report", "leadership update")):
        return "communication_template"
    if any(token in text for token in ("mcp", "api", "server", "sdk", "tool")):
        return "procedural_tool_guide"
    if quality_contract.get("has_expert_methodology") and quality_contract.get("has_decision_criteria"):
        return "expert_behavior"
    return "general_skill"


def _human_review_fields(
    *,
    spec: SkillSpec,
    quality_contract: dict[str, Any],
    improvement_items: list[dict[str, Any]],
    action_boundary_status: str,
    research_recommendation: dict[str, Any],
) -> dict[str, Any]:
    strengths = _human_strengths(quality_contract)
    taxonomy = _split_improvement_items(improvement_items)
    skill_profile = _skill_profile(spec, quality_contract)

    quality_missing = [_human_item_label(item) for item in taxonomy["quality_gap_items"]]
    adaptation_missing = [_human_item_label(item) for item in taxonomy["openswarm_adaptation_items"]]
    research_missing = [_human_item_label(item) for item in taxonomy["research_gap_items"]]
    examples_missing = [_human_item_label(item) for item in taxonomy["examples_gap_items"]]

    missing_items = quality_missing + adaptation_missing + research_missing
    next_steps = quality_missing + adaptation_missing + research_missing

    if not strengths:
        summary = "This skill still looks too generic to work as reusable expert knowledge."
    elif not taxonomy["quality_gap_items"] and not taxonomy["openswarm_adaptation_items"]:
        summary = "This skill has a strong expert-knowledge structure and already includes applicable guidance."
    elif not taxonomy["quality_gap_items"] and taxonomy["openswarm_adaptation_items"]:
        summary = "This skill has strong expert content. The remaining work is mainly OpenSwarm adaptation, not content quality."
    else:
        summary = "This skill already has useful expert content, but still needs quality improvements before it is ideal."

    if action_boundary_status != "clear":
        summary += " It should also clarify that the skill does not activate tools, MCP, or permissions."
    if research_recommendation.get("status") == "web_research_recommended":
        next_steps.append("Mark time-sensitive claims for a separate, permitted web research workflow.")
    if examples_missing and not quality_missing:
        next_steps.append("Consider examples only if they would make the skill easier to apply; this is not a core quality blocker.")
    if strengths:
        next_steps.append("Keep the domain-specific guidance because it helps future agents apply professional judgment.")

    if not taxonomy["quality_gap_items"] and taxonomy["openswarm_adaptation_items"]:
        status_label = "Strong skill · OpenSwarm adaptation needed"
    elif not improvement_items:
        status_label = "Strong expert skill"
    else:
        status_label = "Needs expert-skill polish"

    return {
        "human_summary": summary,
        "human_status_label": status_label,
        "human_next_steps": next_steps,
        "human_strengths": strengths,
        "human_missing_items": missing_items,
        "skill_profile": skill_profile,
        "quality_gap_items": taxonomy["quality_gap_items"],
        "openswarm_adaptation_items": taxonomy["openswarm_adaptation_items"],
        "examples_gap_items": taxonomy["examples_gap_items"],
        "research_gap_items": taxonomy["research_gap_items"],
        "technical_details_label": "Technical reviewer details",
    }


def _research_recommendation(spec: SkillSpec) -> dict[str, Any]:
    text = _normalized(f"{spec.name}\n{spec.description}\n{spec.content}")
    needs_current_info = any(
        token in text
        for token in (
            "latest",
            "current",
            "up-to-date",
            "recent",
            "today",
            "último",
            "actualizado",
            "reciente",
        )
    )
    if needs_current_info:
        return {
            "status": "web_research_recommended",
            "message": "Some claims may depend on current external knowledge. Recommend web research before finalizing, but this reviewer does not browse.",
        }
    return {
        "status": "not_required",
        "message": "No obvious current-information dependency detected by the static reviewer.",
    }


def review_skill_spec(spec: SkillSpec, candidate_id: str | None = None) -> dict[str, Any]:
    """Return a JSON-safe quality review without modifying the SkillSpec."""

    quality_contract = build_skill_knowledge_contract(spec)
    improvement_items: list[dict[str, Any]] = []
    missing_sections: list[str] = []

    checks = [
        ("has_role_definition", "add_expert_role", "high", "Define the expert role", "Role and scope", "The skill should tell future agents which expert persona and quality bar to adopt."),
        ("has_expert_methodology", "add_methodology", "high", "Add expert methodology", "Expert methodology", "A skill should teach a repeatable expert workflow, not only describe a task."),
        ("has_decision_criteria", "add_decision_criteria", "medium", "Add decision criteria", "Decision criteria", "Future agents need tradeoffs, heuristics, and criteria for choosing between valid approaches."),
        ("has_validation_guidance", "add_validation_guidance", "medium", "Add validation guidance", "Validation", "Quality should be testable with checks, acceptance criteria, or review steps."),
        ("has_pitfalls", "add_pitfalls", "medium", "Add pitfalls and anti-patterns", "Pitfalls", "Expert knowledge should include common mistakes, risks, and what to avoid."),
        ("has_operational_boundaries", "add_boundaries", "medium", "Add operational boundaries", "Boundaries", "The skill should state scope, limits, assumptions, and portability constraints."),
    ]
    for check_key, code, severity, title, section, reason in checks:
        if not quality_contract[check_key]:
            missing_sections.append(section)
            improvement_items.append(_item(
                code,
                severity,
                title,
                f"Add a `{section}` section with concrete, domain-specific guidance.",
                section,
                reason,
            ))

    action_boundary_status = "clear" if quality_contract["has_action_boundary_statement"] else "missing"
    if not quality_contract["has_action_boundary_statement"]:
        missing_sections.append("Action boundary statement")
        improvement_items.append(_item(
            "clarify_skill_not_action",
            "high",
            "Clarify Skill vs Action boundary",
            "State that the skill is expert knowledge, not an Action, and does not grant permissions, activate tools/MCP, or execute external operations.",
            "Boundaries",
            "OpenSwarm separates expert knowledge (Skills) from external operations (Actions/tools/MCP).",
        ))

    has_declarative_requirements = bool(spec.required_tools or spec.required_mcp_servers)
    if has_declarative_requirements and not quality_contract["has_action_boundary_statement"]:
        action_boundary_status = "requirements_declared_boundary_missing"
        improvement_items.append(_item(
            "clarify_required_tools_are_declarative",
            "medium",
            "Clarify declarative requirements",
            "Explain that required_tools and required_mcp_servers are requirements only and do not make tools/MCP available.",
            "Boundaries",
            "Declared requirements must not be confused with permissions, activation, or installed Actions.",
        ))

    if not _has_examples(spec.content):
        improvement_items.append(_item(
            "add_domain_specific_examples",
            "low",
            "Add domain-specific examples",
            "Add concise examples showing expert inputs, outputs, review decisions, or edge cases.",
            "Examples",
            "Examples make the skill less generic and easier for future agents and MiniAgents to apply consistently.",
        ))

    research_recommendation = _research_recommendation(spec)
    if research_recommendation["status"] == "web_research_recommended":
        improvement_items.append(_item(
            "web_research_recommended",
            "medium",
            "Research current information before finalizing",
            "Mark any time-sensitive domain claims for web research by a separate, permitted workflow.",
            "Research notes",
            "This reviewer is read-only and does not use internet, but the skill appears to depend on current information.",
        ))

    status = "strong" if not improvement_items else "needs_improvement"
    high_count = sum(1 for item in improvement_items if item["severity"] == "high")
    medium_count = sum(1 for item in improvement_items if item["severity"] == "medium")
    improvement_summary = (
        "Skill has a strong expert-knowledge structure."
        if status == "strong"
        else f"Skill needs quality improvements: {high_count} high, {medium_count} medium, {len(improvement_items) - high_count - medium_count} low."
    )
    human_fields = _human_review_fields(
        spec=spec,
        quality_contract=quality_contract,
        improvement_items=improvement_items,
        action_boundary_status=action_boundary_status,
        research_recommendation=research_recommendation,
    )

    return {
        "review_kind": REVIEW_KIND,
        "candidate_id": candidate_id,
        "skill_name": str(spec.name or "").strip(),
        "status": status,
        "install_approved": False,
        "quality_contract": quality_contract,
        "improvement_summary": improvement_summary,
        **human_fields,
        "improvement_items": improvement_items,
        "recommended_sections": RECOMMENDED_SECTIONS,
        "missing_sections": missing_sections,
        "action_boundary_status": action_boundary_status,
        "risk_notes": [
            "Review is static and heuristic; it does not call models, browse, install, approve, or modify candidates.",
            "Do not treat required_tools or required_mcp_servers as granted permissions or active integrations.",
        ],
        "research_recommendation": research_recommendation,
        "safe_to_auto_apply": False,
    }


def review_skill_candidate(candidate: SkillSpecCandidate) -> dict[str, Any]:
    """Return a JSON-safe quality review without mutating the candidate."""

    review = review_skill_spec(candidate.skill_spec, candidate_id=candidate.candidate_id)
    return {
        **review,
        "status": candidate.status,
        "candidate_status": candidate.status,
        "install_approved": bool(candidate.install_approved),
        "safe_to_auto_apply": False,
    }
