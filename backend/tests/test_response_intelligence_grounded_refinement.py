from backend.apps.agents.orchestration.models import AgentContract, SwarmState
from backend.apps.swarms.code_action import build_code_action_contract, build_code_action_pending_action
from backend.apps.swarms.eval_harness import build_eval_critic_node, build_eval_evaluator_node, build_eval_loop_contract, build_eval_memory_record
from backend.apps.swarms.response_intelligence import build_grounded_code_action_response, build_grounded_refinement_response, build_response_context
from backend.apps.swarms.swarms import _refinement_request_response


def _chat_swarm() -> SwarmState:
    coordinator = AgentContract(
        role="CoordinatorAgent",
        objective="Answer grounded swarm chat messages.",
        allowed_tools=[],
    )
    return SwarmState(
        title="RI-3 test swarm",
        user_prompt="Build an app",
        intent="chat",
        status="draft",
        coordinator_contract_id=coordinator.id,
        contracts=[coordinator],
    )


def test_grounded_refinement_received_preserves_payload_and_ri_state():
    swarm = _chat_swarm()
    result = build_grounded_refinement_response(
        swarm,
        user_message="refine this preview",
        swarm_mode="app_builder",
        refinement_request={
            "output_id": "out-123",
            "source_swarm_id": "swarm-abc",
            "requested_change": "Cambiar el hero a azul.",
            "status": "received",
            "next_action": "refinement_pipeline_pending",
        },
    )

    assert result.requires_provider is False
    assert result.route == "refinement_request"
    assert result.payload["route"] == "refinement_request"
    assert result.payload["swarm_mode"] == "app_builder"
    assert result.payload["refinement_request"]["output_id"] == "out-123"
    assert result.payload["ri_state"]["pending_action"] == "confirm_refinement"
    assert result.payload["ri_state"]["action_stage"] == "registered"
    assert result.payload["ri_state"]["target_output_id"] == "out-123"
    assert "confirm_refinement" in result.payload["ri_state"]["available_actions"]
    assert "edit_refinement_request" in result.payload["ri_state"]["available_actions"]
    assert "cancel_refinement_request" in result.payload["ri_state"]["available_actions"]
    assert "open_preview" not in result.payload["ri_state"]["available_actions"]
    assert "Refinamiento registrado para el Output out-123." in (result.assistant_content or "")
    assert "Cambio solicitado:" in (result.assistant_content or "")
    assert "Cambiar el hero a azul." in (result.assistant_content or "")
    assert "todavía no se modificó la app" in (result.assistant_content or "")
    assert "Siguiente acción interna: confirm_refinement." in (result.assistant_content or "")


def test_grounded_refinement_confirmed_reports_run_pipeline_without_execution_claim():
    swarm = _chat_swarm()
    result = build_grounded_refinement_response(
        swarm,
        user_message="hazlo",
        swarm_mode="app_builder",
        refinement_request={
            "output_id": "out-456",
            "source_swarm_id": "swarm-def",
            "requested_change": "Agregar cards de métricas.",
            "status": "confirmed",
            "next_action": "run_refinement_pipeline",
        },
    )

    assert result.payload["ri_state"]["pending_action"] == "run_refinement_pipeline"
    assert result.payload["ri_state"]["action_stage"] == "confirmed"
    assert result.payload["ri_state"]["target_output_id"] == "out-456"
    assert "run_refinement_pipeline" in result.payload["ri_state"]["available_actions"]
    assert "Confirmación recibida para el Output out-456." in (result.assistant_content or "")
    assert "Cambio a aplicar:" in (result.assistant_content or "")
    assert "Agregar cards de métricas." in (result.assistant_content or "")
    assert "todavía no ejecuté tools ni modifiqué la app" in (result.assistant_content or "")
    assert "Siguiente acción interna: run_refinement_pipeline." in (result.assistant_content or "")


def test_grounded_refinement_missing_output_id_is_honest_and_safe():
    swarm = _chat_swarm()
    result = build_grounded_refinement_response(
        swarm,
        user_message="refine missing output",
        refinement_request={
            "output_id": "",
            "source_swarm_id": "swarm-def",
            "requested_change": "Cambiar copy.",
            "status": "received",
        },
    )

    assert result.payload["route"] == "refinement_request"
    assert result.payload["refinement_request"]["output_id"] == ""
    assert result.payload["ri_state"]["target_output_id"] is None
    assert result.payload["ri_state"]["pending_action"] is None
    assert result.payload["ri_state"]["action_stage"] is None
    assert "no encuentro un Output ID válido" in (result.assistant_content or "")
    assert "No ejecuté cambios ni reinicié el intake." in (result.assistant_content or "")


