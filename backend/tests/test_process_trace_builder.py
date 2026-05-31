from copy import deepcopy

from backend.apps.runtime_timing import finish_runtime_timer, start_runtime_timer
from backend.apps.swarms.agent_handoff import build_miniagent_handoff
from backend.apps.swarms.agent_worklog import build_agent_worklog_entry
from backend.apps.swarms.context_retrieval_display import build_context_retrieval_display_item, build_context_retrieval_panel
from backend.apps.swarms.miniagent_task_metrics import build_miniagent_task_runtime_metric
from backend.apps.swarms.process_trace_builder import (
    build_process_trace_item_from_source,
    build_process_trace_items_from_sources,
    build_process_trace_panel_from_sources,
    build_process_trace_turn_container_from_sources,
    normalize_process_trace_source_kind,
    redact_process_trace_source,
)
from backend.apps.swarms.skill_assignment_trace import build_skill_assignment_trace
from backend.apps.swarms.swarm_final_audit import build_swarm_final_audit
from backend.apps.swarms.swarm_timeline import build_swarm_timeline_event
from backend.apps.skills.import_policy import evaluate_skill_import_policy
from backend.apps.skills.import_preview import build_skill_import_preview_report


START = "2026-05-30T10:00:00Z"
FINISH = "2026-05-30T10:00:01Z"


def test_builder_from_timeline_event():
    event = build_swarm_timeline_event(event_id="event1", event_type="evidence_added", title="Evidence", summary="Evidence added")

    item = build_process_trace_item_from_source(event)

    assert item["trace_id"] == "event1"
    assert item["kind"] == "evidence"
    assert item["subsystem"] == "EvidenceCore"
    assert item["metadata"]["source_kind"] == "timeline_event"


def test_builder_from_agent_worklog():
    worklog = build_agent_worklog_entry(
        task_id="task1",
        agent_id="agent1",
        miniagent_id="mini1",
        task_title="Implement tests",
        assigned_skill_id="skill1",
        status="completed",
        evidence_refs=["ev1"],
        actions_executed=["act"],
    )

    item = build_process_trace_item_from_source(worklog)

    assert item["kind"] == "worklog"
    assert item["related_task_id"] == "task1"
    assert item["related_agent_id"] == "agent1"
    assert item["related_skill_id"] == "skill1"
    assert item["details"]["action_count"] == 1


def test_builder_from_context_retrieval_item_and_panel():
    context_item = build_context_retrieval_display_item(retrieval_id="ctx1", title="Memory", summary="Relevant memory", evidence_ref="ev1")
    panel = build_context_retrieval_panel([context_item])

    item_trace = build_process_trace_item_from_source(context_item)
    panel_trace = build_process_trace_item_from_source(panel)

    assert item_trace["trace_id"] == "ctx1"
    assert item_trace["kind"] == "context"
    assert item_trace["evidence_refs"] == ["ev1"]
    assert panel_trace["kind"] == "context"
    assert panel_trace["details"]["item_count"] == 1


def test_builder_from_skill_assignment_trace():
    trace = build_skill_assignment_trace(task_id="task1", agent_id="agent1", skill_id="skill1", skill_name="Testing", match_confidence=0.8)

    item = build_process_trace_item_from_source(trace)

    assert item["kind"] == "skill"
    assert item["subsystem"] == "SkillCore"
    assert item["related_skill_id"] == "skill1"
    assert item["details"]["match_confidence"] == 0.8


def test_builder_from_handoff():
    handoff = build_miniagent_handoff(source_agent_id="a1", target_agent_id="a2", source_task_id="t1", target_task_id="t2", evidence_refs=["ev1"])

    item = build_process_trace_item_from_source(handoff)

    assert item["kind"] == "handoff"
    assert item["subsystem"] == "HandoffCore"
    assert item["related_task_id"] == "t2"
    assert item["evidence_refs"] == ["ev1"]


