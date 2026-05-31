from backend.apps.skills.skill_harness import (
    build_skill_dry_run_report,
    build_skill_evidence_quality_report,
    build_skill_promotion_gate,
    build_skill_regression_suite,
    build_skill_runtime_validation_report,
    build_skill_test_case_contract,
)


def _candidate(**spec_overrides):
    spec = {
        "name": "CSS Validator",
        "description": "Validate CSS quality.",
        "command": "css-validator",
        "content": "# CSS Validator\nReview CSS for maintainability.",
        "validation_plan": {"checks": [{"title": "Check CSS guidance", "expected_behavior": "Provides CSS review guidance", "required_evidence": ["review_notes"]}]},
        "evidence_contract": {"required_evidence": ["review_notes"]},
        "risks": [],
        "required_tools": [],
        "required_mcp_servers": [],
    }
    spec.update(spec_overrides)
    return {"candidate_id": "cand1", "skill_spec": spec, "source": "skill_builder", "evidence_refs": ["review_notes"], "install_approved": False}


def _assert_safe(payload):
    assert payload["can_install_skill"] is False
    assert payload["can_execute_source"] is False
    assert payload["can_activate_tools"] is False
    assert payload["can_activate_mcp"] is False


def test_candidate_with_content_generates_minimal_test_cases():
    candidate = _candidate(validation_plan={}, evidence_contract={})
    contract = build_skill_test_case_contract(candidate)

    assert contract["contract_kind"] == "skill_test_case_contract"
    assert contract["status"] == "ready"
    assert contract["test_case_count"] >= 2
    assert all(case["status"] == "proposed" for case in contract["test_cases"])
    assert {case["generated_from"] for case in contract["test_cases"]} == {"inferred"}
    _assert_safe(contract)


def test_missing_content_blocks_test_contract():
    contract = build_skill_test_case_contract(_candidate(content=""))

    assert contract["status"] == "blocked"
    assert "skill_content_missing" in contract["blocked_reasons"]
    assert contract["can_run_dry_run"] is False


def test_required_tools_and_mcp_force_needs_review():
    contract = build_skill_test_case_contract(_candidate(required_tools=["Read"], required_mcp_servers=["docs"]))

    assert contract["status"] == "needs_review"
    assert "required_tools_declared_review_required" in contract["warnings"]
    assert "required_mcp_servers_declared_review_required" in contract["warnings"]
    _assert_safe(contract)


def test_validation_plan_and_evidence_contract_enrich_test_cases():
    contract = build_skill_test_case_contract(_candidate())

    assert contract["test_case_count"] == 1
    assert contract["test_cases"][0]["generated_from"] == "explicit"
    assert contract["test_cases"][0]["required_evidence"] == ["review_notes"]


def test_basic_dry_run_simulates_cases_without_execution():
    contract = build_skill_test_case_contract(_candidate())
    report = build_skill_dry_run_report(_candidate(), contract)

    assert report["report_kind"] == "skill_dry_run_report"
    assert report["dry_run_mode"] == "read_only_simulation"
    assert report["simulated"] is True
    assert report["executed"] is False
    assert report["tool_calls_executed"] is False
    assert report["mcp_activated"] is False
    assert report["install_performed"] is False
    assert report["evaluated_test_cases"][0]["status"] == "simulated"


def test_dry_run_builds_missing_contract_and_does_not_activate_tools():
    report = build_skill_dry_run_report(_candidate(required_tools=["Read"], required_mcp_servers=["docs"]))

    assert report["status"] == "needs_review"
    assert report["tool_calls_executed"] is False
    assert report["mcp_activated"] is False
    assert report["evaluated_test_cases"][0]["status"] == "needs_review"


def test_blocked_candidate_produces_blocked_dry_run():
    report = build_skill_dry_run_report(_candidate(risks=["dangerous_execution_instruction"]))

    assert report["status"] == "blocked"
    assert "critical_risk_present" in report["blocked_reasons"]


def test_safe_candidate_passes_runtime_validation():
    dry = build_skill_dry_run_report(_candidate())
    validation = build_skill_runtime_validation_report(_candidate(), dry)

    assert validation["status"] == "passed"
    assert validation["failed_count"] == 0
    assert validation["can_promote_candidate"] is True
    _assert_safe(validation)


