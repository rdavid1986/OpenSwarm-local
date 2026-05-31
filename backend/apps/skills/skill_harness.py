"""Read-only validation harness contracts for SkillSpec candidates.

This module proposes tests and validation metadata only. It never executes skill
commands, installs skills, calls tools/MCP, reads external folders, or mutates
candidates.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CRITICAL_RISKS = {"possible_secret_material", "dangerous_execution_instruction", "secret_material", "critical_risk"}
SAFE_FLAGS = {
    "can_install_skill": False,
    "can_execute_source": False,
    "can_activate_tools": False,
    "can_activate_mcp": False,
}


def _safe(value: Any) -> Any:
    return deepcopy(value)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return _safe(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return _safe(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _candidate_and_spec(candidate_or_spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    data = _as_dict(candidate_or_spec)
    spec = data.get("skill_spec") if isinstance(data.get("skill_spec"), dict) else data
    return data, _as_dict(spec)


def _skill_ref(candidate: dict[str, Any], spec: dict[str, Any]) -> str:
    return _text(candidate.get("candidate_id") or spec.get("id") or spec.get("name"), "unknown")


def _risks(candidate: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    risks = [str(item) for item in _as_list(spec.get("risks"))]
    for warning in _as_list(candidate.get("warnings")):
        if isinstance(warning, dict):
            risks.extend(str(item) for item in _as_list(warning.get("risks")))
            if str(warning.get("severity") or "").lower() == "critical":
                risks.append(str(warning.get("code") or "critical_risk"))
    return [risk for risk in risks if risk]


def _has_critical_risk(candidate: dict[str, Any], spec: dict[str, Any]) -> bool:
    return any(risk in CRITICAL_RISKS for risk in _risks(candidate, spec))


def _required_tools_or_mcp(spec: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    return _as_list(spec.get("required_tools")), _as_list(spec.get("required_mcp_servers"))


def _required_evidence_from_spec(spec: dict[str, Any]) -> list[str]:
    evidence_contract = _as_dict(spec.get("evidence_contract"))
    values: list[Any] = []
    for key in ("required_evidence", "required_evidence_refs", "evidence_types", "required"):
        values.extend(_as_list(evidence_contract.get(key)))
    return [str(value) for value in values if str(value or "").strip()]


def _validation_items(spec: dict[str, Any]) -> list[Any]:
    plan = _as_dict(spec.get("validation_plan"))
    for key in ("test_cases", "tests", "scenarios", "checks"):
        items = _as_list(plan.get(key))
        if items:
            return items
    return []


def _test_case(idx: int, *, title: str, purpose: str, input_context: Any, expected_behavior: str, required_evidence: list[str], risk_level: str, generated_from: str) -> dict[str, Any]:
    return {
        "test_case_id": f"skill-test-{idx}",
        "title": title,
        "purpose": purpose,
        "input_context": input_context,
        "expected_behavior": expected_behavior,
        "required_evidence": required_evidence,
        "risk_level": risk_level,
        "status": "proposed",
        "generated_from": generated_from,
    }


def build_skill_test_case_contract(candidate_or_spec: dict[str, Any]) -> dict[str, Any]:
    candidate, spec = _candidate_and_spec(candidate_or_spec)
    skill_name = _text(spec.get("name"), "unknown")
    content = _text(spec.get("content"))
    tools, mcp = _required_tools_or_mcp(spec)
    warnings: list[str] = []
    blocked_reasons: list[str] = []
    test_cases: list[dict[str, Any]] = []

    if not content:
        blocked_reasons.append("skill_content_missing")
    if tools:
        warnings.append("required_tools_declared_review_required")
    if mcp:
        warnings.append("required_mcp_servers_declared_review_required")

    required_evidence = _required_evidence_from_spec(spec)
    for idx, item in enumerate(_validation_items(spec), start=1):
        item_dict = item if isinstance(item, dict) else {"title": str(item)}
        test_cases.append(_test_case(
            idx,
            title=_text(item_dict.get("title") or item_dict.get("name"), f"Validate {skill_name} behavior"),
            purpose=_text(item_dict.get("purpose") or item_dict.get("description"), "Validate declared skill behavior."),
            input_context=item_dict.get("input_context") or item_dict.get("input") or {"source": "validation_plan"},
            expected_behavior=_text(item_dict.get("expected_behavior") or item_dict.get("expected"), "Skill should follow its declared guidance."),
            required_evidence=[str(v) for v in _as_list(item_dict.get("required_evidence"))] or required_evidence,
            risk_level=_text(item_dict.get("risk_level"), "low"),
            generated_from="explicit",
        ))

    if content and not test_cases:
        base_evidence = required_evidence or ["review_notes"]
        test_cases.append(_test_case(
            1,
            title=f"Apply {skill_name} to a representative request",
            purpose="Check whether the skill guidance is usable from its name, description, and content.",
            input_context={"request": _text(spec.get("description"), "representative task"), "content_ref": "skill_spec.content"},
            expected_behavior="Agent follows the skill guidance without executing commands or activating tools.",
            required_evidence=base_evidence,
            risk_level="medium" if tools or mcp else "low",
            generated_from="inferred",
        ))
        test_cases.append(_test_case(
            2,
            title=f"Respect {skill_name} safety boundary",
            purpose="Verify the skill remains knowledge-only and does not grant permissions.",
            input_context={"declared_tools": tools, "declared_mcp_servers": mcp},
            expected_behavior="No install, command execution, tool call, or MCP activation occurs.",
            required_evidence=["harness_read_only_flags"],
            risk_level="medium" if tools or mcp else "low",
            generated_from="inferred",
        ))

    if blocked_reasons:
        status = "blocked"
    elif not test_cases:
        status = "unmeasured"
    elif warnings:
        status = "needs_review"
    else:
        status = "ready"

    return {
        "contract_kind": "skill_test_case_contract",
        "status": status,
        "skill_ref": _skill_ref(candidate, spec),
        "skill_name": skill_name,
        "source": _text(candidate.get("source"), "not_provided"),
        "test_cases": test_cases,
        "test_case_count": len(test_cases),
        "warnings": warnings,
        "blocked_reasons": blocked_reasons,
        "can_run_dry_run": status in {"ready", "needs_review"},
        **SAFE_FLAGS,
    }


def build_skill_dry_run_report(
    candidate_or_spec: dict[str, Any],
    test_contract: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate, spec = _candidate_and_spec(candidate_or_spec)
    contract = _as_dict(test_contract) or build_skill_test_case_contract(candidate_or_spec)
    ctx = _as_dict(context)
    tools, mcp = _required_tools_or_mcp(spec)
    critical = _has_critical_risk(candidate, spec)
    evidence_refs = [str(item) for item in _as_list(ctx.get("evidence_refs") or candidate.get("evidence_refs"))]

    evaluated: list[dict[str, Any]] = []
    for case in _as_list(contract.get("test_cases")):
        if not isinstance(case, dict):
            continue
        required_evidence = [str(item) for item in _as_list(case.get("required_evidence"))]
        missing = [item for item in required_evidence if item not in evidence_refs]
        status = "blocked" if critical or contract.get("status") == "blocked" else "needs_review" if tools or mcp or missing else "simulated"
        evaluated.append({
            "test_case_id": case.get("test_case_id"),
            "status": status,
            "expected_behavior_summary": _text(case.get("expected_behavior"), "not_provided"),
            "required_evidence": required_evidence,
            "missing_evidence": missing,
            "notes": ["Read-only simulation; no commands, tools, MCP, model calls, or install were executed."],
        })

    if critical or contract.get("status") == "blocked":
        status = "blocked"
    elif not evaluated:
        status = "unmeasured"
    elif tools or mcp or any(item["status"] == "needs_review" for item in evaluated):
        status = "needs_review"
    else:
        status = "ready"

    return {
        "report_kind": "skill_dry_run_report",
        "status": status,
        "skill_ref": contract.get("skill_ref") or _skill_ref(candidate, spec),
        "dry_run_mode": "read_only_simulation",
        "simulated": True,
        "executed": False,
        "tool_calls_executed": False,
        "mcp_activated": False,
        "install_performed": False,
        "evaluated_test_cases": evaluated,
        "evaluated_test_case_count": len(evaluated),
        "blocked_reasons": ["critical_risk_present"] if critical else list(contract.get("blocked_reasons") or []),
        **SAFE_FLAGS,
    }


def _check(code: str, status: str, message: str, severity: str = "medium") -> dict[str, Any]:
    return {"code": code, "status": status, "message": message, "severity": severity}


def build_skill_runtime_validation_report(
    candidate_or_spec: dict[str, Any],
    dry_run_report: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate, spec = _candidate_and_spec(candidate_or_spec)
    dry = _as_dict(dry_run_report) or build_skill_dry_run_report(candidate_or_spec, context=context)
    critical = _has_critical_risk(candidate, spec)
    checks: list[dict[str, Any]] = []
    checks.append(_check("content_present", "passed" if _text(spec.get("content")) else "failed", "Skill content is present." if _text(spec.get("content")) else "Skill content is missing.", "high"))
    checks.append(_check("name_present", "passed" if _text(spec.get("name")) else "failed", "Skill name is present." if _text(spec.get("name")) else "Skill name is missing.", "high"))
    checks.append(_check("command_present_or_optional", "passed" if _text(spec.get("command")) else "warning", "Command is present." if _text(spec.get("command")) else "Command is optional/not_provided.", "low"))
    checks.append(_check("evidence_contract_present_or_warn", "passed" if _as_dict(spec.get("evidence_contract")) else "warning", "Evidence contract present." if _as_dict(spec.get("evidence_contract")) else "Evidence contract missing.", "medium"))
    checks.append(_check("validation_plan_present_or_warn", "passed" if _as_dict(spec.get("validation_plan")) else "warning", "Validation plan present." if _as_dict(spec.get("validation_plan")) else "Validation plan missing.", "medium"))
    checks.append(_check("no_critical_risks", "failed" if critical else "passed", "Critical risk present." if critical else "No critical risks declared.", "critical" if critical else "low"))
    checks.append(_check("dry_run_available", "passed" if dry else "warning", "Dry run report available." if dry else "Dry run report missing.", "medium"))
    checks.append(_check("dry_run_not_executed", "passed" if dry.get("executed") is False else "failed", "Dry run did not execute source." if dry.get("executed") is False else "Dry run execution flag is unsafe.", "critical"))
    checks.append(_check("permissions_not_activated", "passed" if not dry.get("tool_calls_executed") and not dry.get("mcp_activated") else "failed", "Tools/MCP were not activated.", "critical"))
    checks.append(_check("install_not_performed", "passed" if dry.get("install_performed") is False else "failed", "Install was not performed.", "critical"))
    if dry.get("status") == "blocked":
        checks.append(_check("dry_run_blocked", "blocked", "Dry run status is blocked.", "critical"))

    failed_count = sum(1 for item in checks if item["status"] == "failed")
    warning_count = sum(1 for item in checks if item["status"] == "warning")
    blocked_reasons = [item["code"] for item in checks if item["status"] == "blocked" or item["severity"] == "critical" and item["status"] == "failed"]
    if blocked_reasons:
        status = "blocked"
    elif failed_count:
        status = "failed"
    elif warning_count:
        status = "needs_review"
    else:
        status = "passed"

    return {
        "report_kind": "skill_runtime_validation_report",
        "status": status,
        "skill_ref": _skill_ref(candidate, spec),
        "checks": checks,
        "passed_count": sum(1 for item in checks if item["status"] == "passed"),
        "failed_count": failed_count,
        "warning_count": warning_count,
        "blocked_reasons": blocked_reasons,
        "required_evidence": _required_evidence_from_spec(spec),
        "can_promote_candidate": status in {"passed", "needs_review"} and failed_count == 0 and not blocked_reasons,
        **SAFE_FLAGS,
    }


def build_skill_regression_suite(candidate_or_spec: dict[str, Any], validation_report: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate, spec = _candidate_and_spec(candidate_or_spec)
    validation = _as_dict(validation_report)
    test_contract = build_skill_test_case_contract(candidate_or_spec)
    tools, mcp = _required_tools_or_mcp(spec)
    critical = _has_critical_risk(candidate, spec)
    regression_tests = []
    for case in _as_list(test_contract.get("test_cases")):
        if isinstance(case, dict):
            regression_tests.append({
                "regression_test_id": f"regression-{case.get('test_case_id')}",
                "source_test_case_id": case.get("test_case_id"),
                "title": f"Regression: {_text(case.get('title'), 'skill behavior')}",
                "check_type": "declarative",
                "required_evidence": _as_list(case.get("required_evidence")),
                "can_execute": False,
            })
    if tools:
        regression_tests.append({"regression_test_id": "regression-required-tools", "title": "Declared tools remain permission-reviewed", "check_type": "declarative_permission_review", "required_tools": tools, "can_execute": False})
    if mcp:
        regression_tests.append({"regression_test_id": "regression-required-mcp", "title": "Declared MCP remains permission-reviewed", "check_type": "declarative_permission_review", "required_mcp_servers": mcp, "can_execute": False})

    if critical or validation.get("status") == "blocked":
        status = "blocked"
    elif not regression_tests:
        status = "unmeasured"
    elif tools or mcp or test_contract.get("status") == "needs_review":
        status = "needs_review"
    else:
        status = "ready"

    return {
        "suite_kind": "skill_regression_suite",
        "status": status,
        "skill_ref": _skill_ref(candidate, spec),
        "regression_tests": regression_tests,
        "coverage_summary": {
            "test_case_count": test_contract.get("test_case_count", 0),
            "regression_test_count": len(regression_tests),
            "permission_review_checks": int(bool(tools)) + int(bool(mcp)),
            "critical_risk_present": critical,
        },
        "can_execute_tests": False,
        "execution_required": False,
        **SAFE_FLAGS,
    }


def build_skill_evidence_quality_report(
    candidate_or_spec: dict[str, Any],
    validation_report: dict[str, Any] | None = None,
    evidence_refs: list | None = None,
) -> dict[str, Any]:
    candidate, spec = _candidate_and_spec(candidate_or_spec)
    validation = _as_dict(validation_report)
    refs = [str(item) for item in _as_list(evidence_refs if evidence_refs is not None else candidate.get("evidence_refs")) if str(item or "").strip()]
    required = [str(item) for item in (_as_list(validation.get("required_evidence")) or _required_evidence_from_spec(spec)) if str(item or "").strip()]
    missing = [item for item in required if item not in refs]
    quality_checks = [
        {"code": "evidence_refs_present", "status": "passed" if refs else "failed", "message": "Evidence refs are present." if refs else "No evidence refs provided."},
        {"code": "required_evidence_covered", "status": "passed" if required and not missing else "warning" if not required else "failed", "message": "Required evidence covered." if required and not missing else "Required evidence is missing or not declared."},
    ]
    critical = _has_critical_risk(candidate, spec) or validation.get("status") == "blocked"
    if critical:
        status = "blocked"
    elif not refs:
        status = "missing" if required or validation.get("status") in {"passed", "needs_review"} else "weak"
    elif missing:
        status = "weak"
    elif len(refs) >= 2:
        status = "strong"
    else:
        status = "sufficient"

    return {
        "report_kind": "skill_evidence_quality_report",
        "status": status,
        "skill_ref": _skill_ref(candidate, spec),
        "evidence_refs": refs,
        "evidence_count": len(refs),
        "required_evidence": required,
        "missing_evidence": missing,
        "quality_checks": quality_checks,
        "limitations": [] if refs else ["No evidence refs were provided; evidence was not invented."],
        "can_promote_candidate": status in {"sufficient", "strong"} and not missing,
        **SAFE_FLAGS,
    }


def build_skill_promotion_gate(
    candidate_or_spec: dict[str, Any],
    validation_report: dict[str, Any] | None = None,
    evidence_report: dict[str, Any] | None = None,
    regression_suite: dict[str, Any] | None = None,
    version_summary: dict[str, Any] | None = None,
    effectiveness_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate, spec = _candidate_and_spec(candidate_or_spec)
    validation = _as_dict(validation_report) or build_skill_runtime_validation_report(candidate_or_spec)
    evidence = _as_dict(evidence_report) or build_skill_evidence_quality_report(candidate_or_spec, validation)
    regression = _as_dict(regression_suite) or build_skill_regression_suite(candidate_or_spec, validation)
    version = _as_dict(version_summary)
    effectiveness = _as_dict(effectiveness_summary)
    tools, mcp = _required_tools_or_mcp(spec)
    reasons: list[dict[str, Any]] = []
    required_actions: list[dict[str, Any]] = []

    if validation.get("status") not in {"passed", "needs_review"} or not validation.get("can_promote_candidate"):
        reasons.append({"code": "runtime_validation_not_ready", "message": "Runtime validation is not promotion-ready.", "severity": "high"})
    if evidence.get("status") not in {"sufficient", "strong"} or not evidence.get("can_promote_candidate"):
        reasons.append({"code": "evidence_quality_not_sufficient", "message": "Evidence quality is not sufficient for promotion.", "severity": "high"})
    if regression.get("status") == "blocked":
        reasons.append({"code": "regression_suite_blocked", "message": "Regression suite is blocked.", "severity": "critical"})
    if _has_critical_risk(candidate, spec):
        reasons.append({"code": "critical_risk_present", "message": "Critical risk blocks promotion.", "severity": "critical"})
    if tools:
        required_actions.append({"code": "review_required_tools", "message": "Review declared tools before install approval.", "target": "required_tools"})
    if mcp:
        required_actions.append({"code": "review_required_mcp_servers", "message": "Review declared MCP servers before install approval.", "target": "required_mcp_servers"})
    if candidate.get("install_approved"):
        required_actions.append({"code": "install_already_approved_elsewhere", "message": "Harness does not install even when candidate is already approved.", "target": "candidate.install_approved"})
    if version and int(version.get("snapshot_count") or 0) <= 0:
        required_actions.append({"code": "create_version_snapshot_before_install", "message": "Create an explicit version snapshot before requesting install approval.", "target": "skill_versions"})
    elif not version:
        required_actions.append({"code": "create_version_snapshot_before_install", "message": "Version snapshot status is unknown; create one before install approval.", "target": "skill_versions"})
    if not effectiveness:
        required_actions.append({"code": "effectiveness_unmeasured", "message": "Effectiveness metrics are unmeasured; this is a review warning, not a fake pass.", "target": "skill_metrics"})
    elif effectiveness.get("status") == "failing":
        reasons.append({"code": "effectiveness_failing", "message": "Explicit effectiveness records indicate failing outcomes.", "severity": "critical"})
    elif effectiveness.get("status") in {"needs_review", "insufficient_data", "unmeasured"}:
        required_actions.append({"code": f"effectiveness_{effectiveness.get('status')}", "message": "Review explicit effectiveness metrics before approval.", "target": "skill_metrics"})

    if reasons:
        decision = "blocked" if any(reason.get("severity") == "critical" for reason in reasons) else "needs_review"
    elif required_actions:
        decision = "needs_review"
    elif validation.get("status") == "passed" and evidence.get("status") in {"sufficient", "strong"} and regression.get("status") in {"ready", "needs_review"}:
        decision = "promote_ready"
    else:
        decision = "unmeasured"

    return {
        "gate_kind": "skill_promotion_gate",
        "decision": decision,
        "skill_ref": _skill_ref(candidate, spec),
        "reasons": reasons,
        "required_actions": required_actions,
        "can_request_install_approval": decision == "promote_ready",
        "can_install_skill": False,
        "install_requires_explicit_approval": True,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }


def build_skill_harness_full_report(candidate_or_spec: dict[str, Any]) -> dict[str, Any]:
    test_contract = build_skill_test_case_contract(candidate_or_spec)
    dry_run = build_skill_dry_run_report(candidate_or_spec, test_contract)
    validation = build_skill_runtime_validation_report(candidate_or_spec, dry_run)
    regression = build_skill_regression_suite(candidate_or_spec, validation)
    evidence = build_skill_evidence_quality_report(candidate_or_spec, validation)
    promotion = build_skill_promotion_gate(candidate_or_spec, validation, evidence, regression)
    return {
        "harness_kind": "skill_harness_full_report",
        "skill_ref": test_contract.get("skill_ref"),
        "test_contract": test_contract,
        "dry_run": dry_run,
        "runtime_validation": validation,
        "regression_suite": regression,
        "evidence_quality": evidence,
        "promotion_gate": promotion,
        **SAFE_FLAGS,
    }
