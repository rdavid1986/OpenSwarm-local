from backend.apps.agents.orchestration.models import AgentToAgentMessage
from backend.apps.swarms import swarms as swarms_module
from backend.apps.swarms.context_clarification import resolve_context_clarification


async def _capture_context_clarification(**kwargs):
    _capture_context_clarification.calls.append(kwargs)
    return resolve_context_clarification(
        user_message=kwargs["user_message"],
        swarm_mode=kwargs.get("swarm_mode"),
        intent=kwargs.get("intent"),
        available_context=kwargs.get("available_context"),
    )


_capture_context_clarification.calls = []


def test_context_clarification_receives_intent_brief(monkeypatch, tmp_path):
    _capture_context_clarification.calls = []
    monkeypatch.setattr(swarms_module, "resolve_model_context_clarification", _capture_context_clarification)

    orchestrator = swarms_module.swarm_orchestrator
    original_root = orchestrator.store.root
    orchestrator.store.root = tmp_path
    try:
        swarm = orchestrator.create_swarm(user_prompt="Crear app", dashboard_id="dash-1", intent="chat")
        swarm.messages.append(
            AgentToAgentMessage(
                type="chat_message",
                from_agent_id="user",
                payload={"content": "Quiero un dashboard con auth"},
            )
        )
        orchestrator.store.save(swarm)

        body = swarms_module.ExperimentalChatRequest(
            message="hacelo",
            swarm_mode="app_builder",
            model="fake",
        )

        import anyio

        response = anyio.run(swarms_module.experimental_swarm_chat, swarm.id, body)
    finally:
        orchestrator.store.root = original_root

    assert response["final_result"]["route"] == "context_clarification"
    assert _capture_context_clarification.calls
    available_context = _capture_context_clarification.calls[0]["available_context"]
    intent_brief = available_context["intent_brief"]
    assert intent_brief["kind"] == "intent_brief"
    assert intent_brief["primary_goal"] == "hacelo"
    assert intent_brief["original_user_prompt"] == "Crear app"
    assert "Quiero un dashboard con auth" in intent_brief["recent_user_intent_messages"]
