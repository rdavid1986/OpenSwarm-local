"""Read-only knowledge-quality contract for OpenSwarm SkillSpec records."""

from __future__ import annotations

import re
from typing import Any

from backend.apps.skills.models import SkillSpec


CONTRACT_KIND = "skill_knowledge_contract"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean_text(value).lower())


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _match_count(text: str, needles: tuple[str, ...]) -> int:
    return sum(1 for needle in needles if needle in text)


def _has_heading(content: str, heading_terms: tuple[str, ...]) -> bool:
    for line in content.splitlines():
        stripped = line.strip().lower()
        if not stripped.startswith("#"):
            continue
        if any(term in stripped for term in heading_terms):
            return True
    return False


def _has_emphasis_rule(content: str, terms: tuple[str, ...]) -> bool:
    for line in content.splitlines():
        stripped = line.strip()
        if any(term in stripped for term in terms):
            return True
    return False


def _warning(code: str, message: str, *, severity: str = "low") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def build_skill_knowledge_contract(spec: SkillSpec) -> dict[str, Any]:
    """Build a conservative, side-effect-free report for skill knowledge quality.

    The report is heuristic by design: it never installs, approves, mutates,
    calls models, calls tools, activates MCP, or fetches external context.
    """

    name = _clean_text(spec.name)
    description = _clean_text(spec.description)
    content = _clean_text(spec.content)
    combined = _normalized(f"{name}\n{description}\n{content}")
    content_lines = [line.strip() for line in content.splitlines() if line.strip()]
    content_has_depth = len(content) >= 350 and len(content_lines) >= 8

    methodology_terms = (
        "methodology",
        "workflow",
        "step-by-step",
        "process",
        "approach",
        "framework",
        "checklist",
        "guidelines",
        "principles",
        "design thinking",
        "frontend aesthetics guidelines",
        "aesthetics guidelines",
        "before coding",
        "before implementing",
        "focus on",
        "metodolog",
        "proceso",
    )
    domain_terms = (
        "frontend",
        "design",
        "aesthetics",
        "typography",
        "color",
        "theme",
        "motion",
        "spatial",
        "composition",
        "background",
        "visual",
        "accessibility",
        "layout",
        "component",
        "responsive",
        "interaction",
        "contrast",
        "spacing",
        "animation",
        "product intent",
        "user intent",
        "tone",
        "differentiation",
    )
    decision_terms = (
        "decision criteria",
        "tradeoff",
        "trade-off",
        "choose",
        "prefer",
        "when to",
        "criteria",
        "heuristic",
        "constraints",
        "purpose",
        "tone",
        "differentiation",
        "criterios",
        "decidir",
    )
    validation_terms = (
        "validation",
        "validate",
        "verify",
        "testing",
        "test",
        "check",
        "review checklist",
        "acceptance criteria",
        "quality bar",
        "quality",
        "validaci",
        "validar",
        "verificar",
    )
    pitfall_terms = (
        "pitfall",
        "anti-pattern",
        "anti pattern",
        "gotcha",
        "avoid",
        "never",
        "common mistake",
        "mistake",
        "risk",
        "generic",
        "errores",
        "riesgo",
        "evitar",
    )
    boundary_terms = (
        "boundary",
        "boundaries",
        "scope",
        "constraints",
        "limits",
        "non-goals",
        "permissions",
        "provider",
        "portable",
        "assumptions",
    )

    method_signal_count = _match_count(combined, methodology_terms)
    domain_signal_count = _match_count(combined, domain_terms)
    decision_signal_count = _match_count(combined, decision_terms)
    validation_signal_count = _match_count(combined, validation_terms)
    pitfall_signal_count = _match_count(combined, pitfall_terms)
    boundary_signal_count = _match_count(combined, boundary_terms)
    has_strong_domain_guidance = content_has_depth and domain_signal_count >= 4 and method_signal_count >= 2

    has_role_definition = _has_heading(content, ("role", "persona", "expert")) or _has_any(
        combined,
        (
            "act as",
            "actua como",
            "actúa como",
            "you are a",
            "you are an",
            "senior",
            "expert",
            "specialist",
            "professional",
        ),
    ) or has_strong_domain_guidance
    has_expert_methodology = (
        _has_heading(content, ("methodology", "workflow", "process", "approach", "framework", "checklist", "guideline", "principle", "design thinking", "aesthetics"))
        or (method_signal_count >= 1 and content_has_depth and domain_signal_count >= 2)
        or (method_signal_count >= 2 and len(content) >= 180)
    )
    has_decision_criteria = (
        _has_heading(content, ("decision", "criteria", "tradeoff", "heuristic", "criterio", "constraint"))
        or (decision_signal_count >= 2 and content_has_depth)
    )
    has_validation_guidance = (
        _has_heading(content, ("validation", "verify", "testing", "quality", "review checklist", "validaci"))
        or (validation_signal_count >= 2 and content_has_depth)
        or (_has_emphasis_rule(content, ("CRITICAL", "IMPORTANT")) and validation_signal_count >= 1)
    )
    has_pitfalls = (
        _has_heading(content, ("pitfall", "anti-pattern", "anti pattern", "gotcha", "risk", "avoid", "errores"))
        or (pitfall_signal_count >= 2 and len(content) >= 180)
        or (_has_emphasis_rule(content, ("NEVER",)) and pitfall_signal_count >= 1)
    )
    has_operational_boundaries = (
        _has_heading(content, ("boundary", "boundaries", "scope", "constraints", "limits", "non-goals"))
        or (boundary_signal_count >= 1 and content_has_depth)
    )
    has_action_boundary_statement = _has_any(
        combined,
        (
            "not an action",
            "is not an action",
            "does not grant permissions",
            "does not activate tools",
            "does not activate mcp",
            "does not execute external operations",
            "required_tools",
            "required_mcp_servers",
            "no concede permisos",
            "no activa herramientas",
            "no activa mcp",
            "no ejecuta operaciones externas",
        ),
    )

    warnings: list[dict[str, str]] = []
    if len(content) < 120:
        warnings.append(_warning("skill_content_too_short", "SKILL.md content is too short to carry expert knowledge.", severity="medium"))
    if _has_any(combined, ("do the task", "help with tasks", "be useful", "best practices")) and len(content) < 600:
        warnings.append(_warning("skill_content_generic", "Skill content appears generic; add discipline-specific expert guidance.", severity="low"))

    checks = {
        "has_role_definition": has_role_definition,
        "has_expert_methodology": has_expert_methodology,
        "has_decision_criteria": has_decision_criteria,
        "has_validation_guidance": has_validation_guidance,
        "has_pitfalls": has_pitfalls,
        "has_operational_boundaries": has_operational_boundaries,
        "has_action_boundary_statement": has_action_boundary_statement,
    }
    messages = {
        "has_role_definition": "Define the expert role/persona the agent should adopt.",
        "has_expert_methodology": "Add an expert workflow or methodology.",
        "has_decision_criteria": "Add decision criteria, tradeoffs, or heuristics.",
        "has_validation_guidance": "Add validation, testing, or quality guidance.",
        "has_pitfalls": "Add pitfalls, anti-patterns, risks, or mistakes to avoid.",
        "has_operational_boundaries": "Add scope, constraints, portability, or operational boundaries.",
        "has_action_boundary_statement": "State that the skill is knowledge, not an Action, and does not grant permissions or activate tools/MCP.",
    }
    for code, present in checks.items():
        if not present:
            warnings.append(_warning(code.replace("has_", "missing_"), messages[code], severity="low"))

    if (spec.required_tools or spec.required_mcp_servers) and not has_action_boundary_statement:
        warnings.append(_warning(
            "missing_declarative_tool_boundary",
            "Required tools/MCP servers should be declared as requirements only; the skill must not assume availability.",
            severity="medium",
        ))

    return {
        "contract_kind": CONTRACT_KIND,
        "skill_name": name,
        **checks,
        "signal_summary": {
            "domain_signal_count": domain_signal_count,
            "methodology_signal_count": method_signal_count,
            "decision_signal_count": decision_signal_count,
            "validation_signal_count": validation_signal_count,
            "pitfall_signal_count": pitfall_signal_count,
            "boundary_signal_count": boundary_signal_count,
            "content_has_depth": content_has_depth,
        },
        "warnings": warnings,
    }
