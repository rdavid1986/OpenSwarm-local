import pytest

from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntime, MiniAgentRuntimeContext
from backend.apps.agents.runtime.provider_turn_harness import FakeProviderAdapter


@pytest.mark.asyncio
async def test_mini_agent_runtime_evidence_distinguishes_work_states(tmp_path):
    provider = FakeProviderAdapter([{"final": "done"}])
    runtime = MiniAgentRuntime()
    contract = AgentContract(
        role="DocumentationAgent",
        objective="Write documentation.",
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
            max_turns=1,
        )
    )

    assert result.status == "completed"
    runtime_evidence = result.evidence[0]
    assert runtime_evidence["kind"] == "mini_agent_runtime"
    assert runtime_evidence["evidence_contract_version"] == "mini_agent_runtime.v1"
    assert runtime_evidence["planned_work"]["task_id"] == task.id
    assert runtime_evidence["planned_work"]["agent_role"] == "DocumentationAgent"
    assert runtime_evidence["attempted_work"]["turns"] == 1
    assert runtime_evidence["completed_work"]["final_message_available"] is True
    assert runtime_evidence["failed_work"]["errors"] == []
    assert runtime_evidence["tool_count"] == 0
    assert runtime_evidence["error_count"] == 0


@pytest.mark.asyncio
async def test_mini_agent_runtime_evidence_records_provider_failure(tmp_path):
    provider = FakeProviderAdapter([{"error": "provider failed"}])
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

    result = await runtime.run_agent_task(
        MiniAgentRuntimeContext(
            contract=contract,
            task=task,
            provider=provider,
            workspace_path=str(tmp_path),
            model="fake",
            max_turns=1,
        )
    )

    assert result.status == "failed"
    runtime_evidence = result.evidence[0]
    assert runtime_evidence["status"] == "failed"
    assert runtime_evidence["has_final_message"] is False
    assert runtime_evidence["completed_work"]["final_message_available"] is False
    assert runtime_evidence["failed_work"]["errors"]
    assert runtime_evidence["error_count"] >= 1
