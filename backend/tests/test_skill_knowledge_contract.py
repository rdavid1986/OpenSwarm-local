from copy import deepcopy

from backend.apps.skills.candidate_validation import apply_skill_candidate_validation
from backend.apps.skills.knowledge_contract import build_skill_knowledge_contract
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


EXPERT_CONTENT = """
# Senior Frontend Engineer

## Role and scope
Act as a senior frontend expert. Frame product intent, user impact, accessibility,
state ownership, rendering cost, and maintainability before proposing code.

## Expert methodology
Start by reading the relevant component, data flow, and styling tokens. Prefer
small, reversible changes. Separate UI state from server state and keep behavior
observable.

## Decision criteria
Prefer native browser behavior when it is accessible. Choose the simplest state
model that supports the interaction. Trade visual polish against complexity and
bundle cost explicitly.

## Execution guidance
Use project conventions, preserve existing APIs, and explain assumptions when
context is incomplete.

## Validation
Verify type safety, loading and empty states, keyboard flow, visual regressions,
and at least one representative user path.

## Pitfalls
Avoid hidden global state, unbounded effects, inaccessible custom controls,
layout shifts, and generic refactors unrelated to the request.

## Boundaries
This skill is expert knowledge, not an Action. It does not grant permissions,
activate tools/MCP, or execute external operations. If tools are useful, declare
them only as required_tools or required_mcp_servers.
"""

FRONTEND_DESIGN_CONTENT = """
# Frontend Design

## Design Thinking
Start with product intent, audience, tone, constraints, and differentiation.
Before coding, identify what the interface should make the user feel and do.
Use a clear approach: define purpose, select hierarchy, then tune visual rhythm.

## Frontend Aesthetics Guidelines
Focus on typography, color & theme, motion, spatial composition, responsive
layout, backgrounds, contrast, and visual details. Prefer intentional spacing
over generic card grids.

## Decision criteria
Choose typography based on density and tone. Trade decoration against clarity.
Use constraints to decide whether motion should guide attention or stay quiet.

## Quality bar
IMPORTANT: review the result for hierarchy, accessibility, contrast, empty
states, and whether the visual system supports the product intent.

## Anti-patterns
NEVER ship generic SaaS aesthetics. Avoid random gradients, inconsistent
spacing, low contrast, and motion that distracts from the task.

## Scope
This guidance covers frontend visual design and implementation choices.
"""


def test_empty_or_generic_skill_produces_knowledge_warnings():
    spec = SkillSpec(name="Helper", content="Help with tasks using best practices.")

    report = build_skill_knowledge_contract(spec)

    assert report["contract_kind"] == "skill_knowledge_contract"
    assert report["skill_name"] == "Helper"
    codes = {warning["code"] for warning in report["warnings"]}
    assert "skill_content_too_short" in codes
    assert "missing_expert_methodology" in codes
    assert "missing_action_boundary_statement" in codes


def test_expert_sections_reduce_knowledge_warnings():
    spec = SkillSpec(name="Senior Frontend", content=EXPERT_CONTENT)

    report = build_skill_knowledge_contract(spec)

    assert report["has_role_definition"] is True
    assert report["has_expert_methodology"] is True
    assert report["has_decision_criteria"] is True
    assert report["has_validation_guidance"] is True
    assert report["has_pitfalls"] is True
    assert report["has_operational_boundaries"] is True
    assert report["has_action_boundary_statement"] is True
    assert report["warnings"] == []


def test_frontend_design_guidelines_count_as_expert_methodology():
    spec = SkillSpec(name="Frontend Design", content=FRONTEND_DESIGN_CONTENT)

    report = build_skill_knowledge_contract(spec)

    assert report["has_role_definition"] is True
    assert report["has_expert_methodology"] is True
    assert report["has_decision_criteria"] is True
    assert report["has_validation_guidance"] is True
    assert report["has_pitfalls"] is True
    assert "missing_expert_methodology" not in {warning["code"] for warning in report["warnings"]}


def test_never_avoid_and_antipatterns_detect_pitfalls():
    spec = SkillSpec(
        name="Design Pitfalls",
        content="""
        ## Frontend Aesthetics Guidelines
        Use typography, contrast, spacing, and visual hierarchy intentionally.
        NEVER rely on generic gradients. Avoid inconsistent spacing and
        anti-patterns such as motion without purpose or low contrast controls.
        """,
    )

    report = build_skill_knowledge_contract(spec)

    assert report["has_pitfalls"] is True


def test_critical_important_quality_wording_detects_validation_guidance():
    spec = SkillSpec(
        name="Quality Guidance",
        content="""
        ## Frontend Aesthetics Guidelines
        Use design thinking, typography, color, motion, spatial composition,
        backgrounds, and product constraints to guide implementation.
        CRITICAL: quality review must check hierarchy, contrast, accessibility,
        and whether the interface supports the intended tone.
        IMPORTANT: validate visual consistency before finalizing.
        """,
    )

    report = build_skill_knowledge_contract(spec)

    assert report["has_validation_guidance"] is True


def test_required_tools_do_not_convert_skill_into_action():
    spec = SkillSpec(
        name="Frontend Reviewer",
        content=EXPERT_CONTENT,
        required_tools=["Read", "Grep"],
        required_mcp_servers=["Design System MCP"],
    )

    report = build_skill_knowledge_contract(spec)

    assert report["contract_kind"] == "skill_knowledge_contract"
    assert report["has_action_boundary_statement"] is True
    assert "missing_declarative_tool_boundary" not in {warning["code"] for warning in report["warnings"]}


def test_action_boundary_statement_is_detected_when_present():
    spec = SkillSpec(
        name="Portable Expert",
        content="## Boundaries\nThis skill is not an Action and does not grant permissions or activate tools/MCP.",
    )

    report = build_skill_knowledge_contract(spec)

    assert report["has_action_boundary_statement"] is True


def test_knowledge_contract_helper_does_not_modify_candidate():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="Senior Frontend", content=EXPERT_CONTENT, required_tools=["Read"]),
        status="candidate",
    )
    before = deepcopy(candidate.model_dump(mode="json"))

    build_skill_knowledge_contract(candidate.skill_spec)

    assert candidate.model_dump(mode="json") == before


def test_candidate_validation_adds_non_blocking_knowledge_warning():
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="Generic", content="Help with tasks using best practices."),
        source="skill_builder",
    )

    validated = apply_skill_candidate_validation(candidate)

    assert validated.status == "validated"
    assert validated.validation_errors == []
    assert validated.install_approved is False
    assert any(warning["code"] == "skill_knowledge_contract" for warning in validated.warnings)
    assert candidate.warnings == []
