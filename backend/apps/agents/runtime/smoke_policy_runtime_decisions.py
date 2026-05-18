"""Smoke unitario del PolicyRuntime sin depender de permisos reales."""

from __future__ import annotations

import json
from dataclasses import dataclass

from backend.apps.agents.runtime.policies import PolicyRuntime


@dataclass(frozen=True)
class FakeToolSpec:
    name: str
    raw_name: str | None = None
    policy: str = "always_allow"


@dataclass(frozen=True)
class FakeResolution:
    found: bool
    tool: FakeToolSpec | None = None
    reason: str | None = None


@dataclass(frozen=True)
class FakeContext:
    allowed_tools: list[str] | None = None
    require_human_approval: bool = False
    metadata: dict | None = None


def main() -> int:
    policies = PolicyRuntime()

    unknown = policies.evaluate_tool_call(
        resolution=FakeResolution(found=False, reason="unknown tool: X"),
        context=FakeContext(allowed_tools=["Read"]),
        requested_tool_name="X",
    )

    denied_by_allowed_tools = policies.evaluate_tool_call(
        resolution=FakeResolution(found=True, tool=FakeToolSpec(name="Write")),
        context=FakeContext(allowed_tools=["Read"]),
        requested_tool_name="Write",
    )

    denied_by_task_type_registry = policies.evaluate_tool_call(
        resolution=FakeResolution(found=True, tool=FakeToolSpec(name="Write")),
        context=FakeContext(
            allowed_tools=["Read", "Write"],
            metadata={
                "task_type": "inspect_readme",
                "task_type_allowed_tools": ["Read"],
                "agent_contract_allowed_tools": ["Read", "Write"],
            },
        ),
        requested_tool_name="Write",
    )

    denied_by_agent_contract = policies.evaluate_tool_call(
        resolution=FakeResolution(found=True, tool=FakeToolSpec(name="Write")),
        context=FakeContext(
            allowed_tools=["Read", "Write"],
            metadata={
                "task_type": "create_readme",
                "task_type_allowed_tools": ["Read", "Write"],
                "agent_contract_allowed_tools": ["Read"],
            },
        ),
        requested_tool_name="Write",
    )

    denied_by_policy = policies.evaluate_tool_call(
        resolution=FakeResolution(found=True, tool=FakeToolSpec(name="Delete", policy="deny")),
        context=FakeContext(allowed_tools=["Delete"]),
        requested_tool_name="Delete",
    )

    approval_required = policies.evaluate_tool_call(
        resolution=FakeResolution(found=True, tool=FakeToolSpec(name="DangerousTool", policy="ask")),
        context=FakeContext(allowed_tools=["DangerousTool"], require_human_approval=True),
        requested_tool_name="DangerousTool",
    )

    allowed = policies.evaluate_tool_call(
        resolution=FakeResolution(found=True, tool=FakeToolSpec(name="Read", policy="always_allow")),
        context=FakeContext(allowed_tools=["Read"], require_human_approval=True),
        requested_tool_name="Read",
    )

    result = {
        "ok": (
            unknown.status == "denied"
            and denied_by_allowed_tools.status == "denied"
            and denied_by_task_type_registry.status == "denied"
            and denied_by_agent_contract.status == "denied"
            and denied_by_policy.status == "denied"
            and approval_required.status == "approval_required"
            and allowed.status == "allowed"
        ),
        "unknown": unknown.__dict__,
        "denied_by_allowed_tools": denied_by_allowed_tools.__dict__,
        "denied_by_task_type_registry": denied_by_task_type_registry.__dict__,
        "denied_by_agent_contract": denied_by_agent_contract.__dict__,
        "denied_by_policy": denied_by_policy.__dict__,
        "approval_required": approval_required.__dict__,
        "allowed": allowed.__dict__,
    }

    print("########## COPIAR DESDE AQUÍ ##########")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
