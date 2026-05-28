from pathlib import Path
import json

import pytest
from pydantic import ValidationError

from backend.apps.configuration.models import ProjectConfig


def _patch_project_root(monkeypatch, tmp_path: Path):
    root = tmp_path / "projects"
    import backend.apps.configuration.store as store

    monkeypatch.setattr(store, "PROJECT_CONFIG_ROOT", str(root))
    return root


def test_project_config_requires_project_id():
    with pytest.raises(ValidationError):
        ProjectConfig()


def test_project_id_is_sanitized_for_safe_path(monkeypatch, tmp_path: Path):
    root = _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.store import project_config_path, sanitize_project_id

    safe = sanitize_project_id("My Project/../alpha")
    path = Path(project_config_path("My Project/../alpha"))

    assert safe == "My_Project_alpha"
    assert path == root / "My_Project_alpha" / "config.json"


def test_path_traversal_project_id_is_normalized_safely(monkeypatch, tmp_path: Path):
    root = _patch_project_root(monkeypatch, tmp_path).resolve()
    from backend.apps.configuration.store import project_config_path

    path = Path(project_config_path("../../secret-project")).resolve()

    assert path.is_relative_to(root)
    assert ".." not in path.relative_to(root).as_posix()


def test_load_project_defaults_when_file_missing(monkeypatch, tmp_path: Path):
    root = _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.store import load_project_config

    config = load_project_config("project-a")

    assert config.project_id == "project-a"
    assert config.schema_version == 1
    assert config.preferred_models["primary"] == "auto"
    assert (root / "project-a" / "config.json").exists()


def test_save_and_reload_project_config(monkeypatch, tmp_path: Path):
    _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.store import load_project_config, save_project_config

    save_project_config("project-a", {"project_name": "Project A", "project_instructions": "Use tests."})
    loaded = load_project_config("project-a")

    assert loaded.project_name == "Project A"
    assert loaded.project_instructions == "Use tests."


def test_project_config_store_removes_secret_fields(monkeypatch, tmp_path: Path):
    root = _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.store import save_project_config

    save_project_config(
        "project-a",
        {
            "api_key": "sk-test",
            "token": "t",
            "password": "p",
            "credential": "c",
            "private_key": "k",
            "tool_policy": {"auth_token": "nested", "never_assume_permissions": True},
        },
    )
    raw_text = (root / "project-a" / "config.json").read_text(encoding="utf-8")

    assert "api_key" not in raw_text
    assert "token" not in raw_text
    assert "password" not in raw_text
    assert "credential" not in raw_text
    assert "private_key" not in raw_text
    assert "auth_token" not in raw_text


def test_project_config_store_does_not_persist_mcp_activation(monkeypatch, tmp_path: Path):
    root = _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.store import save_project_config

    save_project_config(
        "project-a",
        {
            "mcp_policy": {
                "active_mcps": ["gmail"],
                "mcp_enabled": True,
                "activation_requires_explicit_user_action": True,
            },
            "activate_mcp": "gmail",
        },
    )
    raw = json.loads((root / "project-a" / "config.json").read_text(encoding="utf-8"))

    assert "activate_mcp" not in raw
    assert "active_mcps" not in raw["mcp_policy"]
    assert "mcp_enabled" not in raw["mcp_policy"]
    assert raw["mcp_policy"]["activation_requires_explicit_user_action"] is True


def test_effective_config_preserves_project_config_source(monkeypatch, tmp_path: Path):
    _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config
    from backend.apps.configuration.store import load_project_config, save_project_config

    save_project_config("project-a", {"project_instructions": "Prefer pytest."})
    result = resolve_effective_config(project_config=load_project_config("project-a").to_project_config())

    assert result.effective_config.values["project_instructions"] == "Prefer pytest."
    assert result.source_map["project_instructions"] == ConfigSource.PROJECT_CONFIG


def test_project_override_wins_over_user_global(monkeypatch, tmp_path: Path):
    _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config
    from backend.apps.configuration.store import load_project_config, save_project_config

    save_project_config("project-a", {"default_language": "pt"})
    result = resolve_effective_config(
        user_global={"default_language": "es"},
        project_config=load_project_config("project-a").to_project_config(),
    )

    assert result.effective_config.values["default_language"] == "pt"
    assert result.source_map["default_language"] == ConfigSource.PROJECT_CONFIG


def test_effective_config_uses_global_when_project_does_not_override(monkeypatch, tmp_path: Path):
    _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config
    from backend.apps.configuration.store import load_project_config

    result = resolve_effective_config(
        user_global={"default_language": "es"},
        project_config=load_project_config("project-a").to_project_config(),
    )

    assert result.effective_config.values["default_language"] == "es"
    assert result.source_map["default_language"] == ConfigSource.USER_GLOBAL


def test_effective_hash_changes_when_project_effective_config_changes(monkeypatch, tmp_path: Path):
    _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.resolver import resolve_effective_config
    from backend.apps.configuration.store import load_project_config, save_project_config

    first = resolve_effective_config(project_config=load_project_config("project-a").to_project_config())
    save_project_config("project-a", {"project_instructions": "Run tests."})
    second = resolve_effective_config(project_config=load_project_config("project-a").to_project_config())

    assert first.effective_config_hash != second.effective_config_hash


def test_project_config_file_written_under_projects_safe_project_id(monkeypatch, tmp_path: Path):
    root = _patch_project_root(monkeypatch, tmp_path)
    from backend.apps.configuration.store import project_config_path, save_project_config

    save_project_config("Project One", {"project_name": "Project One"})

    assert Path(project_config_path("Project One")) == root / "Project_One" / "config.json"
    assert (root / "Project_One" / "config.json").exists()
