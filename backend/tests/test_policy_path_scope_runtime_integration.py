import tempfile
from pathlib import Path

from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, tool_runtime


def _ctx(workspace: Path, *, path_scope: dict | None = None) -> ToolExecutionContext:
    metadata = {
        "policy_scope": "test",
        "task_type": "frontend_implementation_execute",
    }
    if path_scope:
        metadata["path_scope"] = path_scope

    return ToolExecutionContext(
        workspace_path=str(workspace),
        session_id="test-session",
        swarm_id="test-swarm",
        agent_id="test-agent",
        task_id="test-task",
        allowed_tools=["Write", "Edit", "Diff", "Read"],
        metadata=metadata,
    )


def test_write_allowed_inside_path_scope():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-path-scope-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="Write", input={"path": "frontend/src/App.tsx", "content": "export default null\n"}),
        _ctx(
            workspace,
            path_scope={
                "allowed_paths": ["frontend/src"],
                "forbidden_paths": ["backend", "electron"],
            },
        ),
        history=[],
    )

    assert result.ok is True
    assert (workspace / "frontend/src/App.tsx").exists()


def test_write_blocked_outside_path_scope():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-path-scope-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="Write", input={"path": "frontend/package.json", "content": "{}\n"}),
        _ctx(
            workspace,
            path_scope={
                "allowed_paths": ["frontend/src"],
                "forbidden_paths": ["backend", "electron", "frontend/package.json"],
            },
        ),
        history=[],
    )

    assert result.ok is False
    assert result.status == "denied"
    assert "outside allowed scope" in str(result.error)
    assert not (workspace / "frontend/package.json").exists()


def test_diff_blocked_outside_path_scope():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-path-scope-")).resolve()
    target = workspace / "backend/app.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old\n", encoding="utf-8")

    result = tool_runtime.execute_tool(
        ToolCall(name="Diff", input={"path": "backend/app.py", "proposed_content": "new\n"}),
        _ctx(
            workspace,
            path_scope={
                "allowed_paths": ["frontend/src"],
                "forbidden_paths": ["backend"],
            },
        ),
        history=[],
    )

    assert result.ok is False
    assert result.status == "denied"
    assert "outside allowed scope" in str(result.error)


def test_write_without_path_scope_preserves_existing_behavior():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-path-scope-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="Write", input={"path": "README.md", "content": "# OK\n"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is True
    assert (workspace / "README.md").exists()