def test_swarms_refinement_confirmation_uses_grounded_ri_result_payload():
    swarm = _chat_swarm()
    swarm.final_result = {
        "refinement_request": {
            "output_id": "out-existing",
            "source_swarm_id": "source-existing",
            "requested_change": "Reducir padding.",
            "status": "received",
            "next_action": "refinement_pipeline_pending",
        }
    }

    content, payload = _refinement_request_response("hazlo", swarm, swarm_mode="app_builder")

    assert payload["route"] == "refinement_request"
    assert payload["swarm_mode"] == "app_builder"
    assert payload["refinement_request"]["status"] == "confirmed"
    assert payload["refinement_request"]["next_action"] == "run_refinement_pipeline"
    assert payload["ri_state"]["pending_action"] == "run_refinement_pipeline"
    assert payload["ri_state"]["action_stage"] == "confirmed"
    assert payload["ri_state"]["target_output_id"] == "out-existing"
    assert "Dejé ese cambio preparado" in content
    assert "Todavía no modifiqué la app" in content


def test_action_stage_prepared_comes_from_prepare_output_refinement_metadata():
    swarm = _chat_swarm()
    swarm.final_result = {
        "refinement_request": {
            "output_id": "out-prepared",
            "source_swarm_id": "source-prepared",
            "requested_change": "Mejorar contraste.",
            "status": "confirmed",
            "next_action": "run_refinement_pipeline",
        },
        "prepare_output_refinement": {
            "metadata": {
                "output_id": "out-prepared",
                "requested_change": "Mejorar contraste.",
                "refinement_status": "prepared",
            },
            "validation_errors": [],
        },
    }

    result = build_grounded_refinement_response(
        swarm,
        user_message="estado",
        swarm_mode="app_builder",
        refinement_request=swarm.final_result["refinement_request"],
    )

    assert result.payload["ri_state"]["pending_action"] == "run_refinement_pipeline"
    assert result.payload["ri_state"]["action_stage"] == "prepared"
    assert "action_stage=prepared" in result.payload["ri_state"]["reason"]


def test_response_context_includes_action_stage_policy_for_model_reasoning():
    swarm = _chat_swarm()
    swarm.final_result = {
        "refinement_request": {
            "output_id": "out-context",
            "source_swarm_id": "source-context",
            "requested_change": "Mejorar la jerarquía visual.",
            "status": "confirmed",
            "next_action": "run_refinement_pipeline",
        },
        "prepare_output_refinement": {
            "metadata": {
                "output_id": "out-context",
                "requested_change": "Mejorar la jerarquía visual.",
                "refinement_status": "prepared",
            },
            "validation_errors": [],
        },
    }

    context = build_response_context(
        swarm,
        route="refinement_request",
        user_message="aplicalo",
    )

    assert "- action_stage: prepared" in context
    assert "[action_semantics_policy]" in context
    assert "action_stage is computed by the system and is authoritative" in context
    assert "preparation happened but execution did not" in context


def test_grounded_code_action_response_reviews_pending_action_without_execution():
    swarm = _chat_swarm()
    action = build_code_action_contract(
        action_id="act-ri-1",
        action_type="edit_file",
        title="Update RI code action flow",
        affected_files=[{"path": "backend/apps/swarms/response_intelligence.py", "operation": "write"}],
        suggested_commands=[{"command": "python -m pytest backend/tests/test_response_intelligence_grounded_refinement.py -q"}],
        expected_evidence=["diff summary", "pytest output"],
    )
    pending = build_code_action_pending_action(
        action,
        allowed_files=["backend/apps/swarms/response_intelligence.py"],
        granted_permissions=["filesystem_write"],
    )

    result = build_grounded_code_action_response(
        swarm,
        user_message="review this code action",
        swarm_mode="debug",
        pending_code_action=pending,
    )

    assert result.requires_provider is False
    assert result.route == "code_action_review"
    assert result.response_source == "local_grounded_code_action"
    assert result.payload["route"] == "code_action_review"
    assert result.payload["swarm_mode"] == "debug"
    assert result.payload["code_action_review"]["status"] == "review_ready"
    assert result.payload["code_action_review"]["executed"] is False
    assert result.payload["code_action_review"]["execution_allowed"] is False
    assert result.payload["code_action_review"]["execution_result"] is None
    assert "Pending code action: Update RI code action flow" in (result.assistant_content or "")
    assert "Guard: pending_approval" in (result.assistant_content or "")
    assert "backend/apps/swarms/response_intelligence.py" in (result.assistant_content or "")
    assert "no se ejecutó nada" in (result.assistant_content or "")


