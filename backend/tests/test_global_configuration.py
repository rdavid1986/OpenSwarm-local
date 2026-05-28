from pathlib import Path
import json

from backend.apps.configuration.models import GlobalUserConfig


def _patch_store_path(monkeypatch, tmp_path: Path):
    path = tmp_path / "settings" / "global_config.json"
    import backend.apps.configuration.store as store

    monkeypatch.setattr(store, "GLOBAL_CONFIG_FILE", str(path))
    return path


def test_load_defaults_when_global_config_file_is_missing(monkeypatch, tmp_path: Path):
    path = _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.store import load_global_config

    config = load_global_config()

    assert isinstance(config, GlobalUserConfig)
    assert config.schema_version == 1
    assert config.default_language == "es"
    assert config.default_commit_policy == "never_without_explicit_request"
    assert path.exists()


def test_save_and_reload_global_config(monkeypatch, tmp_path: Path):
    _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.store import load_global_config, save_global_config

    saved = save_global_config({"default_language": "en", "default_model": "opus"})
    loaded = load_global_config()

    assert saved.default_language == "en"
    assert loaded.default_language == "en"
    assert loaded.default_model == "opus"


def test_global_config_store_removes_secret_fields(monkeypatch, tmp_path: Path):
    path = _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.store import load_global_config, save_global_config

    save_global_config({
        "default_model": "sonnet",
        "api_key": "sk-test",
        "default_tool_policy": {
            "credential": "secret",
            "require_approval_for_privileged_tools": True,
        },
    })
    raw = json.loads(path.read_text(encoding="utf-8"))
    loaded = load_global_config()

    assert "api_key" not in raw
    assert "credential" not in raw["default_tool_policy"]
    assert loaded.default_model == "sonnet"


def test_global_config_store_does_not_persist_secret_key_variants(monkeypatch, tmp_path: Path):
    path = _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.store import save_global_config

    save_global_config({
        "token": "t",
        "password": "p",
        "credential": "c",
        "private_key": "k",
        "default_mcp_policy": {"auth_token": "nested"},
    })
    raw_text = path.read_text(encoding="utf-8")

    assert "token" not in raw_text
    assert "password" not in raw_text
    assert "credential" not in raw_text
    assert "private_key" not in raw_text
    assert "auth_token" not in raw_text


def test_post_style_payload_cannot_persist_mcp_activation(monkeypatch, tmp_path: Path):
    path = _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.store import save_global_config

    save_global_config({
        "default_mcp_policy": {
            "active_mcps": ["gmail"],
            "mcp_enabled": True,
            "allow_configured_catalog_visibility": True,
        },
        "activate_mcp": "gmail",
    })
    raw = json.loads(path.read_text(encoding="utf-8"))

    assert "activate_mcp" not in raw
    assert "active_mcps" not in raw["default_mcp_policy"]
    assert "mcp_enabled" not in raw["default_mcp_policy"]
    assert raw["default_mcp_policy"]["allow_configured_catalog_visibility"] is True


def test_global_config_feeds_effective_config_as_user_global(monkeypatch, tmp_path: Path):
    _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.resolver import ConfigSource, resolve_effective_config
    from backend.apps.configuration.store import load_global_config, save_global_config

    save_global_config({"default_model": "opus"})
    result = resolve_effective_config(user_global=load_global_config().to_user_global_config())

    assert result.effective_config.values["default_model"] == "opus"
    assert result.source_map["default_model"] == ConfigSource.USER_GLOBAL


def test_effective_config_uses_defaults_when_no_overrides(monkeypatch, tmp_path: Path):
    _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.models import default_global_config
    from backend.apps.configuration.resolver import resolve_effective_config
    from backend.apps.configuration.store import load_global_config

    loaded = load_global_config()
    result = resolve_effective_config(
        system_default=default_global_config().to_user_global_config(),
        user_global=loaded.to_user_global_config(),
    )

    assert result.effective_config.values["default_model"] == "auto"
    assert result.effective_config.values["default_mcp_policy"]["activate_from_config_load"] is False
    assert result.effective_config.values["default_docs_update_policy"]["update_roadmap_every_closed_phases"] == 4


def test_global_override_changes_effective_config_hash(monkeypatch, tmp_path: Path):
    _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.models import default_global_config
    from backend.apps.configuration.resolver import resolve_effective_config
    from backend.apps.configuration.store import load_global_config, save_global_config

    first = resolve_effective_config(
        system_default=default_global_config().to_user_global_config(),
        user_global=load_global_config().to_user_global_config(),
    )
    save_global_config({"default_model": "opus"})
    second = resolve_effective_config(
        system_default=default_global_config().to_user_global_config(),
        user_global=load_global_config().to_user_global_config(),
    )

    assert first.effective_config_hash != second.effective_config_hash


def test_global_config_file_is_written_under_controlled_settings_path(monkeypatch, tmp_path: Path):
    path = _patch_store_path(monkeypatch, tmp_path)
    from backend.apps.configuration.store import global_config_path, save_global_config

    save_global_config({"default_language": "en"})

    assert Path(global_config_path()) == path
    assert path.parent.name == "settings"
    assert path.name == "global_config.json"


def test_legacy_or_invalid_global_config_file_does_not_break(monkeypatch, tmp_path: Path):
    path = _patch_store_path(monkeypatch, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-json", encoding="utf-8")
    from backend.apps.configuration.store import load_global_config

    config = load_global_config()

    assert config.default_model == "auto"
    assert config.schema_version == 1