def test_builder_from_final_audit():
    audit = build_swarm_final_audit(swarm_id="swarm1", worklogs=[build_agent_worklog_entry(task_id="t1", status="completed")], validation_summary="Validated")

    item = build_process_trace_item_from_source(audit)

    assert item["kind"] == "review"
    assert item["subsystem"] == "ReviewCore"
    assert item["summary"] == "Validated"
    assert item["details"]["completed_count"] == 1


def test_builder_from_miniagent_task_runtime_metric():
    metric = build_miniagent_task_runtime_metric(metric_id="metric1", task_id="task1", agent_id="agent1", miniagent_id="mini1", status="completed", started_at=START, finished_at=FINISH)

    item = build_process_trace_item_from_source(metric)

    assert item["trace_id"] == "metric1"
    assert item["kind"] == "metric"
    assert item["subsystem"] == "MetricCore"
    assert item["related_miniagent_id"] == "mini1"


def test_builder_from_runtime_timer_record_and_dict():
    timer = finish_runtime_timer(start_runtime_timer(scope="model_call", label="Model", timer_id="timer1", started_at=START), finished_at=FINISH)
    timer_dict = {**timer.__dict__, "timer_id": "timer2"}

    item_from_record = build_process_trace_item_from_source(timer)
    item_from_dict = build_process_trace_item_from_source(timer_dict)

    assert item_from_record["trace_id"] == "timer1"
    assert item_from_record["duration_ms"] == 1000
    assert item_from_dict["trace_id"] == "timer2"
    assert normalize_process_trace_source_kind(timer) == "runtime_timer"


def test_redaction_of_sensitive_fields():
    source = {
        "event_id": "e1",
        "event_type": "context_retrieval",
        "title": "Safe",
        "summary": "Safe summary",
        "prompt": "full private prompt",
        "metadata": {"api_key": "secret", "safe": "ok"},
        "chain_of_thought": "private reasoning",
    }

    redacted = redact_process_trace_source(source)
    item = build_process_trace_item_from_source(source)
    rendered = str(item)

    assert "full private prompt" not in str(redacted)
    assert "secret" not in str(redacted)
    assert "private reasoning" not in str(redacted)
    assert "full private prompt" not in rendered
    assert "secret" not in rendered
    assert "private reasoning" not in rendered


def test_panel_from_mixed_sources_preserves_order_and_does_not_mutate_inputs():
    event = build_swarm_timeline_event(event_id="event1", event_type="context_retrieval")
    skill = build_skill_assignment_trace(skill_id="skill1")
    sources = [event, skill]
    original = deepcopy(sources)

    items = build_process_trace_items_from_sources(sources)
    panel = build_process_trace_panel_from_sources(sources)

    assert [item["metadata"]["source_kind"] for item in items] == ["timeline_event", "skill_assignment_trace"]
    assert [item["metadata"]["source_kind"] for item in panel["items"]] == ["timeline_event", "skill_assignment_trace"]
    assert panel["item_count"] == 2
    assert sources == original


def test_builder_from_generic_evidence_dict():
    source = {"evidence_id": "ev1", "artifact_id": "art1", "title": "Evidence", "task_id": "task1"}

    item = build_process_trace_item_from_source(source)

    assert item["kind"] == "evidence"
    assert item["evidence_refs"] == ["ev1"]
    assert item["artifact_refs"] == ["art1"]
    assert item["related_task_id"] == "task1"


