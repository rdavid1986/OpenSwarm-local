from backend.apps.agents.runtime.policies import PolicyRuntime
from backend.apps.agents.runtime.tools import ToolResolution, ToolSpec


class DummyContext:
    def __init__(self, metadata: dict | None = None, require_human_approval: bool = False, allowed_tools=None):
        self.metadata = metadata or {}
        self.require_human_approval = require_human_approval
        self.allowed_tools = allowed_tools
        self.workspace_path = "."
        self.session_id = "session-1"
        self.swarm_id = "swarm-1"
        self.agent_id = "agent-1"
        self.task_id = "task-1"


def _resolution(tool_name: str = "SafeShell") -> ToolResolution:
    return ToolResolution(
        found=True,
        tool=ToolSpec(name=tool_name, kind="builtin", policy="always_allow", raw_name=tool_name),
        reason=None,
    )


def test_side_effect_policy_requires_approval_for_tool_call():
    runtime = PolicyRuntime()
    context = DummyContext(
        metadata={
            "side_effect_policy": {
                "decision": "requires_approval",
                "requires_approval": True,
                "blocked": False,
            }
        }
    )

    decision = runtime.evaluate_tool_call(
        resolution=_resolution(),
        context=context,
        requested_tool_name="SafeShell",
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.status == "approval_required"
    assert "side effect policy requires approval" in (decision.reason or "")


def test_side_effect_policy_blocks_tool_call():
    runtime = PolicyRuntime()
    context = DummyContext(
        metadata={
            "side_effect_policy": {
                "decision": "blocked",
                "requires_approval": False,
                "blocked": True,
            }
        }
    )

    decision = runtime.evaluate_tool_call(
        resolution=_resolution(),
        context=context,
        requested_tool_name="Write",
    )

    assert decision.allowed is False
    assert decision.requires_approval is False
    assert decision.status == "denied"
    assert "side effect policy blocks this tool call" in (decision.reason or "")
