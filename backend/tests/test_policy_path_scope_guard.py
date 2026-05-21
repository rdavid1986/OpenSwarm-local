from backend.apps.agents.runtime.policies import PolicyRuntime


def test_path_scope_allows_paths_inside_allowed_scope():
    assert PolicyRuntime._is_path_allowed_by_scope(
        "frontend/src/App.tsx",
        allowed_paths=["frontend/src"],
        forbidden_paths=["backend", "electron"],
    )


def test_path_scope_blocks_paths_outside_allowed_scope():
    assert not PolicyRuntime._is_path_allowed_by_scope(
        "frontend/package.json",
        allowed_paths=["frontend/src"],
        forbidden_paths=["backend", "electron"],
    )


def test_path_scope_blocks_forbidden_paths_even_if_allowed_parent_matches():
    assert not PolicyRuntime._is_path_allowed_by_scope(
        "backend/apps/agents/runtime/tools.py",
        allowed_paths=["backend/apps"],
        forbidden_paths=["backend/apps/agents/runtime"],
    )


def test_path_scope_blocks_workspace_escape_and_absolute_paths():
    assert not PolicyRuntime._is_path_allowed_by_scope("../outside.py", allowed_paths=["backend"])
    assert not PolicyRuntime._is_path_allowed_by_scope("/tmp/outside.py", allowed_paths=["backend"])
    assert not PolicyRuntime._is_path_allowed_by_scope("C:/Users/rdavi/outside.py", allowed_paths=["backend"])
    assert not PolicyRuntime._is_path_allowed_by_scope("backend/../outside.py", allowed_paths=["backend"])


def test_path_scope_allows_any_non_forbidden_path_when_allowed_paths_empty():
    assert PolicyRuntime._is_path_allowed_by_scope(
        "README.md",
        allowed_paths=[],
        forbidden_paths=["backend"],
    )
    assert not PolicyRuntime._is_path_allowed_by_scope(
        "backend/app.py",
        allowed_paths=[],
        forbidden_paths=["backend"],
    )