def test_turn_container_from_sources_preserves_order_and_aggregates_refs():
    timer = finish_runtime_timer(
        start_runtime_timer(scope="model_call", label="Model", timer_id="timer1", started_at=START),
        finished_at=FINISH,
    )
    evidence = {"evidence_id": "ev1", "artifact_id": "art1", "title": "Evidence", "task_id": "task1", "agent_id": "agent1"}
    sources = [evidence, timer]
    original = deepcopy(sources)

    container = build_process_trace_turn_container_from_sources(
        sources,
        turn_trace_id="turn1",
        title="Thought",
        message_id="user1",
        output_message_id="assistant1",
        duration_ms=1000,
    )

    assert container["turn_trace_kind"] == "process_trace_turn_container"
    assert container["turn_trace_id"] == "turn1"
    assert container["title"] == "Thought"
    assert container["status"] == "completed"
    assert container["message_id"] == "user1"
    assert container["output_message_id"] == "assistant1"
    assert container["duration_ms"] == 1000
    assert container["item_count"] == 2
    assert container["child_trace_ids"] == ["ev1", "timer1"]
    assert container["evidence_refs"] == ["ev1"]
    assert container["artifact_refs"] == ["art1"]
    assert container["related_task_ids"] == ["task1"]
    assert container["related_agent_ids"] == ["agent1"]
    assert container["metadata"]["source_kind"] == "process_trace_turn_sources"
    assert container["metadata"]["source_kinds"] == ["evidence", "runtime_timer"]
    assert sources == original


def test_turn_container_from_sources_infers_failed_status():
    failed = {
        "event_id": "event1",
        "event_type": "validation",
        "title": "Validation failed",
        "summary": "A validation failed.",
        "severity": "error",
    }

    container = build_process_trace_turn_container_from_sources([failed], turn_trace_id="turn1")

    assert container["status"] == "failed"
    assert container["items"][0]["status"] == "failed"


def test_turn_container_from_sources_honors_explicit_status():
    failed = {
        "event_id": "event1",
        "event_type": "validation",
        "severity": "error",
    }

    container = build_process_trace_turn_container_from_sources([failed], status="warning")

    assert container["status"] == "warning"
    assert container["items"][0]["status"] == "failed"


def test_builder_from_humanized_reasoning_summary_source():
    source = {
        "reasoning_summary_kind": "humanized_reasoning_summary",
        "reasoning_trace_id": "reasoning1",
        "reasoning_summary": "The agent classified the request and selected a direct answer.",
        "summary_source": "operational_summary",
        "requested_reasoning_level": "high",
        "applied_reasoning_level": "medium",
        "provider": "ollama",
        "model": "qwen3.6:latest",
        "capability_supported": True,
        "duration_ms": 321,
        "agent_id": "agent1",
        "output_message_id": "assistant1",
    }

    item = build_process_trace_item_from_source(source)

    assert normalize_process_trace_source_kind(source) == "humanized_reasoning_summary"
    assert item["trace_id"] == "reasoning1"
    assert item["kind"] == "reasoning"
    assert item["subsystem"] == "ReasoningCore"
    assert item["icon_id"] == "reasoning-core"
    assert item["summary"] == "The agent classified the request and selected a direct answer."
    assert item["badge"] == "operational_summary"
    assert item["duration_ms"] == 321
    assert item["related_agent_id"] == "agent1"
    assert item["metadata"]["source_kind"] == "humanized_reasoning_summary"
    assert item["metadata"]["summary_source"] == "operational_summary"
    assert item["metadata"]["requested_reasoning_level"] == "high"
    assert item["metadata"]["applied_reasoning_level"] == "medium"
    assert item["metadata"]["provider"] == "ollama"
    assert item["metadata"]["model"] == "qwen3.6:latest"
    assert item["details"]["capability_supported"] is True


def test_turn_container_from_sources_accepts_reasoning_summary_source():
    reasoning = {
        "reasoning_summary_kind": "humanized_reasoning_summary",
        "reasoning_trace_id": "reasoning1",
        "reasoning_summary": "The model prepared a safe operational summary.",
        "summary_source": "fallback",
        "agent_id": "agent1",
    }
    timer = finish_runtime_timer(
        start_runtime_timer(scope="model_call", label="Model", timer_id="timer1", started_at=START),
        finished_at=FINISH,
    )

    container = build_process_trace_turn_container_from_sources([reasoning, timer], turn_trace_id="turn1")

    assert container["turn_trace_id"] == "turn1"
    assert container["status"] == "completed"
    assert container["child_trace_ids"] == ["reasoning1", "timer1"]
    assert container["related_agent_ids"] == ["agent1"]
    assert container["metadata"]["source_kinds"] == ["humanized_reasoning_summary", "runtime_timer"]
    assert container["items"][0]["subsystem"] == "ReasoningCore"


