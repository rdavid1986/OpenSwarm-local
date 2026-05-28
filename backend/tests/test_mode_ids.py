from backend.apps.modes.mode_ids import (
    CANONICAL_MODE_IDS,
    is_known_mode_id,
    is_project_mode,
    mode_aliases,
    normalize_mode_id,
)


def test_normalize_mode_id_preserves_core_modes():
    assert normalize_mode_id("ask") == "ask"
    assert normalize_mode_id("plan") == "plan"
    assert normalize_mode_id("agent") == "agent"
    assert normalize_mode_id("debug") == "debug"


def test_normalize_mode_id_maps_builder_aliases():
    assert normalize_mode_id("skill-builder") == "skill_builder"
    assert normalize_mode_id("skill_builder") == "skill_builder"
    assert normalize_mode_id("view-builder") == "app_builder"
    assert normalize_mode_id("view_builder") == "app_builder"
    assert normalize_mode_id("app-builder") == "app_builder"
    assert normalize_mode_id("app_builder") == "app_builder"


def test_normalize_mode_id_maps_refine_aliases():
    assert normalize_mode_id("refine") == "refine"
    assert normalize_mode_id("output_refine") == "refine"
    assert normalize_mode_id("output-refine") == "refine"
    assert normalize_mode_id("candidate_refinement") == "refine"
    assert normalize_mode_id("candidate-refinement") == "refine"


def test_normalize_mode_id_fallbacks_are_canonical():
    assert normalize_mode_id(None) == "ask"
    assert normalize_mode_id("") == "ask"
    assert normalize_mode_id("unknown") == "ask"
    assert normalize_mode_id("unknown", default="plan") == "plan"
    assert normalize_mode_id("unknown", default="skill-builder") == "skill_builder"


def test_known_mode_accepts_aliases_and_rejects_unknown():
    assert is_known_mode_id("skill-builder") is True
    assert is_known_mode_id("skill_builder") is True
    assert is_known_mode_id("view-builder") is True
    assert is_known_mode_id("candidate_refinement") is True
    assert is_known_mode_id("not-a-mode") is False


def test_mode_aliases_returns_stable_aliases_for_canonical_target():
    assert "skill-builder" in mode_aliases("skill_builder")
    assert "skill_builder" in mode_aliases("skill_builder")
    assert "view-builder" in mode_aliases("app_builder")
    assert "app_builder" in mode_aliases("app_builder")
    assert "candidate_refinement" in mode_aliases("refine")


def test_project_mode_uses_canonical_mode_ids():
    assert is_project_mode("plan") is True
    assert is_project_mode("view-builder") is True
    assert is_project_mode("skill-builder") is True
    assert is_project_mode("candidate_refinement") is True
    assert is_project_mode("ask") is False
    assert is_project_mode("agent") is False


def test_all_canonical_modes_normalize_to_themselves():
    for mode_id in CANONICAL_MODE_IDS:
        assert normalize_mode_id(mode_id) == mode_id

def test_agent_manager_resolves_canonical_builder_modes_to_legacy_mode_store(monkeypatch):
    from backend.apps.agents.agent_manager import AgentManager
    from backend.apps.modes.models import Mode

    def fake_load_mode(mode_id: str):
        if mode_id == "view-builder":
            return Mode(
                id="view-builder",
                name="App Builder",
                system_prompt="app prompt",
                tools=["Read"],
                default_folder="/tmp/app-workspace",
            )
        if mode_id == "skill-builder":
            return Mode(
                id="skill-builder",
                name="Skill Builder",
                system_prompt="skill prompt",
                tools=["Read", "Write"],
                default_folder="/tmp/skill-workspace",
            )
        return None

    monkeypatch.setattr("backend.apps.agents.agent_manager.load_mode", fake_load_mode)

    manager = AgentManager()

    assert manager._resolve_mode("app_builder") == (["Read"], "app prompt", "/tmp/app-workspace")
    assert manager._resolve_mode("skill_builder") == (["Read", "Write"], "skill prompt", "/tmp/skill-workspace")
