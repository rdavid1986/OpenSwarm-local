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


def _source_dict(source: Any) -> dict[str, Any]:
    return _as_dict(normalize_project_memory_entry(source))


def _nested_dict(source: Any, key: str) -> dict[str, Any]:
    return _as_dict(normalize_project_memory_entry(_read_attr(source, key)))


def _final_result_from_source(source: Any) -> dict[str, Any]:
    nested = _nested_dict(source, "final_result")
    if nested:
        return nested
    data = _source_dict(source)
    if isinstance(data.get("final_result"), dict):
        return data["final_result"]
    return data


def _project_intake_from_source(source: Any, final_result: dict[str, Any] | None = None) -> dict[str, Any]:
    nested = _nested_dict(source, "project_intake_state")
    if nested:
        return nested
    final_result = final_result or _final_result_from_source(source)
    return _as_dict(final_result.get("project_intake_state"))


def _implementation_state_from_source(source: Any, final_result: dict[str, Any] | None = None) -> dict[str, Any]:
    nested = _nested_dict(source, "implementation_state")
    if nested:
        return nested
    final_result = final_result or _final_result_from_source(source)
    return _as_dict(final_result.get("implementation_state"))


def _output_bridge_from_source(source: Any, final_result: dict[str, Any] | None = None) -> dict[str, Any]:
    nested = _nested_dict(source, "output_bridge")
    if nested:
        return nested
    final_result = final_result or _final_result_from_source(source)
    bridge = _as_dict(final_result.get("output_bridge"))
    if bridge:
        return bridge
    implementation_state = _implementation_state_from_source(source, final_result)
    return _as_dict(implementation_state.get("output_bridge"))


def _generated_plan_from_source(source: Any, final_result: dict[str, Any] | None = None) -> dict[str, Any]:
    intake_state = _project_intake_from_source(source, final_result)
    plan = _as_dict(intake_state.get("generated_plan"))
    if plan:
        return plan
    final_result = final_result or _final_result_from_source(source)
    return _as_dict(final_result.get("generated_plan"))


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        marker = json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(entry)
        if len(result) >= MAX_LIST_ITEMS:
            break
    return result


def _candidate_iterations_from_source(source: Any) -> list[dict[str, Any]]:
    data = _source_dict(source)
    candidates = _read_attr(source, "candidate_iterations")
    if candidates is None:
        candidates = data.get("candidate_iterations")
    if candidates is None:
        candidates = _read_attr(source, "iterations")
    if candidates is None:
        candidates = data.get("iterations")
    if candidates is None:
        candidates = _read_attr(source, "output_iterations")
    if candidates is None:
        candidates = data.get("output_iterations")
    return [
        entry for entry in _entry_list(candidates)
        if _as_text(entry.get("status")).lower() == "candidate"
        or entry.get("candidate_iteration_id")
        or entry.get("candidate_workspace_path")
    ]


def _accepted_iterations_from_source(source: Any) -> list[dict[str, Any]]:
    data = _source_dict(source)
    accepted = _read_attr(source, "accepted_iterations")
    if accepted is not None:
        return _entry_list(accepted)
    accepted = data.get("accepted_iterations")
    if accepted is not None:
        return _entry_list(accepted)
    iterations = _read_attr(source, "iterations")
    if iterations is None:
        iterations = data.get("iterations")
    if iterations is None:
        iterations = _read_attr(source, "output_iterations")
    if iterations is None:
        iterations = data.get("output_iterations")
    return [
        entry for entry in _entry_list(iterations)
        if _as_text(entry.get("status")).lower() in {"accepted", "restored", "applied"}
    ]


def _output_id_from_bridge(output_bridge: dict[str, Any]) -> str | None:
    metadata = _as_dict(output_bridge.get("metadata"))
    return _first_text(output_bridge.get("output_id"), metadata.get("output_id"))


