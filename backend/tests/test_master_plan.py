from backend.apps.swarms.master_plan import (
    MASTER_PLAN_ALLOWED_DOMAINS,
    build_blocked_master_plan,
    build_master_plan_contract_prompt,
    build_master_plan_expected_shape,
    build_master_plan_prompt,
    normalize_master_plan,
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