def test_runtime_validation_critical_risks_fail():
    validation = build_skill_runtime_validation_report(_candidate(risks=["possible_secret_material"]))

    assert validation["status"] == "blocked"
    assert "no_critical_risks" in validation["blocked_reasons"]


def test_runtime_validation_missing_evidence_contract_warns_not_blocks():
    validation = build_skill_runtime_validation_report(_candidate(evidence_contract={}))

    assert validation["status"] == "needs_review"
    assert validation["warning_count"] >= 1
    assert "evidence_contract_present_or_warn" not in validation["blocked_reasons"]


def test_runtime_validation_dry_run_blocked_propagates_blocked():
    dry = build_skill_dry_run_report(_candidate(risks=["dangerous_execution_instruction"]))
    validation = build_skill_runtime_validation_report(_candidate(risks=["dangerous_execution_instruction"]), dry)

    assert validation["status"] == "blocked"
    assert "dry_run_blocked" in validation["blocked_reasons"]


def test_regression_suite_generated_from_test_contract_and_never_executes():
    validation = build_skill_runtime_validation_report(_candidate())
    suite = build_skill_regression_suite(_candidate(), validation)

    assert suite["suite_kind"] == "skill_regression_suite"
    assert suite["status"] == "ready"
    assert suite["regression_tests"]
    assert suite["can_execute_tests"] is False
    assert suite["execution_required"] is False
    _assert_safe(suite)


def test_regression_suite_blocks_on_critical_risk_and_declares_permission_checks():
    suite = build_skill_regression_suite(_candidate(risks=["possible_secret_material"], required_tools=["Read"], required_mcp_servers=["docs"]))

    assert suite["status"] == "blocked"
    assert any(test.get("check_type") == "declarative_permission_review" for test in suite["regression_tests"])


def test_evidence_quality_missing_refs_does_not_invent_evidence():
    validation = build_skill_runtime_validation_report(_candidate())
    report = build_skill_evidence_quality_report(_candidate(), validation, evidence_refs=[])

    assert report["status"] == "missing"
    assert report["evidence_refs"] == []
    assert report["missing_evidence"] == ["review_notes"]
    assert report["can_promote_candidate"] is False


def test_evidence_quality_preserves_real_refs_and_required_evidence():
    validation = build_skill_runtime_validation_report(_candidate())
    report = build_skill_evidence_quality_report(_candidate(), validation, evidence_refs=["review_notes"])

    assert report["status"] == "sufficient"
    assert report["evidence_refs"] == ["review_notes"]
    assert report["required_evidence"] == ["review_notes"]
    assert report["missing_evidence"] == []
    _assert_safe(report)


def test_promotion_gate_promote_ready_only_after_validation_and_evidence():
    candidate = _candidate()
    validation = build_skill_runtime_validation_report(candidate)
    evidence = build_skill_evidence_quality_report(candidate, validation, evidence_refs=["review_notes"])
    regression = build_skill_regression_suite(candidate, validation)

    gate = build_skill_promotion_gate(candidate, validation, evidence, regression)

    assert gate["decision"] == "promote_ready"
    assert gate["can_request_install_approval"] is True
    assert gate["can_install_skill"] is False
    assert gate["install_requires_explicit_approval"] is True


def test_promotion_gate_requires_permission_review_for_tools_mcp():
    candidate = _candidate(required_tools=["Read"], required_mcp_servers=["docs"])
    validation = build_skill_runtime_validation_report(candidate)
    evidence = build_skill_evidence_quality_report(candidate, validation, evidence_refs=["review_notes"])
    regression = build_skill_regression_suite(candidate, validation)

    gate = build_skill_promotion_gate(candidate, validation, evidence, regression)

    assert gate["decision"] == "needs_review"
    assert gate["can_request_install_approval"] is False
    assert {item["code"] for item in gate["required_actions"]} >= {"review_required_tools", "review_required_mcp_servers"}


def test_promotion_gate_blocks_without_evidence_or_with_critical_risk():
    candidate = _candidate(risks=["dangerous_execution_instruction"], evidence_refs=[])
    gate = build_skill_promotion_gate(candidate)

    assert gate["decision"] == "blocked"
    assert gate["can_request_install_approval"] is False
    assert any(reason["code"] == "critical_risk_present" for reason in gate["reasons"])
