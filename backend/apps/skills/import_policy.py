"""Read-only policy gate for skill import preview reports."""

from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _unknown(value: Any) -> bool:
    return str(value or "").strip().lower() in {"", "unknown"}


def evaluate_skill_import_policy(preview_report: dict[str, Any]) -> dict[str, Any]:
    """Evaluate whether a preview may become an in-memory candidate later."""

    report = preview_report or {}
    spec = report.get("skill_spec_preview") if isinstance(report.get("skill_spec_preview"), dict) else {}
    contract = report.get("import_contract") if isinstance(report.get("import_contract"), dict) else {}
    risk_report = report.get("risk_report") if isinstance(report.get("risk_report"), dict) else {}
    reasons: list[dict[str, str]] = []
    blocked = False

    risks = {str(item) for item in _as_list(risk_report.get("risks"))}
    if risk_report.get("possible_secret_material") or "possible_secret_material" in risks:
        blocked = True
        reasons.append({"code": "possible_secret_material", "severity": "critical", "message": "Potential secret material blocks candidate creation."})
    if risk_report.get("dangerous_execution_instruction") or "dangerous_execution_instruction" in risks:
        blocked = True
        reasons.append({"code": "dangerous_execution_instruction", "severity": "critical", "message": "Dangerous execution instructions block candidate creation."})

    source_format = str(report.get("source_format") or contract.get("source_format") or spec.get("source_format") or "unknown")
    content = str(spec.get("content") or "")
    provenance = spec.get("provenance") if isinstance(spec.get("provenance"), dict) else {}
    source_license = contract.get("source_license") or provenance.get("source_license")
    source_author = contract.get("source_author") or provenance.get("source_author")
    required_tools = _as_list(report.get("required_tools") or contract.get("required_tools") or spec.get("required_tools"))
    required_mcp_servers = _as_list(report.get("required_mcp_servers") or contract.get("required_mcp_servers") or spec.get("required_mcp_servers"))
    prepared_ingestion_guard = report.get("prepared_ingestion_guard") if isinstance(report.get("prepared_ingestion_guard"), dict) else contract.get("prepared_ingestion_guard") if isinstance(contract.get("prepared_ingestion_guard"), dict) else {}
    ingestion_status = str(prepared_ingestion_guard.get("status") or "not_applicable")
    if ingestion_status == "blocked" or "unsafe_prepared_files" in risks:
        blocked = True
        reasons.append({"code": "prepared_ingestion_blocked", "severity": "critical", "message": "Prepared repo/zip/folder files failed ingestion guard."})
        for item in _as_list(prepared_ingestion_guard.get("rejected_files")):
            if isinstance(item, dict):
                reasons.append({
                    "code": str(item.get("code") or "prepared_file_rejected"),
                    "severity": str(item.get("severity") or "high"),
                    "message": str(item.get("message") or "Prepared file rejected."),
                })
    elif ingestion_status == "needs_review":
        reasons.append({"code": "prepared_ingestion_needs_review", "severity": "medium", "message": "Prepared repo/zip/folder files require manual review."})

    if not content:
        reasons.append({"code": "content_missing", "severity": "high", "message": "Preview content is required."})
    if source_format == "unknown":
        reasons.append({"code": "unknown_source_format", "severity": "medium", "message": "Unknown source format requires manual review."})
    if _unknown(source_license):
        reasons.append({"code": "source_license_unknown", "severity": "medium", "message": "Unknown source license requires manual review."})
    if _unknown(source_author):
        reasons.append({"code": "source_author_unknown", "severity": "medium", "message": "Unknown source author requires manual review."})
    if required_tools:
        reasons.append({"code": "required_tools_declared", "severity": "medium", "message": "Declared tools require manual review and do not activate tools."})
    if required_mcp_servers:
        reasons.append({"code": "required_mcp_servers_declared", "severity": "medium", "message": "Declared MCP servers require manual review and do not activate MCP."})

    if blocked:
        decision = "blocked"
        risk_level = "critical"
        can_create_candidate = False
        ok = False
    elif reasons:
        decision = "needs_review"
        risk_level = "high" if any(reason["severity"] == "high" for reason in reasons) else "medium"
        can_create_candidate = False
        ok = False
    elif content and source_format != "unknown":
        decision = "allow_candidate_preview"
        risk_level = "low"
        can_create_candidate = True
        ok = True
    else:
        decision = "needs_review"
        risk_level = "medium"
        can_create_candidate = False
        ok = False

    return {
        "policy_kind": "skill_import_policy_gate",
        "ok": ok,
        "decision": decision,
        "reasons": reasons,
        "risk_level": risk_level,
        "can_create_candidate": can_create_candidate,
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }
