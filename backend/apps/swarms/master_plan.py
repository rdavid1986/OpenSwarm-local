"""Master Plan builders for Senior Swarm Team orchestration.

SST.2 keeps this module side-effect free. It does not call providers, fetch web
research, mutate SwarmState, persist data, execute tools, create agents, or
authorize actions. It only builds the contract/prompt shape for a future Master
Planner that will reason from IntentBrief + Project Memory + Research state.
"""

from __future__ import annotations

import json
from typing import Any

from backend.apps.swarms.model_response_contract import build_model_response_contract_prompt
from backend.apps.swarms.state_context import build_state_context_payload, build_state_context_prompt
from backend.apps.swarms.system_prompt import build_openswarm_system_prompt


MASTER_PLAN_ALLOWED_DOMAINS = [
    "architecture",
    "frontend",
    "backend",
    "database",
    "auth",
    "security",
    "testing",
    "ui_ux",
    "documentation",
    "devops",
    "desktop",
    "mobile",
    "game",
    "unity",
    "blender",
    "automation",
    "skill_builder",
    "research",
    "integration",
    "review",
]

MASTER_PLAN_REQUIRED_TOP_LEVEL_KEYS = [
    "kind",
    "status",
    "summary",
    "primary_goal",
    "assumptions",
    "constraints",
    "required_domains",
    "domain_planners",
    "miniagent_strategy",
    "skill_strategy",
    "research_strategy",
    "integration_strategy",
    "validation_strategy",
    "risks",
    "open_questions",
    "confidence",
    "reason",
]


def _as_text(value: Any, *, max_chars: int = 1200) -> str:
    return str(value or "").strip()[:max_chars]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json")
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    return {}


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def build_master_plan_expected_shape() -> dict[str, Any]:
    """Return the expected Master Plan JSON contract."""

    return {
        "kind": "master_plan",
        "status": "ready | needs_clarification | needs_research | blocked",
        "summary": "short grounded project summary",
        "primary_goal": "goal from intent_brief or user request",
        "assumptions": ["explicit assumptions, only when unavoidable"],
        "constraints": ["known constraints from intent_brief, intake, memory or user"],
        "required_domains": [
            {
                "domain": "one of allowed domains",
                "reason": "why this domain is needed",
                "complexity": "low | medium | high",
                "needs_domain_planner": True,
            }
        ],
        "domain_planners": [
            {
                "planner_id": "stable short id",
                "domain": "frontend | backend | ui_ux | etc",
                "objective": "domain-specific planning objective",
                "inputs_needed": ["required inputs"],
                "outputs_expected": ["expected planning outputs"],
                "depends_on": ["planner_id"],
            }
        ],
        "miniagent_strategy": {
            "estimated_miniagents": 0,
            "reason": "why this amount/split is appropriate",
            "suggested_roles": [
                {
                    "role": "FrontendAgent | BackendAgent | TesterAgent | etc",
                    "domain": "domain",
                    "objective": "small scoped objective",
                    "context_scope": "what this miniagent should receive",
                }
            ],
        },
        "skill_strategy": {
            "required_skills": [
                {
                    "skill_id": "candidate skill id",
                    "domain": "domain",
                    "status": "available | missing | unknown",
                    "reason": "why this skill is needed",
                    "requires_skill_builder": False,
                }
            ],
            "missing_skill_handoffs": [
                {
                    "skill_id": "missing skill id",
                    "domain": "domain",
                    "research_needed": ["official docs or best practices needed"],
                    "validation_needed": ["checks before use"],
                }
            ],
        },
        "research_strategy": {
            "needs_web_research": False,
            "research_questions": ["specific external questions"],
            "preferred_sources": ["official docs", "standards", "package docs"],
            "reason": "why research is or is not needed",
        },
        "integration_strategy": {
            "integrator_needed": True,
            "assembly_order": ["domain output integration order"],
            "handoff_contract": ["what each domain must provide to integrator"],
        },
        "validation_strategy": {
            "reviewers": ["ReviewerAgent", "TesterAgent", "SecurityAgent"],
            "checks": ["validation checks grounded in deliverable"],
            "acceptance_criteria": ["criteria for final output"],
        },
        "risks": ["known risks"],
        "open_questions": ["minimal questions that block safe planning"],
        "confidence": 0.0,
        "reason": "short grounded reason",
    }


