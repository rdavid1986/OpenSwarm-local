from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.theme_compat import theme_compat


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(theme_compat.router, prefix="/api/theme-compat")
    return TestClient(app)


def test_ide_theme_preview_endpoint_is_side_effect_free():
    client = _client()

    response = client.post(
        "/api/theme-compat/ide-theme/preview",
        json={
            "path": ".vscode/themes/example-dark.json",
            "payload": {
                "name": "Example Dark",
                "colors": {"editor.background": "#111111"},
                "license": "MIT",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["side_effect_free"] is True
    assert data["can_apply_theme"] is False
    assert data["can_install_extensions"] is False
    assert data["can_copy_assets"] is False
    assert data["can_mutate_settings"] is False
    assert data["can_enable_permissions"] is False

    assert data["adapter"]["detected_platform"] == "vscode"
    assert data["candidate"]["detected_kind"] == "color_theme"
    assert data["candidate"]["review_required"] is True
    assert data["candidate"]["approval_required"] is True
    assert data["diagnostic_report"]["status"] == "ready_for_review"


def test_ide_theme_preview_endpoint_blocks_secret_like_settings():
    client = _client()

    response = client.post(
        "/api/theme-compat/ide-theme/preview",
        json={
            "path": ".cursor/settings.json",
            "payload": {
                "workbench.colorTheme": "Example",
                "myExtension.api_key": "secret",
            },
            "source_license": "MIT",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["side_effect_free"] is True
    assert data["candidate"]["detected_platform"] == "cursor"
    assert data["diagnostic_report"]["status"] == "blocked"
    assert "possible_secret_material" in data["diagnostic_report"]["risk_flags"]
    assert "remove_or_redact_secret_material" in data["diagnostic_report"]["required_actions"]


def test_ide_theme_preview_endpoint_handles_empty_payload_as_reviewable_error():
    client = _client()

    response = client.post("/api/theme-compat/ide-theme/preview", json={})

    assert response.status_code == 200
    data = response.json()

    assert data["side_effect_free"] is True
    assert data["diagnostic_report"]["status"] == "blocked"
    assert "empty_theme_candidate" in data["diagnostic_report"]["risk_flags"]
