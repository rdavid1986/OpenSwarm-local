"""Side-effect-free project bootstrap profile contracts.

This module detects project stack markers, conventions, validation commands and
artifact-store mode without executing commands, writing files or mutating project
state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


PROJECT_BOOTSTRAP_PROFILE_VERSION = "openswarm.project_bootstrap_profile.v1"

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "private_key",
    "authorization",
    "cookie",
    "credential",
}

PACKAGE_MARKERS = {
    "package.json": "node",
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "poetry.lock": "poetry",
    "Pipfile": "pipenv",
}

FRAMEWORK_MARKERS = {
    "vite.config.ts": "vite",
    "vite.config.js": "vite",
    "next.config.js": "nextjs",
    "next.config.ts": "nextjs",
    "tsconfig.json": "typescript",
    "tailwind.config.js": "tailwind",
    "tailwind.config.ts": "tailwind",
    "pytest.ini": "pytest",
    "ruff.toml": "ruff",
    ".eslintrc": "eslint",
    ".eslintrc.js": "eslint",
    ".eslintrc.json": "eslint",
}

TEST_MARKERS = {
    "pytest.ini": "python -m pytest -q",
    "backend/tests": "python -m pytest -q backend/tests",
    "package.json": "npm test",
}

BUILD_MARKERS = {
    "package.json": "npm run build",
    "frontend/package.json": "npm --prefix frontend run build",
}

LINT_MARKERS = {
    "ruff.toml": "python -m ruff check .",
    ".eslintrc": "npm run lint",
    ".eslintrc.js": "npm run lint",
    ".eslintrc.json": "npm run lint",
}


@dataclass(frozen=True)
class ProjectStackProfile:
    source_kind: str = "project_bootstrap_profile"
    profile_kind: str = "project_stack_profile"
    detected_stacks: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    workspace_roots: list[str] = field(default_factory=list)
    conventions: list[str] = field(default_factory=list)
    markers_seen: list[str] = field(default_factory=list)
    missing_recommended_markers: list[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False


@dataclass(frozen=True)
class ProjectCommandContract:
    source_kind: str = "project_bootstrap_profile"
    command_kind: str = "project_test_build_lint_contract"
    test_commands: list[str] = field(default_factory=list)
    build_commands: list[str] = field(default_factory=list)
    lint_commands: list[str] = field(default_factory=list)
    package_manager: str = "unknown"
    commands_are_suggestions: bool = True
    execution_required: bool = False
    requires_user_approval: bool = True
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False


@dataclass(frozen=True)
class ProjectArtifactStoreModeDecision:
    source_kind: str = "project_bootstrap_profile"
    artifact_kind: str = "project_artifact_store_mode_decision"
    artifact_mode: str = "unknown"
    output_workspace_required: bool = True
    preview_required: bool = True
    diff_required: bool = True
    rollback_required: bool = True
    evidence_required: list[str] = field(default_factory=list)
    rationale: str = "unmeasured"
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False


@dataclass(frozen=True)
class ProjectBootstrapProfile:
    source_kind: str = "project_bootstrap_profile"
    bootstrap_kind: str = "project_bootstrap_profile"
    stack_profile: dict[str, Any] = field(default_factory=dict)
    command_contract: dict[str, Any] = field(default_factory=dict)
    artifact_decision: dict[str, Any] = field(default_factory=dict)
    summary: str = "Project bootstrap profile prepared without execution."
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_execute: bool = False
    can_write_files: bool = False
    can_run_tests: bool = False
    can_run_build: bool = False
    can_run_lint: bool = False


def dump_project_bootstrap_profile(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dataclass_fields__"):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return _safe(dict(value))
    return {"source_kind": "project_bootstrap_profile", "value": _text(value)}


def _text(value: Any, fallback: str = "", limit: int = 600) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return text[:limit]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]
    result: list[str] = []
    for item in raw:
        text = _text(item, limit=240)
        if text and text not in result:
            result.append(text)
    return result[:120]


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in SENSITIVE_KEYS):
                safe[key_text] = "[redacted]"
            else:
                safe[key_text] = _safe(item)
        return safe
    if isinstance(value, list):
        return [_safe(item) for item in value[:120]]
    if isinstance(value, tuple):
        return [_safe(item) for item in list(value)[:120]]
    if isinstance(value, str):
        return value[:2000]
    return value


def _normalize_marker(value: str) -> str:
    marker = value.replace("\\", "/").strip().lstrip("./")
    return marker


def _collect_markers(markers: list[Any] | None = None, *, files: list[Any] | None = None, root_markers: dict[str, Any] | None = None) -> list[str]:
    found: list[str] = []

    for marker in _as_list(markers):
        found.append(_normalize_marker(marker))

    for file in files or []:
        if isinstance(file, dict):
            name = _text(file.get("path") or file.get("name"))
        else:
            name = _text(file)
        if name:
            found.append(_normalize_marker(name))

    for marker, exists in (root_markers or {}).items():
        if exists:
            found.append(_normalize_marker(str(marker)))

    normalized: list[str] = []
    for marker in found:
        if marker and marker not in normalized:
            normalized.append(marker)
    return normalized


def _has_marker(markers: list[str], marker: str) -> bool:
    marker = marker.lower()
    return any(item.lower() == marker or item.lower().endswith("/" + marker) for item in markers)


def _has_path(markers: list[str], path: str) -> bool:
    path = path.lower().strip("/")
    return any(item.lower().strip("/") == path or item.lower().strip("/").endswith("/" + path) for item in markers)


def build_project_stack_profile(
    markers: list[Any] | None = None,
    *,
    files: list[Any] | None = None,
    root_markers: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProjectStackProfile:
    marker_list = _collect_markers(markers, files=files, root_markers=root_markers)
    lowered = [marker.lower() for marker in marker_list]

    stacks: list[str] = []
    package_managers: list[str] = []
    frameworks: list[str] = []
    conventions: list[str] = []
    warnings: list[str] = []
    required: list[str] = []

    for marker, stack in PACKAGE_MARKERS.items():
        if _has_marker(marker_list, marker):
            if stack in {"npm", "pnpm", "yarn", "poetry", "pipenv"}:
                package_managers.append(stack)
            else:
                stacks.append(stack)

    if _has_marker(marker_list, "package.json"):
        stacks.append("node")
        if not any(pm in package_managers for pm in {"npm", "pnpm", "yarn"}):
            package_managers.append("npm")
    if _has_path(marker_list, "frontend/package.json"):
        stacks.append("frontend")
        package_managers.append("npm")
    if _has_path(marker_list, "backend") or any(item.startswith("backend/") for item in lowered):
        stacks.append("backend")
    if _has_path(marker_list, "backend/tests") or any("backend/tests" in item for item in lowered):
        frameworks.append("pytest")
        conventions.append("backend_tests")
    if _has_path(marker_list, "frontend") or any(item.startswith("frontend/") for item in lowered):
        stacks.append("frontend")

    for marker, framework in FRAMEWORK_MARKERS.items():
        if _has_marker(marker_list, marker):
            frameworks.append(framework)

    if _has_marker(marker_list, "package-lock.json"):
        package_managers.append("npm")
    if _has_marker(marker_list, "pnpm-lock.yaml"):
        package_managers.append("pnpm")
    if _has_marker(marker_list, "yarn.lock"):
        package_managers.append("yarn")

    if _has_marker(marker_list, "AGENTS.md"):
        conventions.append("agents_md")
    if _has_marker(marker_list, ".github/copilot-instructions.md"):
        conventions.append("copilot_instructions")

    if not marker_list:
        warnings.append("no_project_markers_provided")
        required.append("provide_project_root_markers")
    if "node" in stacks and not any(pm in package_managers for pm in {"npm", "pnpm", "yarn"}):
        warnings.append("node_package_manager_unknown")
        required.append("confirm_node_package_manager")
    if "python" in stacks and "pytest" not in frameworks:
        warnings.append("python_test_framework_unknown")
        required.append("confirm_python_test_command")

    confidence = 0.15
    if marker_list:
        confidence += 0.25
    if stacks:
        confidence += 0.25
    if package_managers:
        confidence += 0.15
    if frameworks:
        confidence += 0.15
    if conventions:
        confidence += 0.05

    workspace_roots = []
    if "backend" in stacks:
        workspace_roots.append("backend")
    if "frontend" in stacks:
        workspace_roots.append("frontend")
    if not workspace_roots and marker_list:
        workspace_roots.append(".")

    return ProjectStackProfile(
        detected_stacks=sorted(set(stacks)),
        frameworks=sorted(set(frameworks)),
        package_managers=sorted(set(package_managers)),
        workspace_roots=workspace_roots,
        conventions=sorted(set(conventions)),
        markers_seen=marker_list,
        missing_recommended_markers=[],
        confidence=round(min(confidence, 1.0), 3),
        warnings=warnings,
        required_actions=required,
    )


def build_project_command_contract(stack_profile: ProjectStackProfile | dict[str, Any]) -> ProjectCommandContract:
    data = asdict(stack_profile) if hasattr(stack_profile, "__dataclass_fields__") else dict(stack_profile or {})
    markers = _as_list(data.get("markers_seen"))
    package_managers = _as_list(data.get("package_managers"))
    frameworks = _as_list(data.get("frameworks"))
    stacks = _as_list(data.get("detected_stacks"))

    test_commands: list[str] = []
    build_commands: list[str] = []
    lint_commands: list[str] = []
    warnings: list[str] = []
    required: list[str] = []

    if _has_path(markers, "backend/tests") or "pytest" in frameworks:
        test_commands.append("python -m pytest -q backend/tests")
    elif "python" in stacks or "backend" in stacks:
        test_commands.append("python -m pytest -q")
        warnings.append("python_test_command_inferred")
        required.append("confirm_python_test_command")

    if _has_path(markers, "frontend/package.json"):
        build_commands.append("npm --prefix frontend run build")
        test_commands.append("npm --prefix frontend test -- --run")
        lint_commands.append("npm --prefix frontend run lint")
    elif _has_marker(markers, "package.json") or "node" in stacks:
        build_commands.append("npm run build")
        test_commands.append("npm test")
        lint_commands.append("npm run lint")

    if "ruff" in frameworks:
        lint_commands.append("python -m ruff check .")
    if "eslint" in frameworks and "npm run lint" not in lint_commands and "npm --prefix frontend run lint" not in lint_commands:
        lint_commands.append("npm run lint")

    if not test_commands:
        warnings.append("test_command_unknown")
        required.append("confirm_test_command")
    if not build_commands:
        warnings.append("build_command_unknown")
        required.append("confirm_build_command")
    if not lint_commands:
        warnings.append("lint_command_unknown")
        required.append("confirm_lint_command")

    package_manager = package_managers[0] if package_managers else "unknown"

    return ProjectCommandContract(
        test_commands=list(dict.fromkeys(test_commands)),
        build_commands=list(dict.fromkeys(build_commands)),
        lint_commands=list(dict.fromkeys(lint_commands)),
        package_manager=package_manager,
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(required)),
    )


def decide_project_artifact_store_mode(
    stack_profile: ProjectStackProfile | dict[str, Any],
    command_contract: ProjectCommandContract | dict[str, Any] | None = None,
) -> ProjectArtifactStoreModeDecision:
    stack = asdict(stack_profile) if hasattr(stack_profile, "__dataclass_fields__") else dict(stack_profile or {})
    commands = asdict(command_contract) if hasattr(command_contract, "__dataclass_fields__") else dict(command_contract or {})
    stacks = set(_as_list(stack.get("detected_stacks")))
    frameworks = set(_as_list(stack.get("frameworks")))
    required: list[str] = []
    warnings: list[str] = []

    if {"frontend", "node"} & stacks or {"vite", "nextjs"} & frameworks:
        mode = "output_workspace_with_preview"
        rationale = "Frontend or app stack detected; preview/diff/rollback evidence should be available before acceptance."
    elif "backend" in stacks or "python" in stacks:
        mode = "workspace_patch_with_tests"
        rationale = "Backend/Python stack detected; patch evidence and test commands should gate completion."
    elif stack.get("confidence", 0.0) < 0.4:
        mode = "manual_review"
        rationale = "Project markers are insufficient; manual review is required before choosing artifact storage."
        warnings.append("artifact_mode_low_confidence")
        required.append("confirm_artifact_store_mode")
    else:
        mode = "workspace_patch_with_evidence"
        rationale = "Generic project markers detected; require diff and evidence before applying changes."

    if commands and commands.get("required_actions"):
        required.extend(_as_list(commands.get("required_actions")))

    return ProjectArtifactStoreModeDecision(
        artifact_mode=mode,
        evidence_required=["stack_profile", "command_contract", "diff_summary", "validation_result"],
        rationale=rationale,
        warnings=list(dict.fromkeys(warnings)),
        required_actions=list(dict.fromkeys(required)),
    )


def build_project_bootstrap_profile(
    markers: list[Any] | None = None,
    *,
    files: list[Any] | None = None,
    root_markers: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProjectBootstrapProfile:
    stack = build_project_stack_profile(markers, files=files, root_markers=root_markers, metadata=metadata)
    commands = build_project_command_contract(stack)
    artifact = decide_project_artifact_store_mode(stack, commands)

    warnings = list(dict.fromkeys(stack.warnings + commands.warnings + artifact.warnings))
    required_actions = list(dict.fromkeys(stack.required_actions + commands.required_actions + artifact.required_actions))

    stacks = ", ".join(stack.detected_stacks or ["unknown"])
    summary = f"Project bootstrap profile prepared for stack: {stacks}."

    return ProjectBootstrapProfile(
        stack_profile=_safe(asdict(stack)),
        command_contract=_safe(asdict(commands)),
        artifact_decision=_safe(asdict(artifact)),
        summary=summary,
        warnings=warnings,
        required_actions=required_actions,
    )
