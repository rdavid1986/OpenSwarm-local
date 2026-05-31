"""Side-effect-free compatibility and migration helpers for skill imports."""

from __future__ import annotations

from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or fallback


def _unknown(value: Any) -> bool:
    return str(value or "").strip().lower() in {"", "unknown", "not_provided", "unmeasured"}


def _component(score: float | str, status: str, reasons: list[str]) -> dict[str, Any]:
    return {"score": score, "status": status, "reasons": reasons}


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _risk_report(preview_report: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(preview_report.get("risk_report"))


def _spec(preview_report: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(preview_report.get("skill_spec_preview"))


def _contract(preview_report: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(preview_report.get("import_contract"))


def _provenance(preview_report: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_spec(preview_report).get("provenance"))


def build_skill_import_compatibility_score(preview_report: dict[str, Any]) -> dict[str, Any]:
    """Build an explainable preview-only compatibility score.

    The score is derived only from the already-prepared preview report. It does
    not install, execute, browse, activate tools/MCP, or inspect external files.
    """

    report = preview_report or {}
    spec = _spec(report)
    contract = _contract(report)
    risk = _risk_report(report)
    provenance = _provenance(report)
    content = str(spec.get("content") or "")
    source_format = _text(report.get("source_format") or contract.get("source_format") or spec.get("source_format"))
    required_tools = _as_list(report.get("required_tools") or contract.get("required_tools") or spec.get("required_tools"))
    required_mcp = _as_list(report.get("required_mcp_servers") or contract.get("required_mcp_servers") or spec.get("required_mcp_servers"))
    risks = set(str(item) for item in _as_list(risk.get("risks") or contract.get("risks") or spec.get("risks")))
    has_secret = bool(risk.get("possible_secret_material") or "possible_secret_material" in risks)
    has_dangerous = bool(risk.get("dangerous_execution_instruction") or "dangerous_execution_instruction" in risks)

    if not content and source_format == "unknown":
        components = {
            "structure_compatibility": _component("unmeasured", "unmeasured", ["No skill content or source format provided."]),
            "instruction_clarity": _component("unmeasured", "unmeasured", ["No instruction content provided."]),
            "tool_requirement_fit": _component("unmeasured", "unmeasured", ["No declarative tool/MCP data provided."]),
            "permission_risk": _component("unmeasured", "unmeasured", ["No content available for risk scoring."]),
            "provenance_quality": _component("unmeasured", "unmeasured", ["No source metadata provided."]),
            "testability": _component("unmeasured", "unmeasured", ["No validation or evidence contract provided."]),
        }
        return {
            "score_kind": "skill_import_compatibility_score",
            "score": "unmeasured",
            "status": "unmeasured",
            "confidence": "unmeasured",
            "components": components,
            "weights": {
                "structure_compatibility": 0.18,
                "instruction_clarity": 0.18,
                "tool_requirement_fit": 0.14,
                "permission_risk": 0.2,
                "provenance_quality": 0.18,
                "testability": 0.12,
            },
            "notes": ["Insufficient preview data for compatibility scoring."],
            "can_install_skill": False,
            "can_execute_source": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        }

    structure_score = 1.0
    structure_reasons: list[str] = []
    if source_format == "unknown":
        structure_score -= 0.35
        structure_reasons.append("Unknown source format requires conservative migration review.")
    if not content:
        structure_score -= 0.45
        structure_reasons.append("Skill content is missing.")
    if not _text(spec.get("name"), ""):
        structure_score -= 0.15
        structure_reasons.append("Skill name is missing.")

    clarity_score = 1.0
    clarity_reasons: list[str] = []
    if len(content.strip()) < 24:
        clarity_score -= 0.35
        clarity_reasons.append("Instruction content is very short.")
    if not _text(spec.get("description"), ""):
        clarity_score -= 0.2
        clarity_reasons.append("Description is missing.")
    if not _text(spec.get("command"), ""):
        clarity_score -= 0.15
        clarity_reasons.append("Command/activation phrase is missing.")

    tool_score = 1.0
    tool_reasons: list[str] = []
    if required_tools:
        tool_score -= 0.2
        tool_reasons.append("Required tools are declared and need manual permission review.")
    if required_mcp:
        tool_score -= 0.25
        tool_reasons.append("Required MCP servers are declared and need manual permission review.")

    permission_score = 1.0
    permission_reasons: list[str] = []
    if has_secret:
        permission_score = 0.0
        permission_reasons.append("Possible secret material blocks safe candidate creation.")
    if has_dangerous:
        permission_score = 0.0
        permission_reasons.append("Dangerous execution instruction blocks safe candidate creation.")
    if required_tools or required_mcp:
        permission_score = min(permission_score, 0.65)
        permission_reasons.append("Tool/MCP requirements are declarative only and cannot be activated from preview.")

    provenance_score = 1.0
    provenance_reasons: list[str] = []
    for key in ("source_author", "source_license", "source_url", "source_hash"):
        value = contract.get(key) or provenance.get(key)
        if _unknown(value):
            provenance_score -= 0.18
            provenance_reasons.append(f"{key} is unknown or not provided.")

    validation_plan = _as_dict(spec.get("validation_plan"))
    evidence_contract = _as_dict(spec.get("evidence_contract"))
    testability_score = 1.0
    testability_reasons: list[str] = []
    if not validation_plan:
        testability_score -= 0.3
        testability_reasons.append("Validation plan is missing.")
    if not evidence_contract:
        testability_score -= 0.25
        testability_reasons.append("Evidence contract is missing.")

    component_scores = {
        "structure_compatibility": _bounded(structure_score),
        "instruction_clarity": _bounded(clarity_score),
        "tool_requirement_fit": _bounded(tool_score),
        "permission_risk": _bounded(permission_score),
        "provenance_quality": _bounded(provenance_score),
        "testability": _bounded(testability_score),
    }
    components = {
        "structure_compatibility": _component(component_scores["structure_compatibility"], "needs_review" if structure_reasons else "compatible_preview", structure_reasons or ["Recognized preview structure."]),
        "instruction_clarity": _component(component_scores["instruction_clarity"], "needs_review" if clarity_reasons else "compatible_preview", clarity_reasons or ["Instruction content is present."]),
        "tool_requirement_fit": _component(component_scores["tool_requirement_fit"], "needs_review" if tool_reasons else "compatible_preview", tool_reasons or ["No required tools/MCP declared."]),
        "permission_risk": _component(component_scores["permission_risk"], "blocked" if permission_score == 0 else "needs_review" if permission_reasons else "compatible_preview", permission_reasons or ["No blocking permission risk detected in preview."]),
        "provenance_quality": _component(component_scores["provenance_quality"], "needs_review" if provenance_reasons else "compatible_preview", provenance_reasons or ["Source metadata is present."]),
        "testability": _component(component_scores["testability"], "needs_review" if testability_reasons else "compatible_preview", testability_reasons or ["Validation and evidence metadata are present."]),
    }
    weights = {
        "structure_compatibility": 0.18,
        "instruction_clarity": 0.18,
        "tool_requirement_fit": 0.14,
        "permission_risk": 0.2,
        "provenance_quality": 0.18,
        "testability": 0.12,
    }
    score = _bounded(sum(component_scores[key] * weight for key, weight in weights.items()))
    status = "blocked" if has_secret or has_dangerous else "needs_review" if score < 0.75 or required_tools or required_mcp or any(component["status"] == "needs_review" for component in components.values()) else "compatible_preview"
    notes = [reason for component in components.values() for reason in component["reasons"] if reason]
    if required_tools or required_mcp:
        notes.append("Declared tool/MCP requirements do not activate tools or MCP.")

    return {
        "score_kind": "skill_import_compatibility_score",
        "score": score,
        "status": status,
        "confidence": "inferred",
        "components": components,
        "weights": weights,
        "notes": notes,
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }


def _suggestion(code: str, title: str, severity: str, target: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "severity": severity,
        "target": target,
        "message": message,
        "auto_apply_supported": False,
    }


def build_skill_import_migration_suggestions(preview_report: dict[str, Any]) -> dict[str, Any]:
    """Build manual migration suggestions from preview metadata only."""

    report = preview_report or {}
    spec = _spec(report)
    contract = _contract(report)
    risk = _risk_report(report)
    provenance = _provenance(report)
    source_format = _text(report.get("source_format") or contract.get("source_format") or spec.get("source_format"))
    required_tools = _as_list(report.get("required_tools") or contract.get("required_tools") or spec.get("required_tools"))
    required_mcp = _as_list(report.get("required_mcp_servers") or contract.get("required_mcp_servers") or spec.get("required_mcp_servers"))
    suggestions: list[dict[str, Any]] = []

    if not _text(spec.get("name"), ""):
        suggestions.append(_suggestion("add_skill_name", "Add skill name", "medium", "skill_spec_preview.name", "Provide a clear skill name before candidate review."))
    if not _text(spec.get("description"), ""):
        suggestions.append(_suggestion("add_description", "Add description", "low", "skill_spec_preview.description", "Add a short description explaining when to use this skill."))
    if not _text(spec.get("command"), ""):
        suggestions.append(_suggestion("add_command", "Add command", "low", "skill_spec_preview.command", "Add an activation command or leave an explicit not_provided marker."))
    if not _text(spec.get("content"), ""):
        suggestions.append(_suggestion("add_skill_content", "Add skill content", "high", "skill_spec_preview.content", "Skill instruction content is required before candidate creation."))
    if source_format == "unknown":
        suggestions.append(_suggestion("confirm_source_format", "Confirm source format", "medium", "source_format", "Unknown source format requires manual confirmation."))
    for key, code, title in (
        ("source_author", "add_source_author", "Add source author"),
        ("source_license", "add_source_license", "Add source license"),
        ("source_url", "add_source_ref", "Add source ref"),
    ):
        if _unknown(contract.get(key) or provenance.get(key)):
            suggestions.append(_suggestion(code, title, "medium", f"provenance.{key}", f"{key} is unknown or not provided."))
    if required_tools:
        suggestions.append(_suggestion("review_required_tools", "Review required tools", "medium", "required_tools", "Declared tools require manual review; preview does not activate tools."))
    if required_mcp:
        suggestions.append(_suggestion("review_required_mcp_servers", "Review required MCP servers", "medium", "required_mcp_servers", "Declared MCP servers require manual review; preview does not activate MCP."))
    if risk.get("possible_secret_material") or "possible_secret_material" in set(str(item) for item in _as_list(risk.get("risks"))):
        suggestions.append(_suggestion("remove_secret_material", "Remove secret material", "critical", "skill_spec_preview.content", "Remove possible secret material before candidate creation."))
    if risk.get("dangerous_execution_instruction") or "dangerous_execution_instruction" in set(str(item) for item in _as_list(risk.get("risks"))):
        suggestions.append(_suggestion("rewrite_dangerous_execution_instruction", "Rewrite dangerous execution instruction", "critical", "skill_spec_preview.content", "Rewrite dangerous execution instructions as safe, review-only guidance."))
    if not _as_dict(spec.get("validation_plan")):
        suggestions.append(_suggestion("add_validation_plan", "Add validation plan", "medium", "skill_spec_preview.validation_plan", "Add a validation plan before approving install later."))
    if not _as_dict(spec.get("evidence_contract")):
        suggestions.append(_suggestion("add_evidence_contract", "Add evidence contract", "medium", "skill_spec_preview.evidence_contract", "Add expected evidence refs or mark as not_provided."))

    blocked = any(item["severity"] == "critical" for item in suggestions)
    status = "blocked" if blocked else "needs_migration" if suggestions else "ready_for_candidate_review"
    return {
        "assistant_kind": "skill_import_migration_assistant",
        "status": status,
        "suggestions": suggestions,
        "suggestion_count": len(suggestions),
        "requires_manual_review": bool(suggestions),
        "can_auto_apply": False,
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }
