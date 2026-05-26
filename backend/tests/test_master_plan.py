import pytest

from backend.apps.agents.runtime.provider import ProviderEvent
from backend.apps.swarms.master_plan import (
    MASTER_PLAN_ALLOWED_DOMAINS,
    build_blocked_master_plan,
    build_master_plan_contract_prompt,
    build_master_plan_expected_shape,
    build_master_plan_prompt,
    normalize_master_plan,
    resolve_master_plan,
)


def _intent_brief():
    return {
        "kind": "intent_brief",
        "status": "ready",
        "primary_goal": "Crear dashboard local con auth",
        "original_user_prompt": "Crear app",
        "recent_user_intent_messages": ["Quiero roles admin y usuario"],
        "intake_summary": {
            "status": "ready_to_implement",
            "generated_plan": {
                "app_type": "Dashboard",
                "frontend": "React",
                "backend": "FastAPI",
                "database": "PostgreSQL",
            },
        },
        "known_constraints": ["local-first"],
        "open_questions": [],
    }


def test_master_plan_expected_shape_contains_orchestration_sections():
    shape = build_master_plan_expected_shape()

    assert shape["kind"] == "master_plan"
    assert "required_domains" in shape
    assert "domain_planners" in shape
    assert "miniagent_strategy" in shape
    assert "skill_strategy" in shape
    assert "research_strategy" in shape
    assert "integration_strategy" in shape
    assert "validation_strategy" in shape


def test_master_plan_contract_mentions_missing_skill_handoff():
    prompt = build_master_plan_contract_prompt()

    assert "Master Plan contract" in prompt
    assert "missing_skill_handoffs" in prompt
    assert "Do not execute tools" in prompt
    assert "Use required_domains only from this allowed set" in prompt
    assert "frontend" in MASTER_PLAN_ALLOWED_DOMAINS


def test_build_master_plan_prompt_includes_intent_memory_research_and_skills():
    prompt = build_master_plan_prompt(
        intent_brief=_intent_brief(),
        project_memory_manifest={
            "swarm_id": "swarm-1",
            "current_goal": "Crear dashboard local con auth",
        },
        research_state={
            "status": "not_requested",
        },
        available_skills=[
            {
                "skill_id": "fastapi-auth",
                "description": "FastAPI auth patterns",
                "domains": ["backend", "auth"],
            }
        ],
        model_name="qwen2.5-coder:14b",
    )

    assert "OpenSwarm Local AI Orchestration Studio Master Plan" in prompt
    assert '"route": "master_plan"' in prompt
    assert '"intent_brief": {' in prompt
    assert "Crear dashboard local con auth" in prompt
    assert "fastapi-auth" in prompt
    assert "master_plan_contract_prompt" in prompt
    assert "el modelo razona, pero no inventa estado" in prompt.lower()


def test_normalize_master_plan_accepts_ready_high_confidence_plan():
    result = normalize_master_plan({
        "kind": "master_plan",
        "status": "ready",
        "summary": "Dashboard local",
        "primary_goal": "Crear dashboard",
        "required_domains": [{"domain": "frontend", "reason": "UI", "complexity": "medium", "needs_domain_planner": True}],
        "confidence": 0.82,
    })

    assert result["ok"] is True
    assert result["source"] == "model"
    assert result["master_plan"]["kind"] == "master_plan"
    assert result["master_plan"]["status"] == "ready"
    assert result["master_plan"]["confidence"] == 0.82
    assert "skill_strategy" in result["master_plan"]


def test_normalize_master_plan_blocks_invalid_status():
    result = normalize_master_plan({
        "kind": "master_plan",
        "status": "execute_now",
        "confidence": 0.95,
    })

    assert result["ok"] is False
    assert result["master_plan"]["status"] == "blocked"


def test_build_blocked_master_plan_is_safe_fallback():
    plan = build_blocked_master_plan(reason="missing intent")

    assert plan["kind"] == "master_plan"
    assert plan["status"] == "blocked"
    assert plan["confidence"] == 0.0
    assert plan["reason"] == "missing intent"

class _FakeMasterPlanAdapter:
    def __init__(self, content: str | None = None, *, error: bool = False):
        self.content = content
        self.error = error
        self.calls = []

    async def run_turn(self, context):
        self.calls.append(context)
        if self.error:
            yield ProviderEvent(type="error", payload={"error": "adapter failed"})
            return
        yield ProviderEvent(
            type="message_final",
            payload={
                "message": {
                    "content": self.content
                    or '{"kind":"master_plan","status":"ready","summary":"Dashboard local","primary_goal":"Crear dashboard local con auth","assumptions":[],"constraints":["local-first"],"required_domains":[{"domain":"frontend","reason":"UI","complexity":"medium","needs_domain_planner":true}],"domain_planners":[],"miniagent_strategy":{"estimated_miniagents":2,"reason":"frontend and validation","suggested_roles":[]},"skill_strategy":{"required_skills":[],"missing_skill_handoffs":[]},"research_strategy":{"needs_web_research":false,"research_questions":[],"preferred_sources":[],"reason":"No external docs required"},"integration_strategy":{"integrator_needed":true,"assembly_order":[],"handoff_contract":[]},"validation_strategy":{"reviewers":["TesterAgent"],"checks":["Validate plan"],"acceptance_criteria":["Grounded plan"]},"risks":[],"open_questions":[],"confidence":0.88,"reason":"Enough intent"}'
                }
            },
        )


@pytest.mark.asyncio
async def test_resolve_master_plan_uses_adapter_and_returns_ready_plan():
    adapter = _FakeMasterPlanAdapter()

    result = await resolve_master_plan(
        intent_brief=_intent_brief(),
        available_skills=[{"skill_id": "fastapi-auth", "domains": ["backend", "auth"]}],
        model="fake",
        adapter_factory=lambda: adapter,
    )

    assert result["ok"] is True
    assert result["source"] == "model"
    assert result["master_plan"]["status"] == "ready"
    assert result["master_plan"]["confidence"] == 0.88
    assert adapter.calls
    call = adapter.calls[0]
    assert call.agent_id == "master-plan"
    assert call.model == "fake"
    assert "OpenSwarm Local AI Orchestration Studio Master Plan" in call.messages[0]["content"]
    assert "el modelo razona, pero no inventa estado" in call.system_prompt.lower()


@pytest.mark.asyncio
async def test_resolve_master_plan_falls_back_on_adapter_error():
    adapter = _FakeMasterPlanAdapter(error=True)

    result = await resolve_master_plan(
        intent_brief=_intent_brief(),
        model="fake",
        adapter_factory=lambda: adapter,
    )

    assert result["ok"] is False
    assert result["source"] == "fallback"
    assert result["master_plan"]["status"] == "blocked"
    assert "error" in result["master_plan"]["reason"].lower()


@pytest.mark.asyncio
async def test_resolve_master_plan_falls_back_on_invalid_json():
    adapter = _FakeMasterPlanAdapter(content="not json")

    result = await resolve_master_plan(
        intent_brief=_intent_brief(),
        model="fake",
        adapter_factory=lambda: adapter,
    )

    assert result["ok"] is False
    assert result["source"] == "fallback"
    assert result["master_plan"]["status"] == "blocked"
