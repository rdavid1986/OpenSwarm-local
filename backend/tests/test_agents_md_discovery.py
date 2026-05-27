from pathlib import Path

from backend.apps.swarms.agents_md import (
    discover_agents_md_files,
    normalize_agents_md_discovery_result,
    should_skip_agents_md_discovery_dir,
)


def test_should_skip_agents_md_discovery_dir_excludes_heavy_paths():
    assert should_skip_agents_md_discovery_dir(Path(".git")) is True
    assert should_skip_agents_md_discovery_dir(Path("node_modules")) is True
    assert should_skip_agents_md_discovery_dir(Path(".venv")) is True
    assert should_skip_agents_md_discovery_dir(Path("backend")) is False


def test_normalize_agents_md_discovery_result_does_not_load_content(tmp_path: Path):
    agents_file = tmp_path / "backend" / "AGENTS.md"
    agents_file.parent.mkdir()
    agents_file.write_text("Do not read this in discovery.", encoding="utf-8")

    result = normalize_agents_md_discovery_result(agents_file, tmp_path)

    assert result["path"] == "backend/AGENTS.md"
    assert result["filename"] == "AGENTS.md"
    assert result["scope_path"] == "backend"
    assert result["depth"] == 1
    assert result["exists"] is True
    assert result["is_file"] is True
    assert result["content_loaded"] is False
    assert result["parser_applied"] is False
    assert result["injection_ready"] is False


def test_discover_agents_md_files_finds_root_and_nested_files(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("root instructions", encoding="utf-8")
    nested = tmp_path / "backend" / "apps"
    nested.mkdir(parents=True)
    (nested / "AGENTS.md").write_text("backend instructions", encoding="utf-8")

    result = discover_agents_md_files(tmp_path)

    assert result["ok"] is True
    assert result["reason"] == "discovery_complete"
    assert result["count"] == 2
    assert [item["path"] for item in result["found"]] == [
        "AGENTS.md",
        "backend/apps/AGENTS.md",
    ]
    assert result["found"][0]["scope_path"] == "."
    assert result["found"][1]["scope_path"] == "backend/apps"


def test_discover_agents_md_files_skips_ignored_directories(tmp_path: Path):
    ignored = tmp_path / "node_modules" / "package"
    ignored.mkdir(parents=True)
    (ignored / "AGENTS.md").write_text("ignore", encoding="utf-8")

    included = tmp_path / "frontend"
    included.mkdir()
    (included / "agents.md").write_text("include", encoding="utf-8")

    result = discover_agents_md_files(tmp_path)

    assert result["count"] == 1
    assert result["found"][0]["path"] == "frontend/agents.md"


def test_discover_agents_md_files_handles_missing_root(tmp_path: Path):
    result = discover_agents_md_files(tmp_path / "missing")

    assert result["ok"] is False
    assert result["count"] == 0
    assert result["found"] == []
    assert result["reason"] == "repo_root_missing"


def test_discover_agents_md_files_respects_max_results(tmp_path: Path):
    for index in range(3):
        folder = tmp_path / f"pkg_{index}"
        folder.mkdir()
        (folder / "AGENTS.md").write_text("instructions", encoding="utf-8")

    result = discover_agents_md_files(tmp_path, max_results=2)

    assert result["ok"] is True
    assert result["count"] == 2
    assert result["reason"] == "max_results_reached"
