from backend.apps.swarms.shell_dialect_runtime import (
    build_shell_dialect_capability,
    build_shell_profile,
    build_shell_profile_trace_source,
    build_structured_shell_command,
    classify_shell_dialect_error,
    decide_shell_dialect_retry,
    detect_shell_profile_from_environment,
    dump_shell_dialect,
    infer_shell_id,
    preflight_shell_dialect_command,
    translate_structured_shell_command,
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


def test_shell_dialect_translation_is_declarative_and_non_executable():
    profile = build_shell_profile(shell_id="git_bash")
    command = build_structured_shell_command(
        intent="inspect",
        command_name="git",
        args=["status", "--short"],
        shell_profile=profile,
    )

    translation = translate_structured_shell_command(command, target_shell_id="powershell_7")

    assert translation.translation_kind == "shell_dialect_translation"
    assert translation.source_shell_id == "git_bash"
    assert translation.target_shell_id == "powershell_7"
    assert translation.source_argv == ["git", "status", "--short"]
    assert translation.translated_argv == ["git", "status", "--short"]
    assert translation.can_execute is False
    assert translation.execution_permission_granted is False
    assert translation.translation_executed_process is False
    assert translation.preflight_required is True
    assert "require_policy_matrix_approval" in translation.required_actions
    assert "quote_for_powershell_before_execution" in translation.required_actions


def test_shell_dialect_translation_blocks_raw_command_strings():
    command = build_structured_shell_command(
        intent="run",
        raw_command="git status && npm test",
        shell_id="git_bash",
    )

    translation = translate_structured_shell_command(command, target_shell_id="powershell_5")

    assert translation.translation_status == "blocked"
    assert translation.can_execute is False
    assert translation.raw_command == "git status && npm test"
    assert "parse_raw_command_before_translation" in translation.required_actions
    assert "block_bash_and_operator" in translation.required_actions


def test_shell_dialect_translation_to_python_keeps_structured_argv():
    command = build_structured_shell_command(
        intent="validate",
        command_name="python",
        args=["-m", "py_compile", "backend/apps/swarms/shell_dialect_runtime.py"],
        shell_id="git_bash",
    )

    translation = translate_structured_shell_command(command, target_shell_id="python_subprocess")

    assert translation.target_shell_id == "python_subprocess"
    assert translation.target_shell_family == "python"
    assert translation.translated_argv == [
        "python",
        "-m",
        "py_compile",
        "backend/apps/swarms/shell_dialect_runtime.py",
    ]
    assert "keep_as_structured_argv" in translation.required_actions
    assert translation.can_execute is False


def test_shell_dialect_translation_redacts_metadata_and_environment():
    command = build_structured_shell_command(
        intent="inspect",
        command_name="echo",
        args=["safe"],
        shell_id="git_bash",
        environment={"TOKEN": "secret", "SAFE_ENV": "visible"},
    )

    translation = translate_structured_shell_command(
        command,
        target_shell_id="cmd",
        metadata={"api_key": "secret", "safe": "visible"},
    )
    dumped = dump_shell_dialect(translation)

    assert dumped["environment"]["TOKEN"] == "[redacted]"
    assert dumped["environment"]["SAFE_ENV"] == "visible"
    assert dumped["metadata"]["api_key"] == "[redacted]"
    assert dumped["metadata"]["safe"] == "visible"
    assert "quote_for_cmd_before_execution" in translation.required_actions


def test_preflight_blocks_powershell_5_and_operator_without_policy_approval():
    command = build_structured_shell_command(
        intent="test",
        command_name="npm",
        args=["test", "&&", "npm", "run", "lint"],
        shell_id="powershell_5",
    )

    preflight = preflight_shell_dialect_command(command)

    assert preflight.preflight_kind == "shell_dialect_preflight"
    assert preflight.preflight_status == "blocked"
    assert preflight.can_execute is False
    assert preflight.execution_permission_granted is False
    assert "powershell_5_invalid_and_operator" in preflight.diagnostics
    assert "policy_matrix_approval_missing" in preflight.diagnostics
    assert "block_bash_and_operator_for_powershell_5" in preflight.required_actions


def test_preflight_accepts_translation_and_blocks_raw_redirection():
    command = build_structured_shell_command(
        intent="inspect",
        command_name="cat",
        args=["file.txt", ">", "out.txt"],
        shell_id="git_bash",
    )
    translation = translate_structured_shell_command(command, target_shell_id="cmd")

    preflight = preflight_shell_dialect_command(translation, policy_matrix_approved=True)

    assert preflight.target_shell_id == "cmd"
    assert preflight.preflight_status == "blocked"
    assert "raw_shell_pipe_or_redirection" in preflight.diagnostics
    assert preflight.can_execute is False


def test_preflight_can_pass_as_contract_but_still_cannot_execute():
    command = build_structured_shell_command(
        intent="inspect",
        command_name="git",
        args=["status", "--short"],
        shell_id="git_bash",
    )

    preflight = preflight_shell_dialect_command(command, policy_matrix_approved=True)

    assert preflight.preflight_status == "passed"
    assert preflight.can_execute is False
    assert preflight.execution_permission_granted is False
    assert "policy_matrix_approval_missing" not in preflight.diagnostics


def test_classify_shell_dialect_error_redacts_secret_and_detects_powershell_and_operator():
    classified = classify_shell_dialect_error(
        "The token secret && is not a valid statement separator in this version.",
        shell_id="powershell_5",
        shell_family="powershell",
    )

    assert classified.classification == "powershell_invalid_and_operator"
    assert classified.target_shell_id == "powershell_5"
    assert classified.can_execute is False
    assert classified.sanitized_error == "[redacted]"
    assert "translate_bash_and_operator_for_powershell" in classified.required_actions


def test_classify_shell_dialect_error_categories():
    assert classify_shell_dialect_error("git: command not found").classification == "command_not_found"
    assert classify_shell_dialect_error("Cannot find path C:\\missing").classification == "path_not_found"
    assert classify_shell_dialect_error("Access is denied").classification == "permission_denied"
    assert classify_shell_dialect_error("running scripts is disabled by ExecutionPolicy").classification == "execution_policy_blocked"
    assert classify_shell_dialect_error("unexpected token quote").classification == "quoting_or_parsing_error"
    assert classify_shell_dialect_error("process timed out").classification == "timeout"
    assert classify_shell_dialect_error("unmapped failure").classification == "unknown"


def test_retry_policy_never_retries_automatically():
    classified = classify_shell_dialect_error("git: command not found")

    decision = decide_shell_dialect_retry(classified)

    assert decision.retry_kind == "shell_dialect_retry_decision"
    assert decision.retry_status == "needs_human_review"
    assert decision.should_retry is False
    assert decision.can_execute is False
    assert "do_not_retry_automatically" in decision.next_required_actions


def test_retry_policy_blocks_blocked_preflight():
    command = build_structured_shell_command(raw_command="git status && npm test", shell_id="powershell_5")
    preflight = preflight_shell_dialect_command(command)

    decision = decide_shell_dialect_retry(preflight)

    assert decision.retry_status == "blocked"
    assert decision.should_retry is False
    assert "resolve_preflight_blockers" in decision.next_required_actions