def build_master_plan_contract_prompt() -> str:
    """Build the Master Plan output contract prompt."""

    return "\n".join(
        [
            "Master Plan contract:",
            "Return one JSON object only.",
            "Do not execute tools, create files, create agents, register skills, or authorize actions.",
            "The Master Plan is a planning artifact before Domain Planners, MiniAgents, Skill Builder, DAG materialization, integration and validation.",
            "Use only state supplied in intent_brief, project_memory, research_state and state_context.",
            "Do not invent available skills, files, outputs, evidence, research results, models, agents or completed work.",
            "If a skill is needed but unavailable, mark it missing and route it to missing_skill_handoffs.",
            "If current information is insufficient, use status=needs_clarification or status=needs_research.",
            "Use required_domains only from this allowed set: " + ", ".join(MASTER_PLAN_ALLOWED_DOMAINS),
            "Required top-level keys: " + ", ".join(MASTER_PLAN_REQUIRED_TOP_LEVEL_KEYS),
            _safe_json(build_master_plan_expected_shape()),
        ]
    )


def build_master_plan_prompt(
    *,
    intent_brief: dict[str, Any],
    project_memory_manifest: dict[str, Any] | None = None,
    research_state: dict[str, Any] | None = None,
    available_skills: list[dict[str, Any]] | None = None,
    model_name: str | None = None,
) -> str:
    """Compose a Master Planner prompt from caller-provided state only."""

    intent = _as_dict(intent_brief)
    memory = _as_dict(project_memory_manifest)
    research = _as_dict(research_state)
    skills = available_skills if isinstance(available_skills, list) else []
    state_context = build_state_context_payload(
        mode="plan",
        route="master_plan",
        user_message=_as_text(intent.get("primary_goal")),
        creation_type=_as_text((intent.get("intake_summary") or {}).get("generated_plan", {}).get("app_type")),
        project_intake_status=_as_text((intent.get("intake_summary") or {}).get("status")),
        model_name=model_name,
        project_memory_manifest=memory if memory else None,
        available_context={
            "intent_brief": intent,
            "research_state": research,
            "available_skill_count": len(skills),
            "available_skills": skills[:24],
        },
    )

    payload = {
        "task": "Create an OpenSwarm Local AI Orchestration Studio Master Plan.",
        "openswarm_system_prompt": build_openswarm_system_prompt(mode="plan", task_kind="master_plan"),
        "state_context": state_context,
        "state_context_prompt": build_state_context_prompt(state_context),
        "model_response_contract_prompt": build_model_response_contract_prompt("master_plan"),
        "master_plan_contract_prompt": build_master_plan_contract_prompt(),
        "intent_brief": intent,
        "project_memory_manifest": memory or None,
        "research_state": research or {"status": "not_requested"},
        "available_skills": skills,
        "rules": [
            "Return JSON only.",
            "Follow openswarm_system_prompt.",
            "Use state_context as the real state snapshot.",
            "Use intent_brief as the main source for user intent.",
            "Use project_memory_manifest only if present.",
            "Use research_state only if present; do not invent web research.",
            "Do not create Domain Planners or MiniAgents here; only propose them.",
            "Do not create or register skills here; only mark missing skills and handoff needs.",
            "Prefer the smallest sufficient number of Domain Planners and MiniAgents.",
            "For simple projects, keep the plan small.",
            "For complex projects, decompose by domain and validation needs.",
        ],
        "expected_json_shape": build_master_plan_expected_shape(),
    }
    return _safe_json(payload)


def normalize_master_plan(model_output: Any) -> dict[str, Any]:
    """Normalize a model-produced Master Plan into a conservative shape."""

    parsed = model_output if isinstance(model_output, dict) else None
    if not parsed and isinstance(model_output, str):
        raw = model_output.strip()
        try:
            parsed = json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(raw[start : end + 1])
                except Exception:
                    parsed = None

    if not isinstance(parsed, dict):
        return {
            "ok": False,
            "source": "fallback",
            "master_plan": build_blocked_master_plan(reason="Model did not return a valid JSON object."),
        }

    plan = dict(parsed)
    if plan.get("kind") != "master_plan":
        plan["kind"] = "master_plan"

    status = _as_text(plan.get("status"), max_chars=80) or "blocked"
    if status not in {"ready", "needs_clarification", "needs_research", "blocked"}:
        status = "blocked"
    plan["status"] = status

    try:
        confidence = float(plan.get("confidence"))
    except Exception:
        confidence = 0.0
    plan["confidence"] = max(0.0, min(confidence, 1.0))

    for key in MASTER_PLAN_REQUIRED_TOP_LEVEL_KEYS:
        plan.setdefault(key, build_master_plan_expected_shape().get(key))

    return {
        "ok": status == "ready" and plan["confidence"] >= 0.7,
        "source": "model",
        "master_plan": plan,
    }


def build_blocked_master_plan(*, reason: str) -> dict[str, Any]:
    """Return a safe blocked Master Plan fallback."""

    shape = build_master_plan_expected_shape()
    shape.update(
        {
            "kind": "master_plan",
            "status": "blocked",
            "summary": "",
            "primary_goal": "",
            "confidence": 0.0,
            "reason": reason,
        }
    )
    return shape
