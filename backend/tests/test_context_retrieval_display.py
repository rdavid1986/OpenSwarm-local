import json

from backend.apps.swarms.context_retrieval_display import build_context_retrieval_display_item, build_context_retrieval_panel, summarize_context_retrieval_display


def test_context_display_json_safe_no_cot_redaction_flag():
    item = build_context_retrieval_display_item(source_type="session_summary", title="Recent session", summary="Worked on imports", redaction_applied=True, chain_of_thought="hidden")
    dumped = json.dumps(item)
    assert item["source_type"] == "session_summary"
    assert item["redaction_applied"] is True
    assert "chain_of_thought" not in dumped


def test_context_panel_can_show_prompts_observations_summaries():
    items = [
        build_context_retrieval_display_item(source_type="user_prompt", title="Prompt", summary="Asked for trace"),
        build_context_retrieval_display_item(source_type="memory", title="Observation", summary="Import contracts exist"),
    ]
    panel = build_context_retrieval_panel(items)
    assert panel["title"] == "Mem / Context"
    assert panel["item_count"] == 2
    assert panel["visible_to_user"] is True
    assert summarize_context_retrieval_display(items[0])["title"] == "Prompt"
