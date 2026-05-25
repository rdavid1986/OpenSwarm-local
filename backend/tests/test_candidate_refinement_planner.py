import pytest

from backend.apps.agents.runtime.provider import ProviderEvent
from backend.apps.swarms.candidate_refinement_planner import (
    build_candidate_refinement_prompt,
    normalize_candidate_refinement_plan,
    plan_candidate_refinement_file_updates,
)


class _FakePlannerAdapter:
    def __init__(self, content: str):
        self.content = content

    async def run_turn(self, context):
        yield ProviderEvent(type="message_final", payload={"message": {"role": "assistant", "content": self.content}})


def test_build_candidate_refinement_prompt_includes_allowed_files_only():
    prompt = build_candidate_refinement_prompt(
        requested_change="Make hero blue.",
        files_after={
            "index.html": "<html></html>",
            "styles.css": "body {}",
            "backend.py": "print('no')",
        },
    )

    assert "Make hero blue." in prompt
    assert "index.html" in prompt
    assert "styles.css" in prompt
    assert '"backend.py": "print' not in prompt


def test_normalize_candidate_refinement_plan_accepts_changed_allowed_file():
    result = normalize_candidate_refinement_plan(
        {
            "status": "planned",
            "reason": "Updated hero copy.",
            "file_updates": {"index.html": "<html><body>After</body></html>"},
        },
        existing_files={"index.html": "<html><body>Before</body></html>"},
    )

    assert result["ok"] is True
    assert result["status"] == "planned"
    assert result["file_updates"] == {"index.html": "<html><body>After</body></html>"}


def test_normalize_candidate_refinement_plan_blocks_disallowed_file():
    result = normalize_candidate_refinement_plan(
        {
            "status": "planned",
            "reason": "Bad update.",
            "file_updates": {"backend.py": "print('no')"},
        },
        existing_files={"index.html": "<html></html>"},
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert "disallowed" in result["reason"]


def test_normalize_candidate_refinement_plan_blocks_missing_candidate_file():
    result = normalize_candidate_refinement_plan(
        {
            "status": "planned",
            "reason": "Bad update.",
            "file_updates": {"schema.json": "{}"},
        },
        existing_files={"index.html": "<html></html>"},
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert "not present" in result["reason"]


def test_normalize_candidate_refinement_plan_drops_unchanged_updates():
    result = normalize_candidate_refinement_plan(
        {
            "status": "planned",
            "reason": "No effective change.",
            "file_updates": {"index.html": "<html></html>"},
        },
        existing_files={"index.html": "<html></html>"},
    )

    assert result["ok"] is True
    assert result["status"] == "no_change"
    assert result["file_updates"] == {}


@pytest.mark.asyncio
async def test_plan_candidate_refinement_file_updates_uses_adapter():
    result = await plan_candidate_refinement_file_updates(
        requested_change="Make hero blue.",
        files_after={"index.html": "<html><body>Before</body></html>"},
        adapter_factory=lambda: _FakePlannerAdapter(
            '{"status":"planned","reason":"ok","file_updates":{"index.html":"<html><body>After</body></html>"}}'
        ),
    )

    assert result["ok"] is True
    assert result["status"] == "planned"
    assert result["file_updates"]["index.html"] == "<html><body>After</body></html>"


@pytest.mark.asyncio
async def test_plan_candidate_refinement_file_updates_fails_closed_on_bad_json():
    result = await plan_candidate_refinement_file_updates(
        requested_change="Make hero blue.",
        files_after={"index.html": "<html><body>Before</body></html>"},
        adapter_factory=lambda: _FakePlannerAdapter("not json"),
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["file_updates"] == {}
