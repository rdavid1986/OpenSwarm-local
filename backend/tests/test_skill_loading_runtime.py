from backend.apps.skills.skill_loading_runtime import (
    attach_skill_loading_to_metadata,
    build_skill_availability_index,
    build_skill_context_budget_cost,
    build_skill_loading_trace_source,
    build_skill_runtime_context_payload,
    dump_skill_availability_index,
    estimate_skill_context_tokens,
    select_skill_for_runtime,
)


def _installed_skill():
    return {
        "id": "python-debugger",
        "name": "Python Debugger",
        "description": "Debug Python pytest failures",
        "content": "Use pytest, inspect traceback, patch smallest failing unit.",
        "required_tools": ["pytest"],
        "tags": ["python", "debug"],
        "provenance": {"source_hash": "abc", "evidence_refs": ["ev1"]},
        "content_hash": "hash1",
    }


def _candidate_skill():
    return {
        "candidate_id": "candidate-ui-skill",
        "skill_spec": {
            "name": "UI Reviewer",
            "description": "Review frontend UI consistency",
            "content": "Review UI components.",
            "tags": ["frontend", "ui"],
            "provenance": {"source_hash": "def"},
        },
    }


def test_skill_availability_index_is_compact_and_safe():
    index = build_skill_availability_index(installed_skills=[_installed_skill()], candidates=[_candidate_skill()], registry_skills=[{"name": "Remote Skill", "description": "Remote registry item"}])

    data = dump_skill_availability_index(index)

    assert data["total_count"] == 3
    assert data["installed_count"] == 1
    assert data["candidate_count"] == 1
    assert data["registry_count"] == 1
    assert data["entries"][0]["content_preview"]
    assert data["can_install_skill"] is False
    assert data["can_activate_tools"] is False


def test_skill_context_budget_cost_summary_and_full_modes():
    summary = build_skill_context_budget_cost(_installed_skill(), load_mode="summary_only", max_context_tokens=10_000)
    full = build_skill_context_budget_cost(_installed_skill(), load_mode="full_content", max_context_tokens=10_000)

    assert summary.selected_tokens < full.selected_tokens
    assert summary.status == "within_budget"
    assert full.skill_ref == "python-debugger"


def test_skill_context_budget_detects_over_budget():
    cost = build_skill_context_budget_cost(_installed_skill(), load_mode="full_content", max_context_tokens=1)

    assert cost.status == "over_budget"
    assert "skill_context_over_budget" in cost.warnings


def test_select_skill_for_runtime_prefers_installed_match():
    index = build_skill_availability_index(installed_skills=[_installed_skill()], candidates=[_candidate_skill()])
    selection = select_skill_for_runtime(task={"task_id": "t1", "requirements": ["python", "pytest"], "title": "debug pytest"}, availability_index=index, max_context_tokens=5000, allow_full_content=True)

    assert selection.status == "selected"
    assert selection.selected_skill_ref == "python-debugger"
    assert selection.selected_source == "installed_skill"
    assert selection.load_mode == "full_content"
    assert selection.can_install_skill is False


def test_select_skill_for_runtime_candidate_is_summary_only_and_reviewed():
    index = build_skill_availability_index(candidates=[_candidate_skill()])
    selection = select_skill_for_runtime(task={"requirements": ["frontend", "ui"]}, availability_index=index, allow_full_content=True)

    assert selection.selected_source == "candidate"
    assert selection.load_mode == "summary_only"
    assert "review_skill_candidate_or_registry_source" in selection.required_actions


def test_skill_runtime_context_payload_loads_full_only_for_installed_approved_mode():
    index = build_skill_availability_index(installed_skills=[_installed_skill()])
    selection = select_skill_for_runtime(task={"requirements": ["python"]}, availability_index=index, allow_full_content=True)

    summary_payload = build_skill_runtime_context_payload(selection, availability_index=index, include_full_content=False)
    full_payload = build_skill_runtime_context_payload(selection, availability_index=index, include_full_content=True)

    assert summary_payload.status == "loaded_summary"
    assert full_payload.status == "loaded_full"
    assert full_payload.context_sections[0]["metadata"]["injection_authorizes_actions"] is False
    assert full_payload.can_execute_source is False


def test_skill_runtime_context_payload_preserves_provenance_and_evidence_refs():
    index = build_skill_availability_index(installed_skills=[_installed_skill()])
    selection = select_skill_for_runtime(task={"requirements": ["python"]}, availability_index=index)
    payload = build_skill_runtime_context_payload(selection, availability_index=index)

    assert payload.provenance["source_hash"] == "abc"
    assert payload.evidence_refs == ["ev1"]
    assert payload.version_refs["content_hash"] == "hash1"


def test_skill_loading_trace_source_is_safe():
    index = build_skill_availability_index(installed_skills=[_installed_skill()], metadata={"secret_token": "leak"})
    selection = select_skill_for_runtime(task={"requirements": ["python"]}, availability_index=index)
    payload = build_skill_runtime_context_payload(selection, availability_index=index)
    trace = build_skill_loading_trace_source(availability_index=index, selection=selection, context_payload=payload, metadata={"raw_prompt": "leak"})

    text = str(trace).lower()

    assert trace["source_kind"] == "skill_loading_runtime"
    assert "leak" not in text
    assert trace["can_install_skill"] is False
    assert trace["can_activate_mcp"] is False


def test_attach_skill_loading_to_metadata_does_not_mutate_original():
    index = build_skill_availability_index(installed_skills=[_installed_skill()])
    original = {"existing": True}

    attached = attach_skill_loading_to_metadata(original, availability_index=index)

    assert original == {"existing": True}
    assert attached["existing"] is True
    assert attached["skill_loading_runtime"]["availability_index"]["total_count"] == 1


def test_estimate_skill_context_tokens_is_bounded():
    assert estimate_skill_context_tokens("") == 0
    assert estimate_skill_context_tokens("abcd") == 1
    assert estimate_skill_context_tokens("abcde") == 2
