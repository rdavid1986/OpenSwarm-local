"""Read-only workspace intelligence helpers for Swarm/Output state.

PM-1 intentionally does not execute tools, mutate files, persist snapshots, or
create endpoints. It computes a fresh in-memory view of the current workspace
and compares it with saved Output files when available.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

from backend.apps.outputs.outputs import STATIC_OUTPUT_ALLOWED_FILES, STATIC_OUTPUT_REQUIRED_FILES


Freshness = Literal["fresh", "stale", "missing", "unknown"]


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value if isinstance(value, dict) else {}


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _safe_workspace_root() -> Path:
    return (Path.home() / ".openswarm" / "workspaces").resolve()


def _resolve_workspace_path(raw_path: str | None) -> tuple[Path | None, list[dict[str, Any]]]:
    if not raw_path:
        return None, [{"error": "workspace_path_missing"}]

    workspace = Path(raw_path).expanduser().resolve()
    allowed_root = _safe_workspace_root()
    try:
        workspace.relative_to(allowed_root)
    except ValueError:
        return workspace, [{"error": "workspace_outside_allowed_root", "workspace_path": str(workspace)}]
    return workspace, []


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _file_snapshot(
    workspace: Path,
    rel_path: str,
    *,
    expected_hash: str | None,
    has_reference: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    target = (workspace / rel_path).resolve()
    try:
        target.relative_to(workspace)
    except ValueError:
        return (
            {
                "path": rel_path,
                "exists": False,
                "size": None,
                "sha256": None,
                "mtime": None,
                "freshness": "missing",
            },
            {"error": "path_traversal_not_allowed", "path": rel_path},
        )

    if target.is_symlink():
        try:
            target.resolve().relative_to(workspace)
        except ValueError:
            return (
                {
                    "path": rel_path,
                    "exists": False,
                    "size": None,
                    "sha256": None,
                    "mtime": None,
                    "freshness": "missing",
                },
                {"error": "symlink_outside_workspace", "path": rel_path},
            )

    if not target.exists() or not target.is_file():
        return (
            {
                "path": rel_path,
                "exists": False,
                "size": None,
                "sha256": None,
                "mtime": None,
                "freshness": "missing",
            },
            None,
        )

    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    stat = target.stat()
    if expected_hash:
        freshness: Freshness = "fresh" if digest == expected_hash else "stale"
    elif has_reference:
        freshness = "stale"
    else:
        freshness = "unknown"

    return (
        {
            "path": rel_path,
            "exists": True,
            "size": len(raw),
            "sha256": digest,
            "mtime": stat.st_mtime,
            "freshness": freshness,
        },
        None,
    )


def _overall_freshness(files: list[dict[str, Any]], errors: list[dict[str, Any]]) -> Freshness:
    if any(error.get("error") in {"workspace_path_missing", "workspace_outside_allowed_root"} for error in errors):
        return "unknown"
    if any(error.get("error") == "workspace_not_found" for error in errors):
        return "missing"
    states = [str(item.get("freshness") or "unknown") for item in files]
    if any(state == "missing" for state in states):
        return "missing"
    if any(state == "stale" for state in states):
        return "stale"
    if states and all(state == "fresh" for state in states):
        return "fresh"
    return "unknown"


def _output_metadata(output: Any | None) -> dict[str, Any] | None:
    if output is None:
        return None
    data = _as_dict(output)
    return {
        "id": data.get("id"),
        "source_swarm_id": data.get("source_swarm_id"),
        "source_task_id": data.get("source_task_id"),
        "artifact_refs": list(data.get("artifact_refs") or []),
        "evidence_refs": list(data.get("evidence_refs") or []),
        "validation_status": data.get("validation_status"),
        "updated_at": data.get("updated_at"),
    }


def _collect_evidence_refs(swarm: Any | None, output: Any | None) -> list[str]:
    refs: list[Any] = []
    output_data = _as_dict(output)
    refs.extend(output_data.get("evidence_refs") or [])
    if swarm is None:
        return _dedupe(refs)

    for collection_name in ("evidence", "final_evidence"):
        for item in list(getattr(swarm, collection_name, []) or []):
            data = _as_dict(item)
            refs.append(data.get("id") or data.get("evidence_id") or data.get("evidence_ref") or data.get("tool_call_id"))
    return _dedupe(refs)


def _collect_artifacts(swarm: Any | None) -> list[dict[str, Any]]:
    if swarm is None:
        return []
    return [_as_dict(item) for item in list(getattr(swarm, "artifacts", []) or []) if _as_dict(item)]


def build_workspace_intelligence(
    *,
    swarm: Any | None = None,
    output: Any | None = None,
    workspace_path: str | None = None,
    allowed_files: set[str] | None = None,
) -> dict[str, Any]:
    """Return a read-only snapshot of workspace/output freshness.

    The helper fail-closed on workspace root violations: it reports an error and
    does not inspect file contents outside ``~/.openswarm/workspaces``.
    """

    output_data = _as_dict(output)
    workspace_raw = workspace_path or getattr(swarm, "workspace_path", None) or None
    workspace, errors = _resolve_workspace_path(str(workspace_raw) if workspace_raw else None)

    allowed = set(allowed_files or STATIC_OUTPUT_ALLOWED_FILES)
    reference_files = output_data.get("files") if isinstance(output_data.get("files"), dict) else {}
    expected_paths = set(allowed_files or STATIC_OUTPUT_REQUIRED_FILES)
    expected_paths.update(str(path) for path in reference_files.keys())

    files: list[dict[str, Any]] = []
    exists = False
    can_read_workspace = workspace is not None and not any(
        error.get("error") in {"workspace_path_missing", "workspace_outside_allowed_root"}
        for error in errors
    )

    if can_read_workspace:
        if workspace and workspace.is_dir():
            exists = True
            for child in sorted(workspace.iterdir(), key=lambda item: item.name):
                if child.name in allowed and child.is_file():
                    expected_paths.add(child.name)
                elif child.name in allowed and child.is_symlink():
                    expected_paths.add(child.name)
        else:
            errors.append({"error": "workspace_not_found", "workspace_path": str(workspace)})

    for rel_path in sorted(expected_paths):
        if rel_path not in allowed:
            errors.append({"error": "file_not_allowed", "path": rel_path})
            continue
        expected_content = reference_files.get(rel_path) if isinstance(reference_files, dict) else None
        expected_hash = _hash_text(expected_content) if isinstance(expected_content, str) else None
        has_reference = isinstance(reference_files, dict) and rel_path in reference_files
        if can_read_workspace and workspace and workspace.is_dir():
            snapshot, error = _file_snapshot(
                workspace,
                rel_path,
                expected_hash=expected_hash,
                has_reference=has_reference,
            )
        else:
            snapshot, error = (
                {
                    "path": rel_path,
                    "exists": False,
                    "size": None,
                    "sha256": None,
                    "mtime": None,
                    "freshness": "missing" if workspace_raw else "unknown",
                },
                None,
            )
        files.append(snapshot)
        if error:
            errors.append(error)

    return {
        "workspace_path": str(workspace) if workspace is not None else None,
        "exists": exists,
        "allowed_files": sorted(allowed),
        "files": files,
        "artifacts": _collect_artifacts(swarm),
        "evidence_refs": _collect_evidence_refs(swarm, output),
        "output": _output_metadata(output),
        "freshness": _overall_freshness(files, errors),
        "errors": errors,
    }
