import json

from backend.apps.swarms.code_action import build_code_action_contract, build_code_action_pending_action
from backend.apps.swarms.eval_harness import build_eval_evaluator_node, build_eval_loop_contract, build_eval_memory_record
from backend.apps.swarms.mcp_contract import (
    build_mcp_evidence_record,
    build_mcp_fallback_adapter_contract,
    build_mcp_fallback_plan,
    build_mcp_sandbox_policy_decision,
    build_mcp_tool_registry,
    inspect_mcp_tool_registry,
)
from backend.apps.swarms.state_context import (
    build_state_context_payload,
    build_state_context_prompt,
    normalize_state_context_value,
)


def test_state_context_payload_normalizes_missing_fields_without_inventing():
    payload = build_state_context_payload()

    assert payload["mode"] == "missing"
    assert payload["route"] == "missing"
    assert payload["user_message"] == "missing"
    assert payload["creation_type"] == "unknown"
    assert payload["project_intake_status"] == "missing"
    assert payload["pending_action_type"] is None
    assert payload["has_pending_action"] is False
    assert payload["output_id"] is None
    assert payload["candidate_iteration_id"] is None
    assert payload["has_candidate_iteration"] is False
    assert payload["evidence_status"] == "missing"
    assert payload["artifact_count"] == 0
    assert payload["provider_health_status"] == "missing"
    assert payload["model_name"] == "missing"
    assert payload["guard_status"] == "missing"
    assert payload["project_memory_status"] == "empty"
    assert payload["project_memory_summary"] == "Project Memory: empty"
    assert payload["project_memory_manifest"] is None
    assert payload["available_context_summary"]["status"] == "missing"


def test_state_context_payload_preserves_core_fields_and_context_summary():
    payload = build_state_context_payload(
        mode="app_builder",
        route="context_clarification",
        user_message="Quiero crear una landing",
        creation_type="web",
        available_context={
            "project_intake_status": "collecting",
            "pending_action": "answer_project_intake",
            "preview_output_id": "out-1",
            "candidate_iteration_id": "iter-1",
            "artifact_count": 2,
            "provider_health": {"status": "available", "model": "qwen2.5-coder:14b"},
            "claim_guard_status": "verified",
        },
    )

    assert payload["mode"] == "app_builder"
    assert payload["route"] == "context_clarification"
    assert payload["user_message"] == "Quiero crear una landing"
    assert payload["creation_type"] == "web"
    assert payload["project_intake_status"] == "collecting"
    assert payload["pending_action_type"] == "answer_project_intake"
    assert payload["has_pending_action"] is True
    assert payload["output_id"] == "out-1"
    assert payload["candidate_iteration_id"] == "iter-1"
    assert payload["has_candidate_iteration"] is True
    assert payload["artifact_count"] == 2
    assert payload["provider_health_status"] == "available"
    assert payload["model_name"] == "qwen2.5-coder:14b"
    assert payload["guard_status"] == "verified"
    assert "preview_output_id" in payload["available_context_summary"]["keys"]


def test_state_context_prompt_explains_missing_and_unknown_semantics():
    payload = build_state_context_payload(mode="debug", user_message="debug")
    prompt = build_state_context_prompt(payload)

    assert "missing/null/empty fields" in prompt
    assert "unknown fields" in prompt
    assert "guards authorize or block actions" in prompt
    assert "Project Memory:" in prompt
    assert "Project Memory: empty" in prompt
    assert '"mode": "debug"' in prompt


