import pytest

from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntime, MiniAgentRuntimeContext
from backend.apps.agents.runtime.provider_turn_harness import FakeProviderAdapter


@pytest.mark.asyncio
async def test_mini_agent_runtime_passes_system_prompt_to_provider(tmp_path):
    provider = FakeProviderAdapter([{"final": "done"}])
    runtime = MiniAgentRuntime()
    contract = AgentContract(
        role="DocumentationAgent",
        objective="Write project documentation.",
        allowed_tools=[],
        acceptance_criteria=["Return evidence."],
        output_contract={"summary": "string"},
    )
    task = TaskNode(
        title="Document result",
        objective="Summarize the result with evidence.",
        assigned_contract_id=contract.id,
    )

    result = await runtime.run_agent_task(
        MiniAgentRuntimeContext(
            contract=contract,
            task=task,
            provider=provider,
            workspace_path=str(tmp_path),
            model="fake",
            inputs={"instruction": "Read README.md"},
            max_turns=1,
        )
    )

    assert result.status == "completed"
    assert provider.calls
    system_prompt = provider.calls[0].system_prompt or ""
    assert "openswarm_system_prompt" in system_prompt
    assert "mini_agent_task_context" in system_prompt
    assert "mini_agent_tool_policy_context" in system_prompt
    assert "mini_agent_evidence_contract" in system_prompt
    assert "el modelo razona, pero no inventa estado" in system_prompt.lower()
    assert "DocumentationAgent" in system_prompt
    assert "Read README.md" in system_prompt


@pytest.mark.asyncio
async def test_mini_agent_runtime_keeps_user_task_message_unchanged(tmp_path):
    provider = FakeProviderAdapter([{"final": "done"}])
    runtime = MiniAgentRuntime()
    contract = AgentContract(
        role="ReviewerAgent",
        objective="Review evidence.",
        allowed_tools=[],
        acceptance_criteria=["Do not invent results."],
        output_contract={"review": "string"},
    )
    task = TaskNode(
        title="Review output",
        objective="Review available output only.",
        assigned_contract_id=contract.id,
    )

    await runtime.run_agent_task(
        MiniAgentRuntimeContext(
            contract=contract,
            task=task,
            provider=provider,
            workspace_path=str(tmp_path),
            model="fake",
            max_turns=1,
        )
    )

    message = provider.calls[0].messages[0]
    assert message["role"] == "user"
    assert "Role: ReviewerAgent" in message["content"]
    assert "Task: Review output" in message["content"]
    assert "Use tools only when needed" in message["content"]