def test_grounded_code_action_response_explains_blocked_pending_action():
    swarm = _chat_swarm()
    action = build_code_action_contract(
        action_id="act-ri-2",
        action_type="run_command",
        title="Dangerous RI command",
        suggested_commands=[{"command": "git push --force"}],
    )
    pending = build_code_action_pending_action(action, granted_permissions=["command_execution"])

    result = build_grounded_code_action_response(
        swarm,
        user_message="review blocked action",
        pending_code_action=pending,
    )

    assert result.requires_provider is False
    assert result.payload["code_action_review"]["status"] == "blocked"
    assert result.payload["code_action_review"]["executed"] is False
    assert "Dangerous RI command" in (result.assistant_content or "")
    assert "Guard: blocked" in (result.assistant_content or "")
    assert "dangerous_command" in (result.assistant_content or "")
    assert "no se ejecutó nada" in (result.assistant_content or "")


def test_response_context_includes_eval_harness_for_model_reasoning():
    swarm = _chat_swarm()
    loop = build_eval_loop_contract(
        loop_id="ri-eval-loop-1",
        task_kind="response_intelligence",
        nodes=[
            build_eval_critic_node(
                findings=[{"finding_id": "finding-ri-1", "summary": "Missing evidence."}]
            ),
            build_eval_evaluator_node(
                metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "failed", "score": 0.2}],
                blockers=["missing evidence"],
            ),
        ],
    )
    swarm.final_result = {"eval_harness": loop}

    context = build_response_context(
        swarm,
        route="chat",
        user_message="explica estado",
    )

    assert "[eval_harness]" in context
    assert "ri-eval-loop-1" in context
    assert "stop_reason: blocked" in context
    assert "needs_refinement: True" in context
    assert "blockers: missing evidence" in context


def test_ri_state_snapshot_includes_eval_harness_summary_and_blockers():
    swarm = _chat_swarm()
    loop = build_eval_loop_contract(
        loop_id="ri-eval-loop-2",
        task_kind="code_action_review",
        nodes=[
            build_eval_evaluator_node(
                metrics=[{"metric_id": "safety", "name": "Safety", "status": "failed", "score": 0.1}],
                blockers=["false execution claim"],
            )
        ],
    )
    swarm.final_result = {"eval_harness": loop}

    result = build_grounded_refinement_response(
        swarm,
        user_message="estado",
        refinement_request={
            "output_id": "out-eval-ri",
            "source_swarm_id": "swarm-eval-ri",
            "requested_change": "Revisar evidencia.",
            "status": "received",
        },
    )

    assert result.payload["ri_state"]["eval_harness_status"] == "present"
    assert result.payload["ri_state"]["eval_stop_reason"] == "blocked"
    assert result.payload["ri_state"]["eval_blockers"] == ["false execution claim"]
    assert result.payload["ri_state"]["eval_needs_refinement"] is True
    assert "eval_harness=present" in result.payload["ri_state"]["reason"]
    assert "eval_stop_reason=blocked" in result.payload["ri_state"]["reason"]
    assert result.payload["eval_harness"]["loop_id"] == "ri-eval-loop-2"
    assert result.payload["eval_memory_record"] is None


def test_ri_result_accepts_eval_memory_record_from_payload_without_execution():
    swarm = _chat_swarm()
    loop = build_eval_loop_contract(
        loop_id="ri-eval-loop-3",
        task_kind="response_intelligence",
        nodes=[
            build_eval_evaluator_node(
                metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "passed", "score": 1.0}],
                evidence_refs=["state_context"],
            )
        ],
    )
    memory = build_eval_memory_record(loop_contract=loop, memory_id="ri-memory-3")

    result = build_grounded_code_action_response(
        swarm,
        user_message="review with eval memory",
        pending_code_action=build_code_action_pending_action(
            build_code_action_contract(action_id="act-eval-ri", action_type="run_command"),
            granted_permissions=["command_execution"],
        ),
        swarm_mode="debug",
    )

    result_with_eval = build_response_context(
        swarm,
        route="code_action_review",
        user_message="review with eval memory",
        payload={"eval_memory_record": memory},
    )

    assert result.payload["code_action_review"]["executed"] is False
    assert "[eval_harness]" in result_with_eval
    assert "ri-eval-loop-3" in result_with_eval
    assert "passed: True" in result_with_eval
    assert "score: 1.0" in result_with_eval
