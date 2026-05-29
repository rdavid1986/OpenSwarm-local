from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.skills import skills as skills_module
from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate
from backend.apps.skills.skill_reviewer import review_skill_candidate


EXPERT_CONTENT = """
# Senior Backend Reviewer

## Role and scope
Act as a senior backend expert. Focus on correctness, API contracts, data
integrity, observability, performance, and maintainability.

## Expert methodology
Read the relevant model, route, store, and tests before recommending changes.
Trace data flow and side effects, then prefer the smallest safe implementation.

## Decision criteria
Prefer explicit contracts over implicit behavior. Choose simple transactional
flows when consistency matters. Trade flexibility against auditability.

## Execution guidance
Preserve public APIs unless the user requests a breaking change. Keep errors
deterministic and JSON-safe.

## Validation
Run focused tests for the route, helper, and failure path. Verify no persistence
changes happen in read-only flows.

## Pitfalls
Avoid hidden writes, broad refactors, permission changes, and conflating
validation warnings with install approval.

## Boundaries
This skill is expert knowledge, not an Action. It does not grant permissions,
activate tools/MCP, or execute external operations. required_tools and
required_mcp_servers are declarative requirements only.

## Examples
Example: for a read-only reviewer, compare the candidate before and after review.
"""

FRONTEND_DESIGN_CONTENT = """
# Frontend Design

## Design Thinking
Start with product intent, audience, tone, constraints, and differentiation.
Before coding, identify what the interface should make the user feel and do.
Use a clear approach: define purpose, hierarchy, and visual rhythm.

## Frontend Aesthetics Guidelines
Focus on typography, color & theme, motion, spatial composition, responsive
layout, backgrounds, contrast, and visual details.

## Decision criteria
Choose typography based on density and tone. Trade decoration against clarity.
Use constraints to decide whether motion should guide attention or stay quiet.

## Quality bar
CRITICAL: review hierarchy, accessibility, contrast, empty states, and whether
the visual system supports the product intent.

## Anti-patterns
NEVER ship generic aesthetics. Avoid random gradients, inconsistent spacing,
low contrast, and motion that distracts from the task.

## Scope
This guidance covers frontend visual design and implementation choices.
"""


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(skills_module, "skill_candidate_store", SkillCandidateStore(root=tmp_path / "skill_candidates"))
    monkeypatch.setattr(skills_module, "SKILLS_DIR", str(tmp_path / "legacy_skills"))
    monkeypatch.setattr(skills_module, "INDEX_PATH", str(tmp_path / "legacy_skills" / ".skills_index.json"))
    app = FastAPI()
    app.include_router(skills_module.skills.router, prefix="/api/skills")
    return TestClient(app)


def _candidate(content: str, **spec_updates) -> SkillSpecCandidate:
    return SkillSpecCandidate(
        skill_spec=SkillSpec(name="Review Me", content=content, **spec_updates),
        status="validated",
        install_approved=False,
    )


def test_generic_candidate_produces_improvement_items():
    candidate = _candidate("Help with tasks using best practices.")

    review = review_skill_candidate(candidate)

    codes = {item["code"] for item in review["improvement_items"]}
    assert review["review_kind"] == "skill_quality_review"
    assert review["safe_to_auto_apply"] is False
    assert "add_expert_role" in codes
    assert "add_methodology" in codes
    assert "clarify_skill_not_action" in codes
    assert review["quality_contract"]["contract_kind"] == "skill_knowledge_contract"
    assert review["human_summary"]
    assert review["human_next_steps"]


def test_expert_candidate_produces_fewer_improvement_items():
    generic = review_skill_candidate(_candidate("Help with tasks using best practices."))
    expert = review_skill_candidate(_candidate(EXPERT_CONTENT))

    assert len(expert["improvement_items"]) < len(generic["improvement_items"])
    assert expert["quality_contract"]["has_expert_methodology"] is True
    assert expert["quality_contract"]["has_action_boundary_statement"] is True


def test_frontend_design_style_skill_does_not_miss_methodology():
    review = review_skill_candidate(_candidate(FRONTEND_DESIGN_CONTENT))

    codes = {item["code"] for item in review["improvement_items"]}
    assert review["quality_contract"]["has_expert_methodology"] is True
    assert review["quality_contract"]["has_pitfalls"] is True
    assert review["quality_contract"]["has_validation_guidance"] is True
    assert "add_methodology" not in codes
    assert "clarify_skill_not_action" in codes
    assert review["safe_to_auto_apply"] is False
    assert review["human_summary"]
    assert review["human_strengths"]
    assert review["human_missing_items"]


def test_review_never_modifies_candidate():
    candidate = _candidate("Help with tasks using best practices.", required_tools=["Read"])
    before = deepcopy(candidate.model_dump(mode="json"))

    review_skill_candidate(candidate)

    assert candidate.model_dump(mode="json") == before


def test_review_is_never_safe_to_auto_apply_and_preserves_install_approval_status():
    candidate = _candidate(EXPERT_CONTENT)
    candidate.install_approved = True

    review = review_skill_candidate(candidate)

    assert review["safe_to_auto_apply"] is False
    assert review["install_approved"] is True
    assert candidate.install_approved is True


def test_required_tools_and_mcp_without_boundary_are_declared_as_declarative_gap():
    candidate = _candidate(
        """
        # Reddit Analyst
        ## Role
        Act as a senior analyst.
        """,
        required_tools=["Read"],
        required_mcp_servers=["Reddit MCP"],
    )

    review = review_skill_candidate(candidate)

    codes = {item["code"] for item in review["improvement_items"]}
    assert "clarify_required_tools_are_declarative" in codes
    assert review["action_boundary_status"] == "requirements_declared_boundary_missing"


def test_quality_review_endpoint_returns_review_without_mutating_candidate(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    payload = {
        "skill_spec": {
            "name": "Generic Reviewer",
            "content": "Help with tasks using best practices.",
            "source_format": "unknown",
            "metadata_confidence": "unknown",
        },
        "source": "skill_builder",
    }
    created = client.post("/api/skills/candidates/create", json=payload)
    assert created.status_code == 200
    candidate_id = created.json()["candidate"]["candidate_id"]
    before = client.get(f"/api/skills/candidates/{candidate_id}").json()

    response = client.get(f"/api/skills/candidates/{candidate_id}/quality-review")

    assert response.status_code == 200
    review = response.json()
    assert review["review_kind"] == "skill_quality_review"
    assert review["candidate_id"] == candidate_id
    assert review["safe_to_auto_apply"] is False
    assert review["quality_contract"]["contract_kind"] == "skill_knowledge_contract"
    assert review["install_approved"] is False

    after = client.get(f"/api/skills/candidates/{candidate_id}").json()
    assert after == before


def test_quality_review_endpoint_missing_candidate_returns_404(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.get("/api/skills/candidates/missing/quality-review")

    assert response.status_code == 404
    assert response.json()["detail"] == "Skill candidate not found"
