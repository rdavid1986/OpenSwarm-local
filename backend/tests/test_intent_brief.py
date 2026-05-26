from backend.apps.agents.orchestration.models import AgentToAgentMessage, SwarmState
from backend.apps.swarms.intent_brief import (
    build_intent_brief,
    extract_existing_project_context,
    extract_intake_summary,
    extract_known_constraints,
    extract_open_questions,
    extract_user_intent_messages,
)


def test_build_intent_brief_uses_user_prompt_when_no_chat_messages():
    swarm = SwarmState(title="Test", user_prompt="Crear dashboard local con login")

    brief = build_intent_brief(swarm)

    assert brief["kind"] == "intent_brief"
    assert brief["status"] == "ready"
    assert brief["primary_goal"] == "Crear dashboard local con login"
    assert brief["original_user_prompt"] == "Crear dashboard local con login"
    assert brief["research_status"] == "not_requested"
    assert brief["source"] == "loaded_swarm_state"


def test_build_intent_brief_prefers_latest_user_message():
    swarm = SwarmState(title="Test", user_prompt="Crear app")
    brief = build_intent_brief(swarm, user_message="Ahora quiero una web app con auth y dashboard")

    assert brief["primary_goal"] == "Ahora quiero una web app con auth y dashboard"
    assert brief["latest_user_message"] == "Ahora quiero una web app con auth y dashboard"


def test_extract_user_intent_messages_from_loaded_swarm_messages():
    swarm = SwarmState(title="Test", user_prompt="Crear app")
    swarm.messages.append(
        AgentToAgentMessage(
            type="chat_message",
            from_agent_id="user",
            payload={"content": "Quiero auth con roles"},
        )
    )
    swarm.messages.append(
        AgentToAgentMessage(
            type="chat_message",
            from_agent_id="assistant",
            payload={"content": "Entendido"},
        )
    )

    assert extract_user_intent_messages(swarm) == ["Quiero auth con roles"]


def test_extract_intake_summary_does_not_invent_missing_answers():
    swarm = SwarmState(title="Test", user_prompt="Crear app")
    swarm.project_intake_state = {
        "status": "ready_to_implement",
        "intake_mode": "model_assisted",
        "answers": {"app_type": "Dashboard"},
        "generated_plan": {
            "main_goal": "Crear dashboard",
            "frontend": "React",
            "backend": "FastAPI",
        },
    }

    summary = extract_intake_summary(swarm)

    assert summary["status"] == "ready_to_implement"
    assert summary["intake_mode"] == "model_assisted"
    assert summary["answers_keys"] == ["app_type"]
    assert summary["generated_plan"]["backend"] == "FastAPI"


def test_extract_known_constraints_from_generated_plan():
    swarm = SwarmState(title="Test", user_prompt="Crear app")
    swarm.project_intake_state = {
        "generated_plan": {
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "out_of_scope": "Pagos",
            "constraints": ["Local-first"],
        }
    }

    constraints = extract_known_constraints(swarm)

    assert "Local-first" in constraints
    assert "backend: FastAPI" in constraints
    assert "database: PostgreSQL" in constraints
    assert "out_of_scope: Pagos" in constraints


def test_extract_existing_project_context_counts_loaded_state():
    swarm = SwarmState(title="Test", user_prompt="Crear app")
    swarm.output_bridge = {"output_id": "output-1"}
    swarm.final_result = {"status": "completed", "route": "implementation"}
    swarm.artifacts.append({"id": "artifact-1"})
    swarm.final_evidence.append({"id": "evidence-1"})
    swarm.decisions.append({"kind": "test"})

    context = extract_existing_project_context(swarm)

    assert context["has_final_result"] is True
    assert context["final_result_status"] == "completed"
    assert context["final_result_route"] == "implementation"
    assert context["has_output_bridge"] is True
    assert context["output_id"] == "output-1"
    assert context["artifacts_count"] == 1
    assert context["final_evidence_count"] == 1
    assert context["decisions_count"] == 1


def test_extract_open_questions_from_context_clarification_and_intake():
    swarm = SwarmState(title="Test", user_prompt="Crear app")
    swarm.project_intake_state = {"current_question_id": "backend"}
    swarm.final_result = {
        "context_clarification": {
            "clarification_question": "¿Qué tipo de app querés crear?"
        }
    }

    questions = extract_open_questions(swarm)

    assert "current_question_id: backend" in questions
    assert "¿Qué tipo de app querés crear?" in questions
