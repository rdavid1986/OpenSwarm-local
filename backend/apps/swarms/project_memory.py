"""Side-effect-free Project Memory Manifest helpers.

PM-BASE defines a small, persistible manifest shape that callers can build
from already-available Swarm/Output state. These helpers never query storage,
call providers, execute tools, mutate SwarmState, or write files.
"""

from __future__ import annotations

import json
from typing import Any


MISSING = "missing"
MAX_TEXT = 800
MAX_LIST_ITEMS = 24
MAX_DICT_ITEMS = 32

MANIFEST_KEYS = [
    "project_id",
    "swarm_id",
    "workspace_id",
    "current_goal",
    "decisions",
    "outputs",
    "accepted_iterations",
    "candidate_iterations",
    "artifacts",
    "evidence",
    "constraints",
    "open_questions",
    "last_updated_source",
]


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _as_text(value)
        if text:
            return text[:MAX_TEXT]
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_attr(value: Any, name: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            return value
    if hasattr(value, "dict"):
        try:
            return value.dict()
        except Exception:
            return value
    return value


def normalize_project_memory_entry(value: Any) -> Any:
    """Return a JSON-safe, bounded representation of caller-provided memory.

    Scalars are preserved as values, dicts keep their provided keys, and lists
    are bounded. This function normalizes only what exists; it does not invent
    outputs, evidence, artifacts, decisions, or ids.
    """

    value = _model_dump(value)
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value.strip()[:MAX_TEXT]
    if isinstance(value, (list, tuple, set)):
        return [normalize_project_memory_entry(item) for item in list(value)[:MAX_LIST_ITEMS]]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for index, key in enumerate(sorted(value.keys(), key=lambda item: str(item))):
            if index >= MAX_DICT_ITEMS:
                normalized["__truncated__"] = True
                break
            normalized[str(key)[:160]] = normalize_project_memory_entry(value.get(key))
        return normalized
    return _as_text(value)[:MAX_TEXT]


def _entry_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    raw_items = value if isinstance(value, (list, tuple, set)) else [value]
    entries: list[dict[str, Any]] = []
    for item in list(raw_items)[:MAX_LIST_ITEMS]:
        normalized = normalize_project_memory_entry(item)
        if normalized is None:
            continue
        if isinstance(normalized, dict):
            entries.append(normalized)
        else:
            entries.append({"value": normalized})
    return entries


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    for item in list(raw_items)[:MAX_LIST_ITEMS]:
        text = _as_text(item)
        if text:
            result.append(text[:MAX_TEXT])
    return result


def _derive_final_result(value: Any) -> dict[str, Any]:
    final_result = _read_attr(value, "final_result")
    return _as_dict(normalize_project_memory_entry(final_result))


def build_project_memory_manifest(
    *,
    project_id: str | None = None,
    swarm_id: str | None = None,
    workspace_id: str | None = None,
    current_goal: str | None = None,
    decisions: list[dict[str, Any]] | None = None,
    outputs: list[dict[str, Any]] | None = None,
    accepted_iterations: list[dict[str, Any]] | None = None,
    candidate_iterations: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    constraints: list[str] | None = None,
    open_questions: list[str] | None = None,
    last_updated_source: str | None = None,
    swarm: Any = None,
    final_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the formal Project Memory Manifest from caller-provided state.

    `swarm` and `final_result` are optional convenience inputs. They are read
    only in-memory and only for fields that already exist on the object/dict.
    No storage lookup or persistence happens here.
    """

    resolved_final_result = _as_dict(normalize_project_memory_entry(final_result)) or _derive_final_result(swarm)
    output_bridge = _as_dict(resolved_final_result.get("output_bridge"))

    manifest = {
        "project_id": _first_text(project_id, _read_attr(swarm, "project_id"), _read_attr(swarm, "dashboard_id")),
        "swarm_id": _first_text(swarm_id, _read_attr(swarm, "id")),
        "workspace_id": _first_text(workspace_id, _read_attr(swarm, "workspace_id"), output_bridge.get("workspace_id")),
        "current_goal": _first_text(
            current_goal,
            _read_attr(swarm, "user_prompt"),
            _read_attr(swarm, "title"),
            resolved_final_result.get("summary"),
        ),
        "decisions": _entry_list(decisions if decisions is not None else _read_attr(swarm, "decisions")),
        "outputs": _entry_list(outputs),
        "accepted_iterations": _entry_list(accepted_iterations),
        "candidate_iterations": _entry_list(candidate_iterations),
        "artifacts": _entry_list(artifacts if artifacts is not None else _read_attr(swarm, "artifacts")),
        "evidence": _entry_list(evidence if evidence is not None else _read_attr(swarm, "evidence")),
        "constraints": _text_list(constraints),
        "open_questions": _text_list(open_questions),
        "last_updated_source": _first_text(last_updated_source),
    }
    return {key: manifest[key] for key in MANIFEST_KEYS}


def _manifest_kwargs(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = _as_dict(value)
    return {key: raw.get(key) for key in MANIFEST_KEYS if key in raw}


def summarize_project_memory_manifest(manifest: dict[str, Any] | None) -> str:
    """Return a concise, safe textual summary of the manifest."""

    normalized = build_project_memory_manifest(**_manifest_kwargs(manifest))
    counts = {
        "decisions": len(normalized["decisions"]),
        "outputs": len(normalized["outputs"]),
        "accepted_iterations": len(normalized["accepted_iterations"]),
        "candidate_iterations": len(normalized["candidate_iterations"]),
        "artifacts": len(normalized["artifacts"]),
        "evidence": len(normalized["evidence"]),
        "constraints": len(normalized["constraints"]),
        "open_questions": len(normalized["open_questions"]),
    }
    goal = normalized.get("current_goal") or MISSING
    return "\n".join(
        [
            "Project Memory Manifest summary:",
            f"- project_id: {normalized.get('project_id') or MISSING}",
            f"- swarm_id: {normalized.get('swarm_id') or MISSING}",
            f"- workspace_id: {normalized.get('workspace_id') or MISSING}",
            f"- current_goal: {goal}",
            "- counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()),
        ]
    )


def build_project_memory_prompt(manifest: dict[str, Any] | None) -> str:
    """Render project memory for model prompts with explicit missing semantics."""

    normalized = build_project_memory_manifest(**_manifest_kwargs(manifest))
    return "\n".join(
        [
            "OpenSwarm Project Memory Manifest:",
            "- This is caller-provided project memory only; do not invent missing memory.",
            "- Treat null as missing and [] as empty.",
            "- Outputs, artifacts, evidence, and iterations exist only if listed below.",
            json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True),
        ]
    )


def _collect_refs(items: Any, *keys: str) -> list[str]:
    refs: list[str] = []
    for item in _entry_list(items):
        for key in keys:
            text = _first_text(item.get(key))
            if text and text not in refs:
                refs.append(text)
    return refs


def extract_project_memory_refs(manifest: dict[str, Any] | None) -> dict[str, list[str]]:
    """Extract stable ids from a manifest without inferring absent refs."""

    normalized = build_project_memory_manifest(**_manifest_kwargs(manifest))
    return {
        "decision_ids": _collect_refs(normalized["decisions"], "decision_id", "id"),
        "output_ids": _collect_refs(normalized["outputs"], "output_id", "id"),
        "accepted_iteration_ids": _collect_refs(normalized["accepted_iterations"], "iteration_id", "id"),
        "candidate_iteration_ids": _collect_refs(normalized["candidate_iterations"], "candidate_iteration_id", "iteration_id", "id"),
        "artifact_ids": _collect_refs(normalized["artifacts"], "artifact_id", "id"),
        "evidence_ids": _collect_refs(normalized["evidence"], "evidence_id", "id"),
    }
