from backend.apps.agents.runtime import PolicyRuntime, ToolRuntime


def test_policy_runtime_allows_known_builtin_by_default():
    policy = PolicyRuntime(ToolRuntime())
    decision = policy.decide_tool_use("Read")

    assert decision.decision in ("allow", "ask")
    assert decision.denied is False


def test_policy_runtime_denies_unknown_tool():
    policy = PolicyRuntime(ToolRuntime())
    decision = policy.decide_tool_use("DefinitelyNotATool")

    assert decision.denied is True


def test_policy_runtime_denies_paths_outside_workspace(tmp_path):
    policy = PolicyRuntime(ToolRuntime())

    assert policy.validate_workspace_path(str(tmp_path), "../outside.txt").denied is True
    assert policy.validate_workspace_path(str(tmp_path), "inside.txt").allowed_without_human is True


def test_policy_runtime_command_guards():
    policy = PolicyRuntime(ToolRuntime())

    assert policy.validate_command("git status").allowed_without_human is True
    assert policy.validate_command("rm -rf .").denied is True
    assert policy.validate_command("python script.py").requires_approval is True