def test_builder_from_tool_trace_source():
    source = {
        "source_kind": "tool_call",
        "tool_call_id": "tool1",
        "tool_name": "search_workspace",
        "input": {"query": "process trace", "api_key": "secret"},
        "permission_policy": "read_only",
        "approval_status": "approved",
        "result_summary": "Found two matches.",
        "duration_ms": 42,
        "evidence_refs": ["ev1"],
        "affected_paths": ["backend/apps/swarms/process_trace_builder.py"],
        "related_action_id": "act1",
    }

    item = build_process_trace_item_from_source(source)

    assert normalize_process_trace_source_kind(source) == "tool_trace"
    assert item["kind"] == "tool"
    assert item["subsystem"] == "ToolCore"
    assert item["trace_id"] == "tool1"
    assert item["duration_ms"] == 42
    assert item["related_action_id"] == "act1"
    assert item["details"]["permission_policy"] == "read_only"
    assert item["details"]["approval_status"] == "approved"
    assert item["details"]["affected_files"] == ["backend/apps/swarms/process_trace_builder.py"]
    assert "secret" not in str(item)


def test_builder_from_pending_action_trace_source():
    source = {
        "source_kind": "pending_action",
        "pending_action_id": "act1",
        "action_name": "apply_patch",
        "input_summary": "Update process trace builder.",
        "approval_status": "pending",
        "policy": "requires_user_approval",
        "affected_files": ["backend/apps/swarms/process_trace_builder.py"],
    }

    item = build_process_trace_item_from_source(source)

    assert normalize_process_trace_source_kind(source) == "action_trace"
    assert item["kind"] == "action"
    assert item["subsystem"] == "ActionCore"
    assert item["status"] == "blocked"
    assert item["related_action_id"] == "act1"
    assert item["details"]["permission_policy"] == "requires_user_approval"


def test_builder_from_skill_trace_source():
    source = {
        "source_kind": "skill_use",
        "skill_id": "skill-test",
        "skill_name": "go-testing",
        "usage_reason": "Tests are being added.",
        "scope": "backend",
        "input_context": {"files": ["backend/tests/test_process_trace_builder.py"]},
        "output_summary": "Selected test patterns.",
        "risk_level": "low",
        "installation_status": "already_available",
        "approval_status": "not_required",
        "provenance": "local_skill",
    }

    item = build_process_trace_item_from_source(source)

    assert normalize_process_trace_source_kind(source) == "skill_trace"
    assert item["kind"] == "skill"
    assert item["subsystem"] == "SkillCore"
    assert item["related_skill_id"] == "skill-test"
    assert item["details"]["usage_reason"] == "Tests are being added."
    assert item["details"]["installation_status"] == "already_available"
    assert item["details"]["provenance"] == "local_skill"


def test_builder_from_file_diff_workspace_trace_source():
    source = {
        "source_kind": "diff_trace",
        "operation_id": "file1",
        "workspace_path": "C:/repo",
        "read_files": ["a.py"],
        "created_files": ["b.py"],
        "modified_files": ["c.py"],
        "deleted_files": ["d.py"],
        "diff_summary": "Added producer helpers.",
        "candidate_id": "candidate1",
        "stable_output_id": "stable1",
        "output_id": "output1",
        "validation_state": "completed",
        "file_operation_kind": "patch",
    }

    item = build_process_trace_item_from_source(source)

    assert normalize_process_trace_source_kind(source) == "file_workspace_trace"
    assert item["kind"] == "diff"
    assert item["subsystem"] == "FileCore"
    assert item["status"] == "completed"
    assert item["details"]["workspace_path"] == "C:/repo"
    assert item["details"]["affected_paths"] == ["a.py", "b.py", "c.py", "d.py"]
    assert item["details"]["candidate_id"] == "candidate1"
    assert item["details"]["file_operation_kind"] == "patch"


