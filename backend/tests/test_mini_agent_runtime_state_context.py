import pytest

from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntime, MiniAgentRuntimeContext
from backend.apps.agents.runtime.provider_turn_harness import FakeProviderAdapter


@pytest.mark.asyncio
async def test_mini_agent_runtime_passes_runtime_state_to_provider(tmp_path):
    provider = FakeProviderAdapter([{"final": "done"}])
    runtime = MiniAgentRuntime()
    contract = AgentContract(
        role="FrontendAgent",
        objective="Build UI.",
        allowed_tools=["Read", "Write"],
        acceptance_criteria=["Return evidence.", "Stay scoped."],
        output_contract={"ui_result": "string"},
    )
    task = TaskNode(
        title="Build header",
        objective="Create a scoped header component.",
        task_type="frontend_plan_execute",
        assigned_contract_id=contract.id,
    )

    result = await runtime.run_agent_task(
        MiniAgentRuntimeContext(
            contract=contract,
            task=task,
            provider=provider,
            workspace_path=str(tmp_path),
            model="fake",
            swarm_id="swarm-123",
            inputs={"instruction": "Use the current design system.", "extra": "value"},
            max_turns=1,
        )
    )

    assert result.status == "completed"
    runtime_state = provider.calls[0].runtime_state
    assert runtime_state["runtime"] == "mini_agent_runtime"
    assert runtime_state["task_id"] == task.id
    assert runtime_state["task_type"] == "frontend_plan_execute"
    assert runtime_state["task_title"] == "Build header"
    assert runtime_state["agent_contract_id"] == contract.id
    assert runtime_state["agent_role"] == "FrontendAgent"
    assert runtime_state["assigned_contract_id"] == contract.id
    assert runtime_state["allowed_tools"] == ["Read", "Write"]
    assert runtime_state["workspace_path"] == str(tmp_path)
    assert runtime_state["swarm_id"] == "swarm-123"
    assert runtime_state["acceptance_criteria"] == ["Return evidence.", "Stay scoped."]
    assert runtime_state["output_contract"] == {"ui_result": "string"}
    assert runtime_state["inputs_keys"] == ["extra", "instruction"]
    assert runtime_state["provider_tool_format"] == "ollama"


@pytest.mark.asyncio
async def test_mini_agent_runtime_keeps_security_metadata_separate_from_runtime_state(tmp_path):
    provider = FakeProviderAdapter([{"final": "done"}])
    runtime = MiniAgentRuntime()
    contract = AgentContract(
        role="ReviewerAgent",
        objective="Review only.",
        allowed_tools=["Read"],
        acceptance_criteria=["Do not invent results."],
        output_contract={"review": "string"},
    )
    task = TaskNode(
        title="Review output",
        objective="Review available output.",
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

    call = provider.calls[0]
    assert call.runtime_state["allowed_tools"] == ["Read"]
    assert call.metadata["allowed_tools"] == ["Read"]
    assert call.metadata["agent_contract_allowed_tools"] == ["Read"]
    assert call.metadata["provider_tool_format"] == "ollama"
