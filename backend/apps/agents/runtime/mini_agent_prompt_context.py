"""Prompt/context builders for MiniAgentRuntime.

AG-RI keeps this module side-effect free. It does not execute tools, call
providers, mutate Swarms, persist state, or authorize actions. It only composes
runtime prompt/context text from already-provided AgentContract and TaskNode
state.
"""

from __future__ import annotations

import json
from typing import Any

from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.swarms.model_response_contract import build_model_response_contract_prompt
from backend.apps.swarms.system_prompt import (
    build_mode_prompt,
    build_openswarm_system_prompt,
    build_state_grounding_rules,
)


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def build_mini_agent_task_context(
    *,
    contract: AgentContract,
    task: TaskNode,
    inputs: dict[str, Any] | None = None,
) -> str:
    """Build task-local context for a mini agent."""

    payload = {
        "agent_contract_id": contract.id,
        "agent_role": contract.role,
        "agent_objective": contract.objective,
        "task_id": task.id,
        "task_title": task.title,
        "task_objective": task.objective,
        "allowed_tools": list(contract.allowed_tools or []),
        "acceptance_criteria": list(contract.acceptance_criteria or []),
        "output_contract": dict(contract.output_contract or {}),
        "inputs": dict(inputs or {}),
    }
    return "\n".join(
        [
            "mini_agent_task_context:",
            _safe_json(payload),
            "",
            "Rules:",
            "- This context is the mini agent local scope.",
            "- Do not use tasks, files, tools, outputs, evidence, or agents not present here or in runtime state.",
            "- If required context is missing, report the missing field instead of inventing it.",
        ]
    )


def build_mini_agent_tool_policy_context(*, contract: AgentContract) -> str:
    """Build a concise tool policy context from the contract."""

    allowed_tools = list(contract.allowed_tools or [])
    return "\n".join(
        [
            "mini_agent_tool_policy_context:",
            f"- allowed_tools: {', '.join(allowed_tools) if allowed_tools else 'none'}",
            "- Use only tools exposed by ProviderTurnContext.tools and allowed by runtime metadata.",
            "- Prompt rules are not security; runtime policy and tool bridge enforce execution.",
            "- If a needed tool is missing, explain the missing capability instead of pretending it ran.",
        ]
    )


def build_mini_agent_evidence_contract() -> str:
    """Describe evidence requirements for mini agent final answers."""

    return "\n".join(
        [
            "mini_agent_evidence_contract:",
            "- Distinguish planned work, attempted work, completed work, and failed work.",
            "- Cite only tool results, runtime evidence, touched files, or provider events actually available.",
            "- Do not claim tests passed, files changed, tools executed, or artifacts were produced unless runtime state proves it.",
            "- Final answer must be concise and grounded in actual execution state.",
        ]
    )


def build_mini_agent_system_prompt(
    *,
    contract: AgentContract,
    task: TaskNode,
    inputs: dict[str, Any] | None = None,
) -> str:
    """Compose the MiniAgentRuntime system prompt without side effects."""

    return "\n\n".join(
        [
            "openswarm_system_prompt:\n" + build_openswarm_system_prompt(mode="agent_card", task_kind="mini_agent_runtime"),
            "mode_prompt:\n" + build_mode_prompt("agent_card"),
            "state_grounding_rules:\n" + build_state_grounding_rules(),
            "model_response_contract_prompt:\n" + build_model_response_contract_prompt("mini_agent_runtime"),
            build_mini_agent_task_context(contract=contract, task=task, inputs=inputs),
            build_mini_agent_tool_policy_context(contract=contract),
            build_mini_agent_evidence_contract(),
        ]
    )