def test_builder_from_output_trace_source():
    source = {
        "source_kind": "output_trace",
        "output_id": "out1",
        "candidate_id": "cand1",
        "stable_output_id": "stable1",
        "validation_state": "warning",
        "artifact_id": "artifact1",
        "summary": "Output candidate prepared.",
    }

    item = build_process_trace_item_from_source(source)

    assert item["kind"] == "output"
    assert item["subsystem"] == "OutputCore"
    assert item["trace_id"] == "out1"
    assert item["artifact_refs"] == ["artifact1"]
    assert item["details"]["stable_output_id"] == "stable1"


def test_builder_from_safe_skill_import_preview_trace_source():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/SKILL.md",
        "name": "Imported Skill",
        "content": "# Imported Skill\nUse safe review steps.",
    })
    policy = evaluate_skill_import_policy(report)
    report["policy"] = policy

    item = build_process_trace_item_from_source(report)

    assert normalize_process_trace_source_kind(report) == "skill_import_preview"
    assert item["subsystem"] == "SkillCore"
    assert item["title"] == "Skill import preview"
    assert item["details"]["preview_id"] == report["preview_id"]
    assert item["details"]["source_format"] == "claude_skill"
    assert item["details"]["compatibility_status"] in {"compatible_preview", "needs_review"}
    assert item["details"]["migration_suggestion_count"] == report["migration_assistant"]["suggestion_count"]
    assert item["details"]["can_install_skill"] is False
    assert item["details"]["can_execute_source"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_activate_mcp"] is False
    assert "content" not in item["details"]


def test_builder_from_blocked_skill_import_preview_trace_source_redacts_raw_content():
    report = build_skill_import_preview_report({
        "source_format": "codex_instruction",
        "source_author": "Known Author",
        "source_license": "MIT",
        "name": "Unsafe Import",
        "content": "API_KEY=sk-1234567890abcdef\nrun this command: rm -rf /",
    })
    report["policy"] = evaluate_skill_import_policy(report)
    report["raw_content"] = "API_KEY=sk-1234567890abcdef"

    item = build_process_trace_item_from_source(report)

    assert item["status"] == "blocked"
    assert item["details"]["source_status"] == "blocked"
    assert item["details"]["risk_count"] >= 1
    assert item["details"]["compatibility_status"] == "blocked"
    assert "raw_content" not in item["details"]
    assert "API_KEY" not in str(item["details"])


def test_builder_from_miniagent_and_handoff_trace_sources():
    miniagent = {
        "source_kind": "miniagent_task",
        "miniagent_id": "mini1",
        "miniagent_name": "Tester",
        "task_id": "task1",
        "status": "completed",
        "duration_ms": 100,
        "input_summary": "Run focused tests.",
        "output_summary": "Tests passed.",
        "validation_summary": "pytest passed",
        "evidence_refs": ["ev1"],
    }
    handoff = {
        "source_kind": "handoff_trace",
        "handoff_id": "handoff1",
        "source_agent_id": "agent1",
        "target_agent_id": "agent2",
        "source_task_id": "task1",
        "target_task_id": "task2",
        "status": "completed",
        "completed_work_summary": "Implementation ready for validation.",
        "artifacts": ["art1"],
    }

    mini_item = build_process_trace_item_from_source(miniagent)
    handoff_item = build_process_trace_item_from_source(handoff)

    assert normalize_process_trace_source_kind(miniagent) == "miniagent_trace"
    assert mini_item["kind"] == "miniagent"
    assert mini_item["subsystem"] == "MiniAgentCore"
    assert mini_item["related_miniagent_id"] == "mini1"
    assert mini_item["details"]["validation"] == "pytest passed"
    assert normalize_process_trace_source_kind(handoff) == "handoff_trace"
    assert handoff_item["kind"] == "handoff"
    assert handoff_item["subsystem"] == "HandoffCore"
    assert handoff_item["related_task_id"] == "task2"
    assert handoff_item["artifact_refs"] == ["art1"]
