from backend.apps.swarms.shell_dialect_runtime import (
    build_shell_dialect_capability,
    build_shell_profile,
    build_shell_profile_trace_source,
    build_structured_shell_command,
    detect_shell_profile_from_environment,
    dump_shell_dialect,
    infer_shell_id,
)


def test_git_bash_profile_supports_posix_and_blocks_execution():
    profile = build_shell_profile(shell_id="git_bash", executable_hint="/usr/bin/bash")
    assert profile.shell_id == "git_bash"
    assert profile.shell_family == "posix"
    assert profile.can_execute is False
    assert profile.detection_executed_process is False
    assert profile.capability["supports_posix_tools"] is True
    assert profile.capability["supports_powershell_cmdlets"] is False


def test_powershell_5_profile_blocks_bash_and_operator():
    profile = build_shell_profile(shell_id="powershell_5", shell_version="5.1.19041")
    assert profile.shell_id == "powershell_5"
    assert profile.capability["supports_and_operator"] is False
    assert "block_bash_and_operator" in profile.required_actions
    assert any("&&" in note for note in profile.risk_notes)


def test_powershell_7_profile_supports_and_operator_but_requires_posix_availability_check():
    profile = build_shell_profile(shell_id="pwsh", shell_version="7.4.0")
    assert profile.shell_id == "powershell_7"
    assert profile.capability["supports_and_operator"] is True
    assert "translate_posix_tools_or_check_availability" in profile.required_actions


def test_cmd_profile_uses_cmd_quoting_and_windows_paths():
    profile = build_shell_profile(shell_id="cmd")
    assert profile.shell_id == "cmd"
    assert profile.capability["quoting_style"] == "cmd"
    assert profile.capability["supports_windows_paths"] is True
    assert profile.capability["supports_posix_tools"] is False


def test_wsl_profile_requires_windows_path_translation():
    profile = build_shell_profile(shell_id="wsl")
    assert profile.shell_id == "wsl"
    assert profile.capability["path_style"] == "posix"
    assert "translate_windows_paths_for_wsl" in profile.required_actions


def test_python_subprocess_profile_requires_structured_argv():
    capability = build_shell_dialect_capability("python_subprocess")
    assert capability.supports_structured_args is True
    assert capability.supports_and_operator is False
    assert "represent_command_as_argv" in capability.required_actions


def test_unknown_shell_profile_stays_blocked():
    profile = build_shell_profile(shell_id="unknown")
    assert profile.shell_id == "unknown"
    assert profile.risk_level == "high"
    assert profile.can_execute is False
    assert "select_shell_profile_before_execution" in profile.required_actions


def test_infer_shell_id_from_environment_hints():
    assert infer_shell_id(env={"SHELL": "/usr/bin/bash", "MSYSTEM": "MINGW64"}) == "git_bash"
    assert infer_shell_id(env={"COMSPEC": "C:\\Windows\\System32\\cmd.exe"}) == "cmd"
    assert infer_shell_id(env={"WSL_DISTRO_NAME": "Ubuntu"}) == "wsl"
    assert infer_shell_id(executable_hint="pwsh", shell_version="7.4.0") == "powershell_7"


def test_detect_shell_profile_from_environment_does_not_execute_process():
    profile = detect_shell_profile_from_environment({"SHELL": "/usr/bin/bash", "MSYSTEM": "MINGW64"})
    assert profile.shell_id == "git_bash"
    assert profile.source == "environment"
    assert profile.detection_executed_process is False
    assert profile.can_execute is False


def test_shell_profile_metadata_is_redacted():
    profile = build_shell_profile(
        shell_id="git_bash",
        metadata={"api_key": "secret-value", "safe": "visible"},
    )
    dumped = dump_shell_dialect(profile)
    assert dumped["metadata"]["api_key"] == "[redacted]"
    assert dumped["metadata"]["safe"] == "visible"


def test_shell_profile_trace_source_is_safe_and_non_executable():
    profile = build_shell_profile(shell_id="powershell_5")
    trace = build_shell_profile_trace_source(profile)
    assert trace["source_kind"] == "shell_dialect_runtime"
    assert trace["trace_source_kind"] == "shell_dialect_runtime"
    assert trace["shell_id"] == "powershell_5"
    assert trace["can_execute"] is False
    assert trace["detection_executed_process"] is False
    assert "block_bash_and_operator" in trace["required_actions"]


def test_structured_shell_command_contract_is_non_executable():
    profile = build_shell_profile(shell_id="git_bash")
    command = build_structured_shell_command(
        intent="inspect",
        command_name="git",
        args=["status", "--short"],
        working_directory="/workspace/OpenSwarm",
        shell_profile=profile,
    )

    assert command.command_kind == "structured_shell_command"
    assert command.intent == "inspect"
    assert command.shell_id == "git_bash"
    assert command.command_name == "git"
    assert command.argv == ["git", "status", "--short"]
    assert command.can_execute is False
    assert command.execution_permission_granted is False
    assert command.preflight_required is True
    assert "do_not_execute_shell" in command.required_actions
    assert "require_policy_matrix_approval" in command.required_actions


def test_structured_shell_command_keeps_raw_command_blocked():
    command = build_structured_shell_command(
        intent="run",
        raw_command="git status && npm test",
        shell_id="powershell_5",
    )

    assert command.shell_id == "powershell_5"
    assert command.argv == []
    assert command.can_execute is False
    assert command.risk_level == "high"
    assert "provide_command_name" in command.required_actions
    assert "parse_raw_command_before_execution" in command.required_actions
    assert "select_shell_profile_before_execution" not in command.required_actions


def test_structured_shell_command_redacts_environment_and_metadata():
    command = build_structured_shell_command(
        intent="inspect",
        command_name="echo",
        args=["token=secret-value", "safe"],
        shell_id="git_bash",
        environment={"OPENAI_API_KEY": "secret", "SAFE_ENV": "visible"},
        metadata={"password": "secret", "safe": "visible"},
    )
    dumped = dump_shell_dialect(command)

    assert dumped["argv"][1] == "[redacted]"
    assert dumped["argv"][2] == "safe"
    assert dumped["environment"]["OPENAI_API_KEY"] == "[redacted]"
    assert dumped["environment"]["SAFE_ENV"] == "visible"
    assert dumped["metadata"]["password"] == "[redacted]"
    assert dumped["metadata"]["safe"] == "visible"