def extract_project_decisions(source: Any) -> list[dict[str, Any]]:
    """Extract decision-like memory from provided swarm/final_result data."""

    if source is None:
        return []
    final_result = _final_result_from_source(source)
    intake_state = _project_intake_from_source(source, final_result)
    generated_plan = _generated_plan_from_source(source, final_result)
    entries: list[dict[str, Any]] = []

    entries.extend(_entry_list(_read_attr(source, "decisions")))
    entries.extend(_entry_list(final_result.get("decisions")))

    if generated_plan:
        entries.append({"source": "generated_plan", "kind": "plan", "value": generated_plan})

    skipped_questions = intake_state.get("skipped_questions")
    if skipped_questions:
        entries.append({"source": "project_intake_state", "kind": "skipped_questions", "value": _text_list(skipped_questions)})

    plan_summary = _first_text(generated_plan.get("summary"), final_result.get("summary"))
    if plan_summary:
        entries.append({"source": "plan_summary", "kind": "summary", "value": plan_summary})

    return _dedupe_entries(_entry_list(entries))


def extract_project_outputs(source: Any) -> list[dict[str, Any]]:
    """Extract Output refs only when present in provided data."""

    if source is None:
        return []
    final_result = _final_result_from_source(source)
    output_bridge = _output_bridge_from_source(source, final_result)
    data = _source_dict(source)
    entries = _entry_list(_read_attr(source, "outputs"))
    if not entries:
        entries = _entry_list(data.get("outputs"))

    output_id = _output_id_from_bridge(output_bridge) or _first_text(final_result.get("output_id"))
    if output_id:
        metadata = _as_dict(output_bridge.get("metadata"))
        entry = {
            "source": "output_bridge" if output_bridge else "final_result",
            "output_id": output_id,
            "status": _first_text(output_bridge.get("status"), final_result.get("status")),
        }
        workspace_id = _first_text(output_bridge.get("workspace_id"), metadata.get("workspace_id"), final_result.get("workspace_id"))
        if workspace_id:
            entry["workspace_id"] = workspace_id
        validation_errors = output_bridge.get("validation_errors")
        if validation_errors:
            entry["validation_errors"] = normalize_project_memory_entry(validation_errors)
        if metadata:
            entry["metadata"] = metadata
        entries.append(entry)

    return _dedupe_entries(_entry_list(entries))


def extract_project_iterations(source: Any) -> dict[str, list[dict[str, Any]]]:
    """Extract accepted/candidate iterations only if present in the source."""

    if source is None:
        return {"accepted_iterations": [], "candidate_iterations": []}
    return {
        "accepted_iterations": _dedupe_entries(_accepted_iterations_from_source(source)),
        "candidate_iterations": _dedupe_entries(_candidate_iterations_from_source(source)),
    }


def extract_project_artifacts(source: Any) -> list[dict[str, Any]]:
    """Extract artifacts from source/final_result when explicitly present."""

    if source is None:
        return []
    final_result = _final_result_from_source(source)
    entries: list[dict[str, Any]] = []
    entries.extend(_entry_list(_read_attr(source, "artifacts")))
    entries.extend(_entry_list(final_result.get("artifacts")))
    artifact = final_result.get("artifact")
    if artifact:
        entries.extend(_entry_list(artifact))
    return _dedupe_entries(entries)


def extract_project_evidence(source: Any) -> list[dict[str, Any]]:
    """Extract evidence/claim_guard only if present in provided data."""

    if source is None:
        return []
    final_result = _final_result_from_source(source)
    entries: list[dict[str, Any]] = []
    entries.extend(_entry_list(_read_attr(source, "evidence")))
    entries.extend(_entry_list(_read_attr(source, "final_evidence")))
    entries.extend(_entry_list(final_result.get("evidence")))
    entries.extend(_entry_list(final_result.get("final_evidence")))
    claim_guard = _as_dict(final_result.get("claim_guard"))
    if claim_guard:
        entries.append({"source": "claim_guard", "kind": "claim_guard", "value": claim_guard})
    return _dedupe_entries(entries)


