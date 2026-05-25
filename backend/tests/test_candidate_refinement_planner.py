import pytest

from backend.apps.agents.runtime.provider import ProviderEvent
from backend.apps.swarms.candidate_refinement_planner import (
    build_candidate_refinement_prompt,
    normalize_candidate_refinement_plan,
    plan_candidate_refinement_file_updates,
    plan_candidate_refinement_fast_path,
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


def test_fast_path_updates_title_color_in_styles_css():
    result = plan_candidate_refinement_fast_path(
        requested_change="cambia el color del titulo a verde",
        files_after={
            "styles.css": ".hero h1 {\n  font-size: 3rem;\n  color: #111827;\n}\n",
        },
    )

    assert result is not None
    assert result["ok"] is True
    assert result["planner"] == "fast_path"
    assert result["file_updates"] == {
        "styles.css": ".hero h1 {\n  font-size: 3rem;\n  color: green;\n}\n"
    }


def test_fast_path_appends_title_color_when_selector_has_no_color():
    result = plan_candidate_refinement_fast_path(
        requested_change="cambia el color del título a azul",
        files_after={
            "styles.css": ".hero h1 {\n  font-size: 3rem;\n}\n",
        },
    )

    assert result is not None
    assert result["ok"] is True
    assert "color: blue;" in result["file_updates"]["styles.css"]


def test_fast_path_returns_none_for_unrecognized_request():
    result = plan_candidate_refinement_fast_path(
        requested_change="agrega una sección nueva de precios",
        files_after={"styles.css": ".hero h1 { color: black; }\n"},
    )

    assert result is None


@pytest.mark.asyncio
async def test_plan_candidate_refinement_file_updates_uses_fast_path_without_adapter():
    def fail_adapter():
        raise AssertionError("model adapter should not be called for fast path")

    result = await plan_candidate_refinement_file_updates(
        requested_change="cambia el color del titulo a verde",
        files_after={"styles.css": ".hero h1 {\n  color: black;\n}\n"},
        adapter_factory=fail_adapter,
    )

    assert result["ok"] is True
    assert result["planner"] == "fast_path"
    assert result["file_updates"]["styles.css"] == ".hero h1 {\n  color: green;\n}\n"


def test_fast_path_updates_title_text_in_content_json_and_index_html():
    result = plan_candidate_refinement_fast_path(
        requested_change='cambia el título principal a "Agencia Nova Digital"',
        files_after={
            "content.json": '{\n  "title": "Agencia Nova"\n}\n',
            "index.html": "<h1>Agencia Nova</h1>\n",
            "styles.css": ".hero h1 { color: black; }\n",
        },
    )

    assert result is not None
    assert result["ok"] is True
    assert result["planner"] == "fast_path"
    assert '"title": "Agencia Nova Digital"' in result["file_updates"]["content.json"]
    assert result["file_updates"]["index.html"] == "<h1>Agencia Nova Digital</h1>\n"


def test_fast_path_updates_button_text_in_content_json_and_index_html():
    result = plan_candidate_refinement_fast_path(
        requested_change='cambia el texto del botón a "Solicitar propuesta"',
        files_after={
            "content.json": '{\n  "buttonText": "Contactar"\n}\n',
            "index.html": "<button>Contactar</button>\n",
            "styles.css": ".hero h1 { color: black; }\n",
        },
    )

    assert result is not None
    assert result["ok"] is True
    assert result["planner"] == "fast_path"
    assert '"buttonText": "Solicitar propuesta"' in result["file_updates"]["content.json"]
    assert result["file_updates"]["index.html"] == "<button>Solicitar propuesta</button>\n"


@pytest.mark.asyncio
async def test_plan_candidate_refinement_file_updates_uses_text_fast_path_without_adapter():
    def fail_adapter():
        raise AssertionError("model adapter should not be called for text fast path")

    result = await plan_candidate_refinement_file_updates(
        requested_change='cambia el título principal a "Agencia Nova Digital"',
        files_after={
            "content.json": '{\n  "title": "Agencia Nova"\n}\n',
            "index.html": "<h1>Agencia Nova</h1>\n",
        },
        adapter_factory=fail_adapter,
    )

    assert result["ok"] is True
    assert result["planner"] == "fast_path"
    assert "Agencia Nova Digital" in result["file_updates"]["content.json"]
