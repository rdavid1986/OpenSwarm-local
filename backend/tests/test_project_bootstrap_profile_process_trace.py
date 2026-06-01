from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.project_bootstrap_profile import (
    build_project_bootstrap_profile,
    build_project_command_contract,
    build_project_stack_profile,
    decide_project_artifact_store_mode,
)


def assert_bootstrap_trace(source):
    assert normalize_process_trace_source_kind(source) == "project_bootstrap_profile"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "project_bootstrap_profile"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_run_tests"] is False
    assert item["details"]["can_run_build"] is False
    assert item["details"]["can_run_lint"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_process_trace_recognizes_all_bootstrap_contracts():
    stack = build_project_stack_profile(markers=["frontend/package.json", "backend/tests"])
    commands = build_project_command_contract(stack)
    artifact = decide_project_artifact_store_mode(stack, commands)
    profile = build_project_bootstrap_profile(markers=["frontend/package.json", "backend/tests"])

    items = [assert_bootstrap_trace(source) for source in [stack, commands, artifact, profile]]

    assert [item["details"]["contract_kind"] for item in items] == [
        "project_stack_profile",
        "project_test_build_lint_contract",
        "project_artifact_store_mode_decision",
        "project_bootstrap_profile",
    ]


def test_process_trace_maps_subsystems():
    stack = assert_bootstrap_trace(build_project_stack_profile(markers=["package.json"]))
    commands = assert_bootstrap_trace(build_project_command_contract(build_project_stack_profile(markers=["package.json"])))
    artifact = assert_bootstrap_trace(decide_project_artifact_store_mode(build_project_stack_profile(markers=["frontend/package.json"])))
    profile = assert_bootstrap_trace(build_project_bootstrap_profile(markers=["package.json"]))

    assert stack["subsystem"] == "ConfigCore"
    assert commands["subsystem"] == "ValidationCore"
    assert artifact["subsystem"] == "OutputCore"
    assert profile["subsystem"] == "ReviewCore"


def test_process_trace_low_information_is_warning():
    profile = build_project_bootstrap_profile(markers=[])
    item = assert_bootstrap_trace(profile)

    assert item["status"] == "warning"
    assert "provide_project_root_markers" in item["details"]["required_actions"]


def test_process_trace_includes_commands_as_suggestions_only():
    profile = build_project_bootstrap_profile(markers=["frontend/package.json", "backend/tests"])
    item = assert_bootstrap_trace(profile)

    assert "npm --prefix frontend run build" in item["details"]["build_commands"]
    assert item["details"]["commands_are_suggestions"] is True
    assert item["details"]["can_run_tests"] is False
