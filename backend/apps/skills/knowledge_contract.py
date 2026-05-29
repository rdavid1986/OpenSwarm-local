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


def _has_heading(content: str, heading_terms: tuple[str, ...]) -> bool:
    for line in content.splitlines():
        stripped = line.strip().lower()
        if not stripped.startswith("#"):
            continue
        if any(term in stripped for term in heading_terms):
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

    has_role_definition = _has_heading(content, ("role", "persona", "expert")) or _has_any(
        combined,
        (
            "act as",
            "actúa como",
            "you are a",
            "you are an",
            "senior",
            "expert",
            "specialist",
            "professional",
        ),
    )
    has_expert_methodology = _has_heading(content, ("methodology", "workflow", "process", "approach", "metodología")) or _has_any(
        combined,
        ("methodology", "workflow", "step-by-step", "process", "approach", "metodología", "proceso"),
    )
    has_decision_criteria = _has_heading(content, ("decision", "criteria", "tradeoff", "heuristic", "criterio")) or _has_any(
        combined,
        ("decision criteria", "tradeoff", "choose", "prefer", "when to", "criterios", "decidir"),
    )
    has_validation_guidance = _has_heading(content, ("validation", "verify", "testing", "quality", "validación")) or _has_any(
        combined,
        ("validate", "verify", "test", "check", "acceptance criteria", "quality bar", "validar", "verificar"),
    )
    has_pitfalls = _has_heading(content, ("pitfall", "anti-pattern", "gotcha", "risk", "avoid", "errores")) or _has_any(
        combined,
        ("pitfall", "anti-pattern", "gotcha", "avoid", "common mistake", "risk", "riesgo", "evitar"),
    )
    has_operational_boundaries = _has_heading(content, ("boundary", "boundaries", "scope", "constraints", "limits", "non-goals")) or _has_any(
        combined,
        (
            "boundary",
            "boundaries",
            "scope",
            "constraints",
            "limits",
            "non-goals",
            "permissions",
            "provider",
            "portable",
        ),
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
        "warnings": warnings,
    }
