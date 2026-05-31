from backend.apps.skills.skill_loading_runtime import (
    build_skill_availability_index,
    build_skill_loading_trace_source,
    build_skill_runtime_context_payload,
    select_skill_for_runtime,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def _skill():
    return {
        "id": "python-debugger",
        "name": "Python Debugger",
        "description": "Debug Python pytest failures",
        "content": "Use pytest and traceback.",
        "tags": ["python", "debug"],
        "provenance": {"source_hash": "abc", "evidence_refs": ["ev1"]},
    }


def test_process_trace_recognizes_skill_loading_runtime():
    index = build_skill_availability_index(installed_skills=[_skill()])
    selection = select_skill_for_runtime(task={"requirements": ["python"]}, availability_index=index, allow_full_content=True)
    payload = build_skill_runtime_context_payload(selection, availability_index=index, include_full_content=True)
    source = build_skill_loading_trace_source(availability_index=index, selection=selection, context_payload=payload)

    assert normalize_process_trace_source_kind(source) == "skill_loading_runtime"

    item = build_process_trace_item_from_source(source)

    assert item["subsystem"] == "SkillCore"
    assert item["kind"] == "skill"
    assert item["details"]["source_kind"] == "skill_loading_runtime"
    assert item["details"]["context_payload"]["status"] == "loaded_full"
    assert item["evidence_refs"] == ["ev1"]


def test_skill_loading_process_trace_is_redacted():
    source = {
        "source_kind": "skill_loading_runtime",
        "loading_kind": "skill_loading_runtime",
        "status": "loaded_summary",
        "availability_index": {"metadata": {"secret_token": "leak"}},
        "selection": {"selected_skill_ref": "skill1", "raw_prompt": "leak"},
        "context_payload": {"status": "loaded_summary", "response": "leak"},
    }

    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    assert item["subsystem"] == "SkillCore"
    assert "leak" not in text
    assert "raw_prompt" not in text
    assert "response" not in text


def test_skill_loading_process_trace_warns_when_actions_required():
    source = {
        "source_kind": "skill_loading_runtime",
        "loading_kind": "skill_loading_runtime",
        "status": "selected",
        "selection": {"selected_skill_ref": "candidate1", "required_actions": ["review_skill_candidate_or_registry_source"]},
        "required_actions": ["review_skill_candidate_or_registry_source"],
    }

    item = build_process_trace_item_from_source(source)

    assert item["status"] == "warning"
    assert item["details"]["required_actions"] == ["review_skill_candidate_or_registry_source"]
