from backend.apps.swarms.lsp_diagnostic_feedback import (
    attach_lsp_diagnostics_to_metadata,
    build_diagnostic_delta,
    build_diagnostic_evidence_bundle,
    build_diagnostic_feedback_decision,
    build_diagnostic_snapshot,
    build_lsp_diagnostic_trace_source,
    dump_diagnostic_snapshot,
    normalize_diagnostic_record,
    normalize_diagnostic_severity,
)


def _error_diag():
    return {
        "file_path": "src/app.ts",
        "line": 10,
        "column": 4,
        "severity": "error",
        "source": "tsserver",
        "code": "TS2322",
        "message": "Type string is not assignable to number.",
    }


def _warning_diag():
    return {
        "file": "src/app.ts",
        "line": 12,
        "severity": "warning",
        "source": "eslint",
        "code": "no-unused-vars",
        "message": "Unused variable.",
    }


def test_normalize_diagnostic_severity_aliases():
    assert normalize_diagnostic_severity("err") == "error"
    assert normalize_diagnostic_severity("warn") == "warning"
    assert normalize_diagnostic_severity("info") == "information"
    assert normalize_diagnostic_severity("4") == "hint"
    assert normalize_diagnostic_severity("x") == "unknown"


def test_normalize_diagnostic_record_redacts_sensitive_metadata():
    record = normalize_diagnostic_record({**_error_diag(), "secret_token": "leak", "raw_prompt": "leak"}, workspace_root="/repo")
    data = record.__dict__
    text = str(data).lower()

    assert record.severity == "error"
    assert record.file_path == "src/app.ts"
    assert record.message_hash
    assert record.evidence_ref.startswith("diagnostic:")
    assert "leak" not in text
    assert "raw_prompt" not in text


def test_build_diagnostic_snapshot_counts_and_status():
    snapshot = build_diagnostic_snapshot([_error_diag(), _warning_diag()], workspace_root="/repo", source="mixed")

    assert snapshot.status == "has_errors"
    assert snapshot.error_count == 1
    assert snapshot.warning_count == 1
    assert snapshot.affected_files == ["src/app.ts"]
    assert len(snapshot.evidence_refs) == 2
    assert snapshot.can_execute_diagnostics is False


def test_empty_snapshot_is_unmeasured_and_requires_action():
    snapshot = build_diagnostic_snapshot([])

    assert snapshot.status == "empty"
    assert snapshot.required_actions == ["run_diagnostics_or_attach_snapshot"]
    assert "diagnostics_empty" in snapshot.warnings


def test_diagnostic_evidence_bundle_maps_errors_to_failed_validation():
    snapshot = build_diagnostic_snapshot([_error_diag()])
    bundle = build_diagnostic_evidence_bundle(snapshot)

    assert bundle.status == "failed"
    assert bundle.validation_status == "failed"
    assert bundle.failure_reasons[0]["code"] == "diagnostic_errors_present"
    assert bundle.evidence_refs == snapshot.evidence_refs


def test_diagnostic_feedback_decision_blocks_errors():
    snapshot = build_diagnostic_snapshot([_error_diag()])
    bundle = build_diagnostic_evidence_bundle(snapshot)
    decision = build_diagnostic_feedback_decision(snapshot, bundle)

    assert decision.status == "failed"
    assert decision.should_block_acceptance is True
    assert decision.should_request_review is True


def test_diagnostic_feedback_decision_passes_clean_snapshot():
    snapshot = build_diagnostic_snapshot([{"file_path": "src/app.ts", "severity": "information", "message": "ok", "source": "tsserver"}])
    decision = build_diagnostic_feedback_decision(snapshot)

    assert decision.status == "passed"
    assert decision.should_block_acceptance is False
    assert decision.should_request_review is False


def test_diagnostic_delta_detects_added_and_resolved():
    previous = build_diagnostic_snapshot([_error_diag()])
    current = build_diagnostic_snapshot([_warning_diag()])

    delta = build_diagnostic_delta(previous, current)

    assert delta.status == "mixed"
    assert delta.added_count == 1
    assert delta.resolved_count == 1
    assert delta.required_actions == ["review_added_diagnostics"]


def test_diagnostic_trace_source_is_safe():
    snapshot = build_diagnostic_snapshot([_error_diag()], metadata={"secret_token": "leak"})
    bundle = build_diagnostic_evidence_bundle(snapshot)
    decision = build_diagnostic_feedback_decision(snapshot, bundle)
    trace = build_lsp_diagnostic_trace_source(snapshot=snapshot, evidence_bundle=bundle, decision=decision, metadata={"raw_response": "leak"})

    text = str(trace).lower()

    assert trace["source_kind"] == "lsp_diagnostic_feedback"
    assert trace["diagnostic_kind"] == "lsp_diagnostic_feedback"
    assert trace["status"] == "failed"
    assert "leak" not in text
    assert trace["can_execute_diagnostics"] is False


def test_attach_lsp_diagnostics_to_metadata_does_not_mutate_original():
    snapshot = build_diagnostic_snapshot([_warning_diag()])
    original = {"existing": True}

    attached = attach_lsp_diagnostics_to_metadata(original, snapshot=snapshot)

    assert original == {"existing": True}
    assert attached["existing"] is True
    assert attached["lsp_diagnostic_feedback"]["snapshot"]["warning_count"] == 1


def test_dump_snapshot_removes_sensitive_keys():
    snapshot = build_diagnostic_snapshot([_error_diag()], metadata={"password": "leak", "safe": "ok"})
    dumped = dump_diagnostic_snapshot(snapshot)
    text = str(dumped).lower()

    assert "leak" not in text
    assert "password" not in text
    assert dumped["metadata"]["safe"] == "ok"
