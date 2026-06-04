"""Side-effect-free IDE theme/profile candidate contracts.

This module models VS Code/Cursor-like theme/profile imports as reviewable
candidates only. It never applies themes, installs extensions, copies assets,
enables permissions, or mutates settings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any


SUPPORTED_THEME_KINDS = {
    "color_theme",
    "icon_theme",
    "file_icon_theme",
    "product_icon_theme",
    "settings_profile",
    "unknown",
}

KNOWN_PLATFORMS = {
    "vscode",
    "cursor",
    "unknown",
}

DANGEROUS_SETTING_KEYS = {
    "terminal.integrated.env",
    "terminal.integrated.shellArgs",
    "terminal.integrated.defaultProfile",
    "security.workspace.trust.enabled",
    "extensions.autoUpdate",
    "extensions.autoCheckUpdates",
    "remote.SSH.configFile",
    "remote.SSH.path",
}

SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "bearer",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)


@dataclass(frozen=True)
class IDEThemeSourceAdapter:
    source_kind: str = "ide_theme_compat"
    adapter_kind: str = "ide_theme_source_adapter"
    detected_platform: str = "unknown"
    detected_kind: str = "unknown"
    source_uri: str = "unknown"
    source_hash: str = "unknown"
    source_name: str = "Untitled IDE Theme Candidate"
    source_license: str = "unknown"
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    can_apply_theme: bool = False
    can_install_extensions: bool = False
    can_copy_assets: bool = False
    can_mutate_settings: bool = False
    can_enable_permissions: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IDEThemeCandidate:
    source_kind: str = "ide_theme_compat"
    candidate_kind: str = "ide_theme_candidate"
    candidate_type: str = "IDEThemeCandidate"
    candidate_id: str = "ide-theme-candidate-unknown"
    title: str = "Untitled IDE Theme Candidate"
    detected_platform: str = "unknown"
    detected_kind: str = "unknown"
    source_uri: str = "unknown"
    source_hash: str = "unknown"
    source_license: str = "unknown"
    theme_refs: list[dict[str, Any]] = field(default_factory=list)
    icon_theme_refs: list[dict[str, Any]] = field(default_factory=list)
    product_icon_theme_refs: list[dict[str, Any]] = field(default_factory=list)
    settings_refs: dict[str, Any] = field(default_factory=dict)
    profile_refs: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    review_required: bool = True
    approval_required: bool = True

    can_apply_theme: bool = False
    can_install_extensions: bool = False
    can_copy_assets: bool = False
    can_mutate_settings: bool = False
    can_enable_permissions: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IDEThemeDiagnosticReport:
    source_kind: str = "ide_theme_compat"
    diagnostic_kind: str = "ide_theme_diagnostic_report"
    candidate_id: str = "ide-theme-candidate-unknown"
    status: str = "needs_review"
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    warning_count: int = 0
    error_count: int = 0

    can_apply_theme: bool = False
    can_install_extensions: bool = False
    can_copy_assets: bool = False
    can_mutate_settings: bool = False
    can_enable_permissions: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return {}


def _text(value: Any, *, fallback: str = "", limit: int = 400) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return text[:limit]


def _safe_json_loads(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_platform(value: Any, *, source_uri: str = "") -> str:
    raw = _text(value, fallback="").lower()
    uri = source_uri.lower()
    if "cursor" in raw or ".cursor" in uri or "cursor" in uri:
        return "cursor"
    if raw in {"vscode", "vs_code", "visual_studio_code"} or ".vscode" in uri or "code" in uri:
        return "vscode"
    return "unknown"


def _normalize_kind(value: Any, payload: dict[str, Any]) -> str:
    raw = _text(value, fallback="").lower().replace("-", "_").replace(" ", "_")
    if raw in SUPPORTED_THEME_KINDS:
        return raw

    if payload.get("colors") or payload.get("tokenColors") or payload.get("semanticTokenColors"):
        return "color_theme"
    if payload.get("iconDefinitions") or payload.get("fileExtensions") or payload.get("fileNames"):
        return "file_icon_theme"
    if payload.get("fonts") or payload.get("settings") or payload.get("extensions"):
        return "settings_profile"
    if payload.get("productIconDefinitions"):
        return "product_icon_theme"
    return "unknown"


def _normalize_refs(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []

    refs: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            ref = {
                "id": _text(item.get("id") or item.get("name") or f"ref-{index}", fallback=f"ref-{index}", limit=160),
                "label": _text(item.get("label") or item.get("name") or item.get("id") or f"Ref {index + 1}", fallback=f"Ref {index + 1}", limit=220),
                "path": _text(item.get("path") or item.get("uri") or item.get("source_uri"), fallback="", limit=600),
            }
        else:
            ref = {
                "id": f"ref-{index}",
                "label": _text(item, fallback=f"Ref {index + 1}", limit=220),
                "path": "",
            }
        refs.append(ref)
    return refs


def _extract_settings(payload: dict[str, Any]) -> dict[str, Any]:
    settings = payload.get("settings")
    if isinstance(settings, dict):
        return dict(settings)

    # Accept raw VS Code settings.json-like payload as settings profile candidate.
    known_settings_shape = any("." in str(key) for key in payload.keys())
    if known_settings_shape:
        return dict(payload)

    return {}


def _has_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in SECRET_KEY_MARKERS):
                return True
            if _has_secret_key(item):
                return True
    elif isinstance(value, list):
        return any(_has_secret_key(item) for item in value)
    return False


def _settings_risk_flags(settings: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    keys = {str(key) for key in settings.keys()}

    if any(key.startswith("terminal.integrated.env") for key in keys):
        flags.append("terminal_environment_settings")
    if any(key in DANGEROUS_SETTING_KEYS for key in keys):
        flags.append("sensitive_ide_setting")
    if any(key.startswith("remote.") for key in keys):
        flags.append("remote_access_related_setting")
    if _has_secret_key(settings):
        flags.append("possible_secret_material")

    return sorted(set(flags))


def build_ide_theme_source_adapter(input_data: dict[str, Any] | None = None) -> IDEThemeSourceAdapter:
    data = dict(input_data or {})
    content = _text(data.get("content"), fallback="", limit=200_000)
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else _safe_json_loads(content)

    source_uri = _text(data.get("source_uri") or data.get("path") or data.get("filename"), fallback="unknown", limit=600)
    source_hash = _text(data.get("source_hash"), fallback="", limit=160) or _hash_text(content or json.dumps(payload, sort_keys=True))
    platform = _normalize_platform(data.get("source_platform") or data.get("platform"), source_uri=source_uri)
    detected_kind = _normalize_kind(data.get("theme_kind") or data.get("kind") or data.get("type"), payload)

    warnings: list[str] = []
    if not content and not payload:
        warnings.append("empty_theme_source")
    if platform == "unknown":
        warnings.append("unknown_ide_platform")
    if detected_kind == "unknown":
        warnings.append("unknown_theme_candidate_kind")

    confidence = 0.25
    if platform != "unknown":
        confidence += 0.25
    if detected_kind != "unknown":
        confidence += 0.35
    if payload:
        confidence += 0.15

    return IDEThemeSourceAdapter(
        detected_platform=platform,
        detected_kind=detected_kind,
        source_uri=source_uri,
        source_hash=source_hash,
        source_name=_text(data.get("name") or payload.get("name"), fallback="Untitled IDE Theme Candidate", limit=220),
        source_license=_text(data.get("source_license") or payload.get("license"), fallback="unknown", limit=120),
        confidence=min(confidence, 1.0),
        warnings=warnings,
    )


def build_ide_theme_candidate(
    input_data: dict[str, Any] | None = None,
    adapter: IDEThemeSourceAdapter | dict[str, Any] | None = None,
) -> IDEThemeCandidate:
    data = dict(input_data or {})
    content = _text(data.get("content"), fallback="", limit=200_000)
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else _safe_json_loads(content)
    adapter_data = _dump(adapter) if adapter is not None else _dump(build_ide_theme_source_adapter(data))

    source_hash = _text(adapter_data.get("source_hash"), fallback="unknown", limit=160)
    title = _text(data.get("title") or data.get("name") or payload.get("name") or adapter_data.get("source_name"), fallback="Untitled IDE Theme Candidate", limit=220)
    settings = _extract_settings(payload or data)

    theme_refs = _normalize_refs(data.get("theme_refs") or payload.get("themes") or payload.get("contributes", {}).get("themes") if isinstance(payload.get("contributes"), dict) else None)
    icon_theme_refs = _normalize_refs(
        data.get("icon_theme_refs")
        or data.get("file_icon_theme_refs")
        or payload.get("iconThemes")
        or (payload.get("contributes", {}).get("iconThemes") if isinstance(payload.get("contributes"), dict) else None)
    )
    product_icon_theme_refs = _normalize_refs(
        data.get("product_icon_theme_refs")
        or payload.get("productIconThemes")
        or (payload.get("contributes", {}).get("productIconThemes") if isinstance(payload.get("contributes"), dict) else None)
    )

    if not theme_refs and adapter_data.get("detected_kind") == "color_theme" and (
        payload.get("colors") or payload.get("tokenColors") or payload.get("semanticTokenColors")
    ):
        theme_refs = [{
            "id": _text(payload.get("name") or title, fallback="color-theme", limit=160),
            "label": title,
            "path": _text(adapter_data.get("source_uri"), fallback="", limit=600),
        }]

    provenance = {
        "source_uri": adapter_data.get("source_uri") or "unknown",
        "source_hash": source_hash,
        "source_platform": adapter_data.get("detected_platform") or "unknown",
        "source_kind": adapter_data.get("detected_kind") or "unknown",
        "source_license": adapter_data.get("source_license") or "unknown",
        "source_author": _text(data.get("source_author") or payload.get("publisher"), fallback="unknown", limit=220),
    }

    return IDEThemeCandidate(
        candidate_id=f"ide-theme-{source_hash[:16] if source_hash != 'unknown' else 'unknown'}",
        title=title,
        detected_platform=_text(adapter_data.get("detected_platform"), fallback="unknown"),
        detected_kind=_text(adapter_data.get("detected_kind"), fallback="unknown"),
        source_uri=_text(adapter_data.get("source_uri"), fallback="unknown", limit=600),
        source_hash=source_hash,
        source_license=_text(adapter_data.get("source_license"), fallback="unknown", limit=120),
        theme_refs=theme_refs,
        icon_theme_refs=icon_theme_refs,
        product_icon_theme_refs=product_icon_theme_refs,
        settings_refs=settings,
        profile_refs=dict(data.get("profile_refs") or payload.get("profile") or {}),
        provenance=provenance,
    )


def build_ide_theme_diagnostic_report(candidate: IDEThemeCandidate | dict[str, Any]) -> IDEThemeDiagnosticReport:
    candidate_data = _dump(candidate)
    candidate_id = _text(candidate_data.get("candidate_id"), fallback="ide-theme-candidate-unknown")
    diagnostics: list[dict[str, Any]] = []
    risk_flags: list[str] = []
    required_actions: list[str] = []

    source_license = _text(candidate_data.get("source_license"), fallback="unknown").lower()
    settings = candidate_data.get("settings_refs") if isinstance(candidate_data.get("settings_refs"), dict) else {}

    if source_license in {"", "unknown", "none"}:
        risk_flags.append("unknown_license")
        required_actions.append("verify_theme_license_and_provenance")
        diagnostics.append({
            "level": "warning",
            "code": "unknown_license",
            "message": "Theme candidate has no verified license/provenance.",
        })

    setting_flags = _settings_risk_flags(settings)
    for flag in setting_flags:
        risk_flags.append(flag)

    if "possible_secret_material" in setting_flags:
        required_actions.append("remove_or_redact_secret_material")
        diagnostics.append({
            "level": "error",
            "code": "possible_secret_material",
            "message": "Settings candidate may contain secret material.",
        })

    if any(flag in setting_flags for flag in {"terminal_environment_settings", "sensitive_ide_setting", "remote_access_related_setting"}):
        required_actions.append("review_ide_settings_before_apply")
        diagnostics.append({
            "level": "warning",
            "code": "sensitive_settings_review_required",
            "message": "Settings candidate contains IDE settings that require human review.",
        })

    if not candidate_data.get("theme_refs") and not candidate_data.get("icon_theme_refs") and not candidate_data.get("product_icon_theme_refs") and not settings:
        risk_flags.append("empty_theme_candidate")
        required_actions.append("provide_theme_or_profile_metadata")
        diagnostics.append({
            "level": "error",
            "code": "empty_theme_candidate",
            "message": "Candidate has no theme, icon, product icon, or settings metadata.",
        })

    risk_flags = sorted(set(risk_flags))
    required_actions = sorted(set(required_actions))
    error_count = sum(1 for item in diagnostics if item.get("level") == "error")
    warning_count = sum(1 for item in diagnostics if item.get("level") == "warning")
    status = "blocked" if error_count else ("needs_review" if warning_count or risk_flags else "ready_for_review")

    return IDEThemeDiagnosticReport(
        candidate_id=candidate_id,
        status=status,
        diagnostics=diagnostics,
        risk_flags=risk_flags,
        required_actions=required_actions,
        warning_count=warning_count,
        error_count=error_count,
    )
