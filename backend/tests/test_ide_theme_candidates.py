from backend.apps.theme_compat.ide_theme_candidates import (
    build_ide_theme_candidate,
    build_ide_theme_diagnostic_report,
    build_ide_theme_source_adapter,
)


def assert_no_side_effects(value):
    assert getattr(value, "can_apply_theme", False) is False
    assert getattr(value, "can_install_extensions", False) is False
    assert getattr(value, "can_copy_assets", False) is False
    assert getattr(value, "can_mutate_settings", False) is False
    assert getattr(value, "can_enable_permissions", False) is False


def test_builds_vscode_color_theme_candidate_without_side_effects():
    adapter = build_ide_theme_source_adapter({
        "path": ".vscode/extensions/example/theme.json",
        "payload": {
            "name": "Example Dark",
            "colors": {"editor.background": "#111111"},
            "license": "MIT",
        },
    })
    candidate = build_ide_theme_candidate({"payload": {"name": "Example Dark", "colors": {"editor.background": "#111111"}, "license": "MIT"}}, adapter)

    assert adapter.detected_platform == "vscode"
    assert adapter.detected_kind == "color_theme"
    assert adapter.confidence > 0.7
    assert candidate.title == "Example Dark"
    assert candidate.detected_kind == "color_theme"
    assert candidate.review_required is True
    assert candidate.approval_required is True
    assert_no_side_effects(adapter)
    assert_no_side_effects(candidate)


def test_builds_cursor_icon_theme_candidate_with_provenance():
    adapter = build_ide_theme_source_adapter({
        "path": ".cursor/themes/material-icons/package.json",
        "payload": {
            "name": "Material Icons Candidate",
            "contributes": {
                "iconThemes": [{"id": "material-icon-theme", "label": "Material Icon Theme", "path": "./icons.json"}]
            },
            "license": "MIT",
        },
    })
    candidate = build_ide_theme_candidate({"payload": {
        "name": "Material Icons Candidate",
        "contributes": {
            "iconThemes": [{"id": "material-icon-theme", "label": "Material Icon Theme", "path": "./icons.json"}]
        },
        "license": "MIT",
    }}, adapter)

    assert adapter.detected_platform == "cursor"
    assert candidate.icon_theme_refs[0]["id"] == "material-icon-theme"
    assert candidate.provenance["source_platform"] == "cursor"
    assert candidate.provenance["source_license"] == "MIT"
    assert_no_side_effects(candidate)


def test_diagnostic_requires_license_review_for_unknown_license():
    candidate = build_ide_theme_candidate({
        "path": ".vscode/theme.json",
        "payload": {"name": "No License Theme", "colors": {"editor.background": "#000000"}},
    })
    report = build_ide_theme_diagnostic_report(candidate)

    assert report.status == "needs_review"
    assert "unknown_license" in report.risk_flags
    assert "verify_theme_license_and_provenance" in report.required_actions
    assert_no_side_effects(report)


def test_diagnostic_blocks_secret_like_settings():
    candidate = build_ide_theme_candidate({
        "path": ".vscode/settings.json",
        "payload": {
            "workbench.colorTheme": "Example",
            "myExtension.api_key": "secret",
        },
        "source_license": "MIT",
    })
    report = build_ide_theme_diagnostic_report(candidate)

    assert report.status == "blocked"
    assert "possible_secret_material" in report.risk_flags
    assert "remove_or_redact_secret_material" in report.required_actions
    assert_no_side_effects(report)


def test_diagnostic_flags_terminal_and_remote_settings_for_review():
    candidate = build_ide_theme_candidate({
        "path": ".vscode/settings.json",
        "payload": {
            "terminal.integrated.env.windows": {"NODE_ENV": "development"},
            "remote.SSH.path": "ssh",
        },
        "source_license": "MIT",
    })
    report = build_ide_theme_diagnostic_report(candidate)

    assert report.status == "needs_review"
    assert "terminal_environment_settings" in report.risk_flags
    assert "remote_access_related_setting" in report.risk_flags
    assert "review_ide_settings_before_apply" in report.required_actions
    assert_no_side_effects(report)


def test_empty_candidate_is_blocked():
    candidate = build_ide_theme_candidate({"payload": {}, "source_license": "MIT"})
    report = build_ide_theme_diagnostic_report(candidate)

    assert report.status == "blocked"
    assert "empty_theme_candidate" in report.risk_flags
    assert "provide_theme_or_profile_metadata" in report.required_actions
    assert_no_side_effects(report)