def test_state_context_payload_accepts_project_memory_manifest_and_refs():
    payload = build_state_context_payload(
        mode="app_builder",
        route="context_clarification",
        user_message="Continuar",
        project_memory_manifest={
            "project_id": "project-1",
            "swarm_id": "swarm-1",
            "current_goal": "Crear app visual",
            "outputs": [{"output_id": "output-1"}],
            "evidence": [{"id": "evidence-1"}],
        },
        project_memory_refs={"output_ids": ["output-1"], "evidence_ids": ["evidence-1"]},
    )

    assert payload["project_memory_status"] == "present"
    assert "Project Memory Manifest summary" in payload["project_memory_summary"]
    assert payload["project_memory_refs"]["output_ids"] == ["output-1"]
    assert payload["project_memory_refs"]["evidence_ids"] == ["evidence-1"]
    assert payload["project_memory_manifest"]["current_goal"] == "Crear app visual"
    assert payload["project_memory_manifest"]["outputs"] == [{"output_id": "output-1"}]


def test_state_context_prompt_includes_project_memory_when_present():
    payload = build_state_context_payload(
        project_memory_manifest={
            "project_id": "project-1",
            "swarm_id": "swarm-1",
            "outputs": [{"output_id": "output-1"}],
        }
    )

    prompt = build_state_context_prompt(payload)

    assert "Project Memory:" in prompt
    assert "status: present" in prompt
    assert "Project Memory Manifest summary" in prompt
    assert '"output_ids": ["output-1"]' in prompt


def test_normalize_state_context_value_is_json_safe_and_bounded():
    normalized = normalize_state_context_value(
        {
            "long": "x" * 1000,
            "items": list(range(20)),
            "nested": {"b": 2, "a": None},
        }
    )

    assert len(normalized["long"]) == 600
    assert len(normalized["items"]) == 12
    assert normalized["nested"] == {"a": None, "b": 2}
    json.dumps(normalized)


def test_state_context_payload_supports_mini_agent_context_budget_fields():
    payload = build_state_context_payload(
        mode="swarm_card",
        route="mini_agent_runtime",
        user_message="Crear componente visual",
        agent_id="agent-1",
        mini_agent_id="mini-1",
        task_id="task-1",
        context_budget_used=1200,
        context_budget_total=32000,
        context_budget_source="configured",
        context_sections=["swarm_goal", "task_contract", "allowed_files"],
        allowed_files=["frontend/src/App.tsx"],
        relevant_files=["frontend/src/styles.css"],
        forbidden_files=["backend/main.py"],
        dependency_outputs=[{"task_id": "task-0", "summary": "Base UI creada"}],
        tools_allowed=["read_file", "edit_file"],
        memory_scope="project:ui",
        freshness_refs={"frontend/src/App.tsx": {"hash": "abc123", "fresh": True}},
    )

    assert payload["agent_id"] == "agent-1"
    assert payload["mini_agent_id"] == "mini-1"
    assert payload["task_id"] == "task-1"
    assert payload["context_budget_used"] == 1200
    assert payload["context_budget_total"] == 32000
    assert payload["context_budget_source"] == "configured"
    assert payload["context_sections"] == ["swarm_goal", "task_contract", "allowed_files"]
    assert payload["allowed_files"] == ["frontend/src/App.tsx"]
    assert payload["relevant_files"] == ["frontend/src/styles.css"]
    assert payload["forbidden_files"] == ["backend/main.py"]
    assert payload["dependency_outputs"][0]["task_id"] == "task-0"
    assert payload["tools_allowed"] == ["read_file", "edit_file"]
    assert payload["memory_scope"] == "project:ui"
    assert payload["freshness_refs"]["frontend/src/App.tsx"]["fresh"] is True


