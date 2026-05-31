from backend.apps.swarms.lsp_diagnostic_feedback import (
    build_diagnostic_evidence_bundle,
    build_diagnostic_feedback_decision,
    build_diagnostic_snapshot,
    build_lsp_diagnostic_trace_source,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def _diag(severity="error"):
    return {
        "file_path": "src/app.ts",
        "line": 1,
        "column": 2,
        "severity": severity,
        "source": "tsserver",
        "code": "TS1005",
        "message": "Expected semicolon.",
    }


def test_process_trace_recognizes_lsp_diagnostic_feedback():
    snapshot = build_diagnostic_snapshot([_diag()])
    bundle = build_diagnostic_evidence_bundle(snapshot)
    decision = build_diagnostic_feedback_decision(snapshot, bundle)
    source = build_lsp_diagnostic_trace_source(snapshot=snapshot, evidence_bundle=bundle, decision=decision)

    assert normalize_process_trace_source_kind(source) == "lsp_diagnostic_feedback"

    item = build_process_trace_item_from_source(source)

    assert item["subsystem"] == "ValidationCore"
    assert item["kind"] == "validation"
    assert item["status"] == "blocked"
    assert item["details"]["source_kind"] == "lsp_diagnostic_feedback"
    assert item["evidence_refs"] == snapshot.evidence_refs


def test_lsp_diagnostic_process_trace_warning_status():
    snapshot = build_diagnostic_snapshot([_diag("warning")])
    source = build_lsp_diagnostic_trace_source(snapshot=snapshot)

    item = build_process_trace_item_from_source(source)

    assert item["status"] == "warning"
    assert item["details"]["snapshot"]["warning_count"] == 1


def test_lsp_diagnostic_process_trace_is_redacted():
    source = {
        "source_kind": "lsp_diagnostic_feedback",
        "diagnostic_kind": "lsp_diagnostic_feedback",
        "status": "failed",
        "snapshot": {"metadata": {"secret_token": "leak"}, "evidence_refs": ["ev1"]},
        "decision": {"status": "failed", "raw_prompt": "leak"},
        "metadata": {"response": "leak"},
    }

    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    assert item["subsystem"] == "ValidationCore"
    assert "leak" not in text
    assert "raw_prompt" not in text
    assert "response" not in text
