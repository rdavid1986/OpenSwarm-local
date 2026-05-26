from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.agents.runtime.mini_agent_prompt_context import (
    build_mini_agent_evidence_contract,
    build_mini_agent_system_prompt,
    build_mini_agent_task_context,
    build_mini_agent_tool_policy_context,
)


def _contract() -> AgentContract:
    return AgentContract(
        role="DocumentationAgent",
        objective="Write project documentation.",
        allowed_tools=["Read", "Write"],
        acceptance_criteria=["Return evidence.", "Stay in scope."],
        output_contract={"summary": "string"},
    )


def _task(contract: AgentContract) -> TaskNode:
    return TaskNode(
        title="Document result",
        objective="Summarize the result with evidence.",
        assigned_contract_id=contract.id,
    )


def test_build_mini_agent_task_context_is_scoped_and_json_like():
    contract = _contract()
    task = _task(contract)

    context = build_mini_agent_task_context(
        contract=contract,
        task=task,
        inputs={"instruction": "Read README.md"},
    )

    assert "mini_agent_task_context" in context
    assert "DocumentationAgent" in context
    assert "Document result" in context
    assert '"allowed_tools": [' in context
    assert '"Read"' in context
    assert "Do not use tasks, files, tools, outputs, evidence, or agents not present here" in context


def test_build_mini_agent_tool_policy_context_keeps_runtime_as_authority():
    context = build_mini_agent_tool_policy_context(contract=_contract())

    assert "mini_agent_tool_policy_context" in context
    assert "allowed_tools: Read, Write" in context
    assert "Prompt rules are not security" in context
    assert "runtime policy and tool bridge enforce execution" in context


def test_build_mini_agent_evidence_contract_blocks_invented_results():
    context = build_mini_agent_evidence_contract()

    assert "mini_agent_evidence_contract" in context
    assert "Do not claim tests passed" in context
    assert "runtime state proves it" in context


def test_build_mini_agent_system_prompt_composes_ri_architecture():
    contract = _contract()
    task = _task(contract)
    prompt = build_mini_agent_system_prompt(
        contract=contract,
        task=task,
        inputs={"instruction": "Read README.md"},
    )

    assert "openswarm_system_prompt" in prompt
    assert "mode_prompt" in prompt
    assert "state_grounding_rules" in prompt
    assert "model_response_contract_prompt" in prompt
    assert "mini_agent_task_context" in prompt
    assert "mini_agent_tool_policy_context" in prompt
    assert "mini_agent_evidence_contract" in prompt
    assert "el modelo razona, pero no inventa estado" in prompt.lower()
    assert "DocumentationAgent" in prompt
    assert "Read README.md" in prompt