def test_state_context_prompt_highlights_mini_agent_context_budget_sections():
    payload = build_state_context_payload(
        agent_id="agent-1",
        mini_agent_id="mini-1",
        task_id="task-1",
        context_budget_used=1200,
        context_budget_total=32000,
        context_budget_source="configured",
        context_sections=["swarm_goal", "task_contract"],
        allowed_files=["frontend/src/App.tsx"],
        relevant_files=["frontend/src/styles.css"],
        forbidden_files=["backend/main.py"],
        dependency_outputs=[{"task_id": "task-0"}],
        tools_allowed=["read_file"],
        memory_scope="project:ui",
        freshness_refs={"frontend/src/App.tsx": {"fresh": True}},
    )

    prompt = build_state_context_prompt(payload)

    assert "MiniAgent Context:" in prompt
    assert "Context Budget:" in prompt
    assert "MiniAgent Files / Tools:" in prompt
    assert "agent_id: agent-1" in prompt
    assert "mini_agent_id: mini-1" in prompt
    assert "task_id: task-1" in prompt
    assert "memory_scope: project:ui" in prompt
    assert "used: 1200" in prompt
    assert "total: 32000" in prompt
    assert "source: configured" in prompt
    assert "frontend/src/App.tsx" in prompt
    assert "read_file" in prompt


def test_state_context_payload_accepts_code_actions_without_execution():
    action = build_code_action_contract(
        action_id="act-1",
        action_type="edit_file",
        title="Edit state context",
        affected_files=[{"path": "backend/apps/swarms/state_context.py", "operation": "write"}],
        suggested_commands=[{"command": "python -m pytest backend/tests/test_state_context.py -q"}],
    )

    payload = build_state_context_payload(
        mode="swarm_card",
        route="code_action_review",
        code_actions=[action],
    )

    assert payload["code_action_status"] == "present"
    assert payload["code_action_count"] == 1
    assert "type=edit_file" in payload["code_action_summary"]
    assert payload["code_actions"][0]["action_id"] == "act-1"
    assert payload["code_actions"][0]["executed"] is False
    assert payload["code_actions"][0]["execution_result"] is None


def test_state_context_payload_accepts_code_actions_from_available_context():
    action = build_code_action_contract(
        action_id="act-2",
        action_type="run_command",
        suggested_commands=[{"command": "git diff --stat"}],
    )

    payload = build_state_context_payload(
        available_context={"code_actions": [action]},
    )

    assert payload["code_action_status"] == "present"
    assert payload["code_action_count"] == 1
    assert payload["code_actions"][0]["action_type"] == "run_command"
    assert payload["code_actions"][0]["executed"] is False


def test_state_context_prompt_includes_code_action_context():
    action = build_code_action_contract(
        action_id="act-3",
        action_type="apply_patch",
        affected_files=[{"path": "backend/apps/swarms/code_action.py", "operation": "patch"}],
    )
    payload = build_state_context_payload(code_actions=[action])

    prompt = build_state_context_prompt(payload)

    assert "Code Actions:" in prompt
    assert "status: present" in prompt
    assert "count: 1" in prompt
    assert "type=apply_patch" in prompt
    assert "backend/apps/swarms/code_action.py" in prompt
    assert '"executed": false' in prompt


def test_state_context_payload_accepts_pending_code_actions_without_execution():
    action = build_code_action_contract(
        action_id="act-pending-1",
        action_type="edit_file",
        affected_files=[{"path": "backend/apps/swarms/state_context.py", "operation": "write"}],
    )
    pending = build_code_action_pending_action(
        action,
        allowed_files=["backend/apps/swarms/state_context.py"],
        granted_permissions=["filesystem_write"],
    )

    payload = build_state_context_payload(
        mode="swarm_card",
        route="pending_code_action_review",
        pending_action_type="code_action",
        pending_code_actions=[pending],
    )

    assert payload["pending_action_type"] == "code_action"
    assert payload["has_pending_action"] is True
    assert payload["pending_code_action_status"] == "present"
    assert payload["pending_code_action_count"] == 1
    assert "pending_status=pending_approval" in payload["pending_code_action_summary"]
    assert payload["pending_code_actions"][0]["pending_action_type"] == "code_action"
    assert payload["pending_code_actions"][0]["code_action"]["action_id"] == "act-pending-1"
    assert payload["pending_code_actions"][0]["executed"] is False
    assert payload["pending_code_actions"][0]["execution_allowed"] is False
    assert payload["pending_code_actions"][0]["execution_result"] is None


