"""Deterministic fail-closed guard for refinement execution.

RI-7.D intentionally does not execute the refinement pipeline, mutate Output
files, create snapshots, or create rollback records. It only evaluates whether
the current prepared refinement state would be safe to advance from
``prepared`` to a future ``executing`` stage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.apps.outputs.outputs import load_output, load_output_iterations
from backend.apps.swarms.response_intelligence import build_ri_state_snapshot
from backend.apps.swarms.workspace_intelligence import build_workspace_intelligence


WORKSPACE_BLOCKING_ERRORS = {
    "workspace_path_missing",
    "workspace_outside_allowed_root",
    "workspace_not_found",
    "file_not_allowed",
    "path_traversal_not_allowed",
    "symlink_outside_workspace",
}


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value if isinstance(value, dict) else {}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _add_reason(
    reasons: list[dict[str, Any]],
    *,
    code: str,
    message: str,
    severity: str = "high",
    metadata: dict[str, Any] | None = None,
) -> None:
    if any(reason.get("code") == code for reason in reasons):
        return
    reason: dict[str, Any] = {
        "code": code,
        "message": message,
        "severity": severity,
    }
    if metadata:
        reason["metadata"] = metadata
    reasons.append(reason)


def _next_steps_for(reasons: list[dict[str, Any]]) -> list[dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {
        "action_stage_not_prepared": {
            "code": "prepare_refinement",
            "label": "Preparar el refinamiento antes de intentar ejecutarlo.",
            "phase": "RI-7.D",
        },
        "prepare_metadata_missing": {
            "code": "prepare_refinement",
            "label": "Generar metadata de preparación para el refinamiento.",
            "phase": "RI-7.D",
        },
        "prepare_status_not_prepared": {
            "code": "prepare_refinement",
            "label": "Reintentar preparación hasta obtener refinement_status=prepared.",
            "phase": "RI-7.D",
        },
        "output_not_found": {
            "code": "select_existing_output",
            "label": "Seleccionar un Output existente antes de refinar.",
            "phase": "Apps-3.G",
        },
        "output_id_mismatch": {
            "code": "reconcile_output_id",
            "label": "Reconciliar el Output ID entre request, preparación y Output cargado.",
            "phase": "RI-7.D",
        },
        "requested_change_required": {
            "code": "provide_requested_change",
            "label": "Indicar el cambio solicitado antes de ejecutar.",
            "phase": "RI-7.D",
        },
        "requested_change_mismatch": {
            "code": "reconfirm_requested_change",
            "label": "Reconfirmar el cambio solicitado para evitar ejecutar otro pedido.",
            "phase": "RI-7.D",
        },
        "workspace_stale": {
            "code": "refresh_workspace",
            "label": "Sincronizar workspace y Output antes de ejecutar.",
            "phase": "PM-3",
        },
        "workspace_missing": {
            "code": "restore_workspace",
            "label": "Restaurar o recrear el workspace asociado al Output.",
            "phase": "PM-3",
        },
        "workspace_unknown": {
            "code": "resolve_workspace_freshness",
            "label": "Resolver freshness del workspace antes de ejecutar.",
            "phase": "PM-3",
        },
        "approval_missing": {
            "code": "request_refinement_execution_approval",
            "label": "Solicitar approval explícito para ejecutar el refinamiento.",
            "phase": "W.2.A",
        },
        "snapshot_missing": {
            "code": "create_output_iteration_snapshot",
            "label": "Crear snapshot/version base del Output antes de ejecutar.",
            "phase": "Apps-3.G.4.A",
        },
        "candidate_iteration_missing": {
            "code": "create_candidate_output_iteration",
            "label": "Crear candidate iteration antes de ejecutar el refinamiento.",
            "phase": "CMP-1",
        },
        "rollback_missing": {
            "code": "create_refinement_rollback_plan",
            "label": "Crear rollback mínimo antes de ejecutar.",
            "phase": "W.2.A",
        },
        "execution_pipeline_unavailable": {
            "code": "implement_guarded_refinement_pipeline",
            "label": "Implementar pipeline real de refinamiento detrás del guard.",
            "phase": "RI-7.F",
        },
        "evidence_insufficient": {
            "code": "attach_output_evidence",
            "label": "Adjuntar artifacts/evidence suficientes para justificar la base.",
            "phase": "Apps-3.G",
        },
        "source_swarm_mismatch": {
            "code": "reconcile_source_swarm",
            "label": "Reconciliar source_swarm_id entre request y Output.",
            "phase": "RI-7.D",
        },
    }
    steps: list[dict[str, str]] = []
    seen: set[str] = set()
    for reason in reasons:
        code = str(reason.get("code") or "")
        step = mapping.get(code)
        if step and step["code"] not in seen:
            steps.append(step)
            seen.add(step["code"])
    return steps


def _risk_level(reasons: list[dict[str, Any]]) -> str:
    severities = {str(reason.get("severity") or "high") for reason in reasons}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"


def _state_from_bool(value: bool) -> str:
    return "available" if value else "missing"


def _has_snapshot(prepare_metadata: dict[str, Any], output_data: dict[str, Any]) -> bool:
    """Best-effort forward-compatible detector for future snapshot/version state."""

    for key in (
        "snapshot_id",
        "base_snapshot_id",
        "version_id",
        "base_version_id",
        "output_iteration_id",
    ):
        if _as_text(prepare_metadata.get(key)) or _as_text(output_data.get(key)):
            return True
    snapshot = prepare_metadata.get("snapshot")
    version = prepare_metadata.get("version")
    return bool(_as_dict(snapshot) or _as_dict(version))


def _latest_candidate_iteration(output_id: str) -> dict[str, Any]:
    candidates = []
    for iteration in load_output_iterations(output_id):
        if getattr(iteration, "status", None) != "candidate":
            continue
        base_workspace_path = _as_text(getattr(iteration, "base_workspace_path", None))
        candidate_workspace_path = _as_text(getattr(iteration, "candidate_workspace_path", None))
        if not base_workspace_path or not candidate_workspace_path:
            continue
        if not Path(base_workspace_path).is_dir() or not Path(candidate_workspace_path).is_dir():
            continue
        candidates.append(iteration)

    if not candidates:
        return {}
    candidates.sort(key=lambda iteration: getattr(iteration, "created_at", ""))
    return candidates[-1].model_dump(mode="json")


def _has_rollback(prepare_metadata: dict[str, Any]) -> bool:
    for key in ("rollback_id", "rollback_plan_id"):
        if _as_text(prepare_metadata.get(key)):
            return True
    if prepare_metadata.get("rollback_available") is True:
        return True
    return bool(_as_dict(prepare_metadata.get("rollback")) or _as_dict(prepare_metadata.get("rollback_plan")))


def _evidence_state(
    *,
    swarm: Any,
    output_data: dict[str, Any],
    workspace_intelligence: dict[str, Any],
) -> tuple[str, int, int]:
    artifact_count = len(_list(output_data.get("artifact_refs"))) + len(_list(getattr(swarm, "artifacts", [])))
    evidence_refs = _list(workspace_intelligence.get("evidence_refs"))
    evidence_count = len(evidence_refs)
    if artifact_count > 0 and evidence_count > 0:
        return "sufficient", artifact_count, evidence_count
    if artifact_count > 0 or evidence_count > 0:
        return "partial", artifact_count, evidence_count
    return "missing", artifact_count, evidence_count


def _source_swarm_state(
    *,
    swarm: Any,
    refinement_request: dict[str, Any],
    prepare_metadata: dict[str, Any],
    output_data: dict[str, Any],
) -> tuple[str, str | None]:
    source_swarm_id = (
        _as_text(refinement_request.get("source_swarm_id"))
        or _as_text(prepare_metadata.get("source_swarm_id"))
        or _as_text(getattr(swarm, "id", None))
        or None
    )
    output_source = _as_text(output_data.get("source_swarm_id")) or None
    if source_swarm_id and output_source and source_swarm_id != output_source:
        return "mismatch", source_swarm_id
    if source_swarm_id and output_source:
        return "match", source_swarm_id
    return "unknown", source_swarm_id or output_source


def evaluate_refinement_execution_guard(
    *,
    swarm: Any,
    output_id: str,
    requested_change: str,
    approve: bool = False,
) -> dict[str, Any]:
    """Return a structured fail-closed decision for prepared -> executing.

    The current RI-7.D implementation is intentionally informational: it never
    executes, never mutates Output files, and blocks whenever required future
    safety primitives (snapshot/version, rollback, real pipeline) are missing.
    """

    requested_output_id = _as_text(output_id)
    requested_change_text = _as_text(requested_change)
    final_result = _as_dict(getattr(swarm, "final_result", None))
    refinement_request = _as_dict(final_result.get("refinement_request"))
    prepare_payload = _as_dict(final_result.get("prepare_output_refinement"))
    prepare_metadata = _as_dict(prepare_payload.get("metadata"))
    prepare_status = _as_text(prepare_metadata.get("refinement_status")).lower()

    ri_state = build_ri_state_snapshot(swarm, route="refinement_request")
    action_stage = ri_state.action_stage
    output = load_output(requested_output_id) if requested_output_id else None
    output_data = _as_dict(output)
    has_output = output is not None
    candidate_iteration = _latest_candidate_iteration(requested_output_id) if has_output and requested_output_id else {}
    has_candidate_iteration = bool(candidate_iteration)

    workspace_source = "output_workspace"
    workspace_path_override = None
    workspace_reference_output: Any = output
    if candidate_iteration:
        workspace_path_override = _as_text(candidate_iteration.get("base_workspace_path")) or None
        files_before = candidate_iteration.get("files_before")
        if isinstance(files_before, dict) and files_before:
            workspace_reference_output = {**output_data, "files": dict(files_before)}
        workspace_source = "candidate_base_workspace"

    workspace_intelligence = build_workspace_intelligence(
        swarm=swarm,
        output=workspace_reference_output,
        workspace_path=workspace_path_override,
    )

    workspace_errors = [
        error for error in _list(workspace_intelligence.get("errors"))
        if isinstance(error, dict)
    ]
    workspace_error_codes = {
        str(error.get("error") or "")
        for error in workspace_errors
        if str(error.get("error") or "")
    }
    workspace_freshness = _as_text(workspace_intelligence.get("freshness")) or "unknown"
    has_workspace = bool(workspace_intelligence.get("exists"))
    has_snapshot = _has_snapshot(prepare_metadata, output_data) or has_candidate_iteration
    has_rollback = (
        _has_rollback(prepare_metadata)
        or bool(candidate_iteration.get("base_workspace_path"))
        or bool(candidate_iteration.get("files_before"))
    )
    approval_state = "provided" if approve else "missing"
    source_swarm_state, source_swarm_id = _source_swarm_state(
        swarm=swarm,
        refinement_request=refinement_request,
        prepare_metadata=prepare_metadata,
        output_data=output_data,
    )
    evidence_state, artifact_count, evidence_count = _evidence_state(
        swarm=swarm,
        output_data=output_data,
        workspace_intelligence=workspace_intelligence,
    )

    reasons: list[dict[str, Any]] = []

    if action_stage != "prepared":
        _add_reason(
            reasons,
            code="action_stage_not_prepared",
            message=f"El action_stage actual es {action_stage or 'none'}, no prepared.",
        )
    if not prepare_metadata:
        _add_reason(
            reasons,
            code="prepare_metadata_missing",
            message="No existe metadata de prepare_output_refinement.",
        )
    elif prepare_status != "prepared":
        _add_reason(
            reasons,
            code="prepare_status_not_prepared",
            message=f"refinement_status es {prepare_status or 'missing'}, no prepared.",
        )

    if not requested_output_id:
        _add_reason(reasons, code="output_id_required", message="Falta output_id para evaluar el guard.")
    if not requested_change_text:
        _add_reason(
            reasons,
            code="requested_change_required",
            message="Falta requested_change para evaluar el guard.",
        )
    if not has_output and requested_output_id:
        _add_reason(
            reasons,
            code="output_not_found",
            message="No existe el Output solicitado.",
            metadata={"output_id": requested_output_id},
        )

    prepared_output_id = _as_text(prepare_metadata.get("output_id"))
    refinement_output_id = _as_text(refinement_request.get("output_id"))
    if prepared_output_id and requested_output_id and prepared_output_id != requested_output_id:
        _add_reason(
            reasons,
            code="output_id_mismatch",
            message="El output_id solicitado no coincide con la metadata preparada.",
            metadata={"requested": requested_output_id, "prepared": prepared_output_id},
        )
    if refinement_output_id and requested_output_id and refinement_output_id != requested_output_id:
        _add_reason(
            reasons,
            code="output_id_mismatch",
            message="El output_id solicitado no coincide con refinement_request.",
            metadata={"requested": requested_output_id, "refinement_request": refinement_output_id},
        )

    prepared_change = _as_text(prepare_metadata.get("requested_change"))
    refinement_change = _as_text(refinement_request.get("requested_change"))
    if prepared_change and requested_change_text and prepared_change != requested_change_text:
        _add_reason(
            reasons,
            code="requested_change_mismatch",
            message="El requested_change solicitado no coincide con la metadata preparada.",
            metadata={"requested": requested_change_text, "prepared": prepared_change},
        )
    if refinement_change and requested_change_text and refinement_change != requested_change_text:
        _add_reason(
            reasons,
            code="requested_change_mismatch",
            message="El requested_change solicitado no coincide con refinement_request.",
            metadata={"requested": requested_change_text, "refinement_request": refinement_change},
        )

    if not has_workspace:
        _add_reason(reasons, code="workspace_missing", message="No hay workspace legible para el refinamiento.")
    if workspace_freshness == "stale":
        _add_reason(reasons, code="workspace_stale", message="El workspace está stale contra el Output.")
    elif workspace_freshness == "missing":
        _add_reason(reasons, code="workspace_missing", message="El workspace o archivos requeridos están missing.")
    elif workspace_freshness == "unknown":
        _add_reason(reasons, code="workspace_unknown", message="No se pudo verificar freshness del workspace.")

    for error_code in sorted(workspace_error_codes & WORKSPACE_BLOCKING_ERRORS):
        _add_reason(
            reasons,
            code=error_code,
            message=f"Workspace Intelligence reportó {error_code}.",
            metadata={"workspace_errors": [error for error in workspace_errors if error.get("error") == error_code]},
        )

    if approval_state == "missing":
        _add_reason(
            reasons,
            code="approval_missing",
            message="Falta approval explícito para ejecución del refinamiento.",
            severity="medium",
        )
    if not has_snapshot:
        _add_reason(
            reasons,
            code="snapshot_missing",
            message="No existe snapshot/version base del Output para ejecución segura.",
        )
    if not has_candidate_iteration:
        _add_reason(
            reasons,
            code="candidate_iteration_missing",
            message="No existe candidate iteration con workspace base/candidate para ejecución segura.",
        )
    if not has_rollback:
        _add_reason(
            reasons,
            code="rollback_missing",
            message="No existe rollback mínimo disponible para revertir la iteración.",
        )

    execution_pipeline_available = has_candidate_iteration and has_snapshot and has_rollback

    if not execution_pipeline_available:
        _add_reason(
            reasons,
            code="execution_pipeline_unavailable",
            message="El pipeline real de refinamiento todavía no está habilitado detrás del guard.",
        )

    if evidence_state != "sufficient":
        _add_reason(
            reasons,
            code="evidence_insufficient",
            message="Artifacts/evidence asociados son insuficientes para una ejecución segura.",
            severity="medium",
            metadata={"artifact_count": artifact_count, "evidence_count": evidence_count},
        )

    if source_swarm_state == "mismatch":
        _add_reason(
            reasons,
            code="source_swarm_mismatch",
            message="source_swarm_id no coincide entre request/preparación y Output.",
        )

    allowed = not any(reason.get("severity") == "high" for reason in reasons)
    guard_status = "allowed" if allowed else "blocked"
    return {
        "allowed": allowed,
        "guard_status": guard_status,
        "action_stage": action_stage,
        "blocked_reasons": reasons,
        "required_next_steps": _next_steps_for(reasons),
        "risk_level": _risk_level(reasons),
        "metadata": {
            "output_id": requested_output_id or None,
            "requested_change": requested_change_text,
            "workspace_freshness": workspace_freshness,
            "has_output": has_output,
            "has_workspace": has_workspace,
            "has_snapshot": has_snapshot,
            "has_candidate_iteration": has_candidate_iteration,
            "candidate_iteration_id": candidate_iteration.get("iteration_id"),
            "has_rollback": has_rollback,
            "approval_state": approval_state,
            "snapshot_state": _state_from_bool(has_snapshot),
            "rollback_state": _state_from_bool(has_rollback),
            "evidence_state": evidence_state,
            "source_swarm_id": source_swarm_id,
            "source_swarm_state": source_swarm_state,
            "prepare_state": "prepared" if prepare_status == "prepared" else ("missing" if not prepare_metadata else "mismatch"),
            "prepared_output_id": prepared_output_id or None,
            "prepared_requested_change": prepared_change,
            "refinement_request_output_id": refinement_output_id or None,
            "refinement_request_requested_change": refinement_change,
            "workspace_path": workspace_intelligence.get("workspace_path"),
            "workspace_source": workspace_source,
            "workspace_errors": workspace_errors,
            "candidate_base_workspace_path": candidate_iteration.get("base_workspace_path"),
            "candidate_workspace_path": candidate_iteration.get("candidate_workspace_path"),
            "artifact_count": artifact_count,
            "evidence_count": evidence_count,
            "execution_pipeline_state": "available" if execution_pipeline_available else "unavailable",
        },
    }
