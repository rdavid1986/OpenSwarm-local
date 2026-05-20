import tempfile
from pathlib import Path

from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, tool_runtime
from backend.apps.tools_lib.models import BUILTIN_TOOLS


def _ctx(workspace: Path) -> ToolExecutionContext:
    return ToolExecutionContext(
        workspace_path=str(workspace),
        session_id="test-session",
        swarm_id="test-swarm",
        agent_id="test-agent",
        task_id="test-task",
        allowed_tools=["Diff"],
        metadata={"policy_scope": "test"},
    )


def test_diff_builtin_tool_is_registered():
    names = {tool.name for tool in BUILTIN_TOOLS}
    assert "Diff" in names


def test_diff_tool_returns_unified_diff_without_modifying_file():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-tool-diff-")).resolve()
    target = workspace / "README.md"
    target.write_text("# Old\\n", encoding="utf-8")

    result = tool_runtime.execute_tool(
        ToolCall(name="Diff", input={"path": "README.md", "proposed_content": "# New\\n"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is True
    assert result.status == "completed"
    assert result.result["changed"] is True
    assert result.result["additions"] >= 1
    assert result.result["deletions"] >= 1
    assert "--- a/README.md" in result.result["unified_diff"]
    assert "+++ b/README.md" in result.result["unified_diff"]
    assert target.read_text(encoding="utf-8") == "# Old\\n"


def test_diff_tool_uses_workspace_path_safety():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-tool-diff-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="Diff", input={"path": "../outside.md", "proposed_content": "bad"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is False
    assert result.status == "failed"