def test_state_context_payload_accepts_pending_code_actions_from_available_context():
    action = build_code_action_contract(
        action_id="act-pending-2",
        action_type="run_command",
        suggested_commands=[{"command": "git diff --stat"}],
    )
    pending = build_code_action_pending_action(action, granted_permissions=["command_execution"])

    payload = build_state_context_payload(
        available_context={
            "pending_action": "code_action",
            "pending_code_actions": [pending],
        }
    )

    assert payload["pending_action_type"] == "code_action"
    assert payload["pending_code_action_status"] == "present"
    assert payload["pending_code_actions"][0]["code_action"]["action_type"] == "run_command"
    assert payload["pending_code_actions"][0]["executed"] is False


def test_state_context_prompt_includes_pending_code_action_context():
    action = build_code_action_contract(
        action_id="act-pending-3",
        action_type="apply_patch",
        affected_files=[{"path": "backend/apps/swarms/code_action.py", "operation": "patch"}],
    )
    pending = build_code_action_pending_action(
        action,
        allowed_files=["backend/apps/swarms/code_action.py"],
        granted_permissions=["filesystem_write"],
    )
    payload = build_state_context_payload(
        pending_action_type="code_action",
        pending_code_actions=[pending],
    )

    prompt = build_state_context_prompt(payload)

    assert "Pending Code Actions:" in prompt
    assert "pending_status=pending_approval" in prompt
    assert "act-pending-3" in prompt
    assert "backend/apps/swarms/code_action.py" in prompt
    assert '"executed": false' in prompt
    assert '"execution_allowed": false' in prompt


def test_state_context_payload_accepts_eval_harness_without_execution():
    loop = build_eval_loop_contract(
        loop_id="eval-loop-1",
        objective="Evaluate RI response.",
        task_kind="response_intelligence",
        nodes=[
            build_eval_evaluator_node(
                metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "passed", "score": 0.9}],
                evidence_refs=["state_context"],
            )
        ],
    )

    payload = build_state_context_payload(
        mode="swarm_card",
        route="eval_review",
        eval_harness=loop,
    )

    assert payload["eval_harness_status"] == "present"
    assert payload["eval_harness"]["loop_id"] == "eval-loop-1"
    assert payload["eval_harness"]["executed"] is False
    assert payload["eval_harness"]["stop_decision"]["executed"] is False
    assert payload["eval_memory_record"]["kind"] == "eval_memory_record"
    assert payload["eval_memory_record"]["persisted"] is False
    assert payload["eval_memory_record"]["executed"] is False
    assert "Eval Memory:" in payload["eval_harness_summary"]


def test_state_context_payload_accepts_eval_harness_from_available_context():
    loop = build_eval_loop_contract(
        loop_id="eval-loop-2",
        task_kind="code_action_review",
        nodes=[
            build_eval_evaluator_node(
                metrics=[{"metric_id": "safety", "name": "Safety", "status": "failed", "score": 0.2}],
                blockers=["false execution claim"],
            )
        ],
    )

    payload = build_state_context_payload(
        available_context={"eval_harness": loop},
    )

    assert payload["eval_harness_status"] == "present"
    assert payload["eval_harness"]["loop_id"] == "eval-loop-2"
    assert payload["eval_memory_record"]["status"] == "blocked"
    assert payload["eval_memory_record"]["blockers"] == ["false execution claim"]


def test_state_context_payload_accepts_eval_memory_record_without_rebuilding_loop():
    loop = build_eval_loop_contract(
        loop_id="eval-loop-3",
        task_kind="response_intelligence",
        nodes=[
            build_eval_evaluator_node(
                metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "passed", "score": 1.0}],
                evidence_refs=["state_context"],
            )
        ],
    )
    memory = build_eval_memory_record(loop_contract=loop, memory_id="eval-memory-3")

    payload = build_state_context_payload(eval_memory_record=memory)

    assert payload["eval_harness_status"] == "present"
    assert payload["eval_harness"] is None
    assert payload["eval_memory_record"]["memory_id"] == "eval-memory-3"
    assert payload["eval_memory_record"]["persisted"] is False