def extract_project_constraints(source: Any) -> list[str]:
    """Extract explicit project constraints from intake/generated plan/context."""

    if source is None:
        return []
    final_result = _final_result_from_source(source)
    intake_state = _project_intake_from_source(source, final_result)
    generated_plan = _generated_plan_from_source(source, final_result)
    available_context = _as_dict(_read_attr(source, "available_context"))
    answers = _as_dict(intake_state.get("answers"))
    constraints: list[str] = []
    constraints.extend(_text_list(_read_attr(source, "constraints")))
    constraints.extend(_text_list(final_result.get("constraints")))
    constraints.extend(_text_list(available_context.get("constraints")))
    constraints.extend(_text_list(generated_plan.get("technical_constraints")))
    constraints.extend(_text_list(answers.get("technical_constraints")))
    constraints.extend(_text_list(generated_plan.get("out_of_scope")))
    return list(dict.fromkeys(constraints))[:MAX_LIST_ITEMS]


def extract_project_open_questions(source: Any) -> list[str]:
    """Extract unresolved questions from context clarification or intake state."""

    if source is None:
        return []
    final_result = _final_result_from_source(source)
    intake_state = _project_intake_from_source(source, final_result)
    clarification = _as_dict(final_result.get("context_clarification"))
    questions: list[str] = []
    questions.extend(_text_list(_read_attr(source, "open_questions")))
    questions.extend(_text_list(final_result.get("open_questions")))
    questions.extend(_text_list(intake_state.get("open_questions")))
    questions.extend(_text_list(intake_state.get("remaining_questions")))
    question = _first_text(clarification.get("clarification_question"), clarification.get("question"))
    if question:
        questions.append(question)
    options = clarification.get("clarification_options")
    if options and clarification.get("needs_clarification") is True:
        questions.extend(_text_list(options))
    return list(dict.fromkeys(questions))[:MAX_LIST_ITEMS]


def _current_goal_from_source(source: Any) -> str | None:
    final_result = _final_result_from_source(source)
    intake_state = _project_intake_from_source(source, final_result)
    generated_plan = _generated_plan_from_source(source, final_result)
    answers = _as_dict(intake_state.get("answers"))
    return _first_text(
        generated_plan.get("main_goal"),
        answers.get("main_goal"),
        intake_state.get("current_goal"),
        intake_state.get("user_message"),
        intake_state.get("initial_prompt"),
        final_result.get("current_goal"),
        final_result.get("summary"),
        _read_attr(source, "current_goal"),
        _read_attr(source, "user_prompt"),
        _read_attr(source, "title"),
    )


def _workspace_id_from_source(source: Any) -> str | None:
    final_result = _final_result_from_source(source)
    output_bridge = _output_bridge_from_source(source, final_result)
    metadata = _as_dict(output_bridge.get("metadata"))
    return _first_text(
        _read_attr(source, "workspace_id"),
        final_result.get("workspace_id"),
        output_bridge.get("workspace_id"),
        metadata.get("workspace_id"),
    )


def build_project_memory_from_swarm_state(swarm_state_or_dict: Any) -> dict[str, Any]:
    """Build Project Memory Manifest from existing swarm-like data only."""

    source = swarm_state_or_dict
    if source is None:
        return build_project_memory_manifest(last_updated_source="swarm_state")
    iterations = extract_project_iterations(source)
    return build_project_memory_manifest(
        project_id=_first_text(_read_attr(source, "project_id"), _read_attr(source, "dashboard_id")),
        swarm_id=_first_text(_read_attr(source, "id"), _read_attr(source, "swarm_id")),
        workspace_id=_workspace_id_from_source(source),
        current_goal=_current_goal_from_source(source),
        decisions=extract_project_decisions(source),
        outputs=extract_project_outputs(source),
        accepted_iterations=iterations["accepted_iterations"],
        candidate_iterations=iterations["candidate_iterations"],
        artifacts=extract_project_artifacts(source),
        evidence=extract_project_evidence(source),
        constraints=extract_project_constraints(source),
        open_questions=extract_project_open_questions(source),
        last_updated_source="swarm_state",
    )


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