def test_state_context_prompt_includes_eval_harness_context():
    loop = build_eval_loop_contract(
        loop_id="eval-loop-4",
        task_kind="response_intelligence",
        nodes=[
            build_eval_evaluator_node(
                metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "passed", "score": 1.0}],
                evidence_refs=["state_context"],
            )
        ],
    )
    payload = build_state_context_payload(eval_harness=loop)

    prompt = build_state_context_prompt(payload)

    assert "Eval Harness:" in prompt
    assert "status: present" in prompt
    assert "Eval Memory:" in prompt
    assert "eval-loop-4" in prompt
    assert '"executed": false' in prompt
    assert '"persisted": false' in prompt


def test_state_context_payload_accepts_mcp_context_from_arguments():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "Unity", "mcp_config": {"type": "stdio"}, "auth_status": "expired"},
        ],
    )
    inspection = inspect_mcp_tool_registry(registry, target_server_name="Unity")
    fallback_plan = build_mcp_fallback_plan(
        inspection=inspection,
        fallback_adapters=[
            build_mcp_fallback_adapter_contract(
                server_name="Unity",
                fallback_type="script",
                script_path="tools/unity_cli_adapter.py",
            )
        ],
        target_server_name="Unity",
    )
    sandbox_policy = build_mcp_sandbox_policy_decision(
        fallback_plan=fallback_plan,
        allowed_script_roots=["tools/unity"],
    )
    evidence = build_mcp_evidence_record(
        server_name="Unity",
        registry=registry,
        inspection=inspection,
        fallback_plan=fallback_plan,
    )

    payload = build_state_context_payload(
        mcp_registry=registry,
        mcp_inspection=inspection,
        mcp_fallback_plan=fallback_plan,
        mcp_sandbox_policy=sandbox_policy,
        mcp_evidence_bundle={"contract_kind": "mcp_evidence_bundle", "records": [evidence], "record_count": 1},
    )

    assert payload["mcp_context_status"] == "present"
    assert "MCP Registry:" in payload["mcp_context_summary"]
    assert "MCP Inspection:" in payload["mcp_context_summary"]
    assert "MCP Fallback Plan:" in payload["mcp_context_summary"]
    assert "MCP Sandbox Policy:" in payload["mcp_context_summary"]
    assert payload["mcp_registry"]["server_count"] == 1
    assert payload["mcp_inspection"]["target_server_name"] == "unity"
    assert payload["mcp_fallback_plan"]["target_server_name"] == "unity"
    assert payload["mcp_sandbox_policy"]["contract_kind"] == "mcp_sandbox_policy_decision"
    assert payload["mcp_evidence_bundle"]["record_count"] == 1
    assert payload["mcp_required_user_action_count"] >= 1


def test_state_context_payload_accepts_mcp_context_from_available_context():
    registry = build_mcp_tool_registry(
        tools=[
            {"name": "Unity", "mcp_config": {"type": "stdio"}, "auth_status": "connected"},
        ],
        active_mcps=["Unity"],
    )

    payload = build_state_context_payload(
        available_context={"mcp_registry": registry},
    )

    assert payload["mcp_context_status"] == "present"
    assert payload["mcp_registry"]["active_server_count"] == 1
    assert "MCP Registry:" in payload["mcp_context_summary"]


def test_state_context_prompt_includes_mcp_context():
    inspection = inspect_mcp_tool_registry(build_mcp_tool_registry(tools=[]), target_server_name="Unity")
    payload = build_state_context_payload(mcp_inspection=inspection)

    prompt = build_state_context_prompt(payload)

    assert "MCP Context:" in prompt
    assert "status: present" in prompt
    assert "mcp_target_not_installed" in prompt
    assert "tools/mcp/unity" in prompt
    assert '"executed": false' in prompt
