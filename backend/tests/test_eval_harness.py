from backend.apps.swarms.eval_harness import (
    build_default_eval_critic_node,
    build_default_eval_evaluator_node,
    build_default_eval_generator_node,
    build_default_eval_loop_contract,
    build_default_eval_planner_node,
    build_default_eval_refiner_node,
    build_eval_critic_node,
    build_eval_memory_record,
    build_eval_evaluator_node,
    build_eval_generator_node,
    build_eval_loop_contract,
    build_eval_planner_node,
    build_eval_refiner_node,
    collect_eval_loop_memory_items,
    evaluate_eval_loop_stop_policy,
    normalize_eval_critic_finding,
    normalize_eval_final_decision,
    normalize_eval_generator_candidate,
    normalize_eval_metric,
    normalize_eval_node,
    normalize_eval_planner_criterion,
    normalize_eval_refinement_proposal,
    normalize_eval_stop_policy,
    summarize_eval_loop,
    summarize_eval_memory_record,
)


def test_normalize_eval_metric_clamps_score_and_preserves_evidence_refs():
    metric = normalize_eval_metric(
        {
            "metric_id": "json",
            "name": "JSON validity",
            "status": "passed",
            "score": 1.7,
            "severity": "low",
            "evidence_refs": ["test:json", ""],
        }
    )

    assert metric["metric_id"] == "json"
    assert metric["status"] == "passed"
    assert metric["score"] == 1.0
    assert metric["severity"] == "low"
    assert metric["evidence_refs"] == ["test:json"]


def test_normalize_eval_node_never_marks_execution():
    node = normalize_eval_node(
        {
            "node_id": "critic-1",
            "node_type": "critic",
            "status": "ready",
            "objective": "Review contract safety.",
            "metrics": [{"name": "Safety", "score": 0.75}],
            "requires_provider": True,
            "executed": True,
            "execution_result": {"claimed": True},
        }
    )

    assert node["node_id"] == "critic-1"
    assert node["node_type"] == "critic"
    assert node["status"] == "ready"
    assert node["requires_provider"] is True
    assert node["executed"] is False
    assert node["execution_result"] is None
    assert node["metrics"][0]["score"] == 0.75


def test_normalize_eval_stop_policy_bounds_iterations_and_score():
    policy = normalize_eval_stop_policy({"max_iterations": 50, "min_score": -1, "stop_on_pass": False})

    assert policy["max_iterations"] == 12
    assert policy["min_score"] == 0.0
    assert policy["stop_on_pass"] is False
    assert policy["stop_on_failed"] is False
    assert policy["stop_on_blocked"] is True
    assert policy["stop_on_max_iterations"] is True
    assert policy["allow_refinement"] is True
    assert policy["require_evidence"] is True


def test_build_eval_loop_contract_is_side_effect_free_contract():
    contract = build_eval_loop_contract(
        loop_id="loop-1",
        objective="Evaluate grounded code action response.",
        task_kind="code_action_review",
        status="ready",
        nodes=[
            {"node_id": "planner", "node_type": "planner", "status": "ready", "score": 0.9},
            {"node_id": "evaluator", "node_type": "evaluator", "status": "draft", "score": 0.4},
        ],
        stop_policy={"max_iterations": 2, "min_score": 0.85},
    )

    assert contract["loop_id"] == "loop-1"
    assert contract["kind"] == "eval_loop_contract"
    assert contract["status"] == "ready"
    assert contract["task_kind"] == "code_action_review"
    assert contract["node_count"] == 2
    assert contract["stop_policy"]["max_iterations"] == 2
    assert contract["executed"] is False
    assert contract["execution_result"] is None
    assert "planner=1" in contract["summary"]
    assert "evaluator=1" in contract["summary"]
    assert "executed=False" in contract["summary"]


def test_build_default_eval_loop_contract_contains_all_loop_nodes():
    contract = build_default_eval_loop_contract(
        objective="Evaluate response intelligence.",
        task_kind="response_intelligence",
    )

    node_types = [node["node_type"] for node in contract["nodes"]]

    assert contract["kind"] == "eval_loop_contract"
    assert contract["objective"] == "Evaluate response intelligence."
    assert contract["task_kind"] == "response_intelligence"
    assert node_types == ["planner", "generator", "critic", "refiner", "evaluator"]
    assert contract["node_count"] == 5
    assert contract["stop_policy"]["max_iterations"] == 3
    assert contract["executed"] is False


def test_summarize_eval_loop_handles_empty_nodes():
    summary = summarize_eval_loop(nodes=[], stop_policy={}, status="draft")

    assert summary == "Eval Loop: status=draft; nodes=0; types=none; max_iterations=3; min_score=0.8; executed=False"


def test_normalize_eval_planner_criterion_preserves_required_evidence():
    criterion = normalize_eval_planner_criterion(
        {
            "criterion_id": "grounding",
            "name": "Grounding",
            "description": "Claims must be grounded.",
            "severity": "critical",
            "metric_refs": ["grounding"],
            "evidence_required": ["state_context", ""],
        }
    )

    assert criterion["criterion_id"] == "grounding"
    assert criterion["name"] == "Grounding"
    assert criterion["severity"] == "critical"
    assert criterion["metric_refs"] == ["grounding"]
    assert criterion["evidence_required"] == ["state_context"]
    assert criterion["required"] is True


def test_build_eval_planner_node_creates_non_executing_planner_contract():
    planner = build_eval_planner_node(
        node_id="planner-1",
        objective="Plan RI evaluation.",
        task_kind="response_intelligence",
        criteria=[
            {
                "criterion_id": "contract",
                "name": "Contract",
                "metric_refs": ["contract_validity"],
                "evidence_required": ["expected_json"],
            }
        ],
        expected_metrics=[
            {"metric_id": "contract_validity", "name": "Contract validity", "status": "draft", "score": 0.2}
        ],
        required_evidence=["state_context"],
        risks=["contract_drift"],
        suggested_nodes=[
            {"node_id": "critic", "node_type": "critic", "objective": "Review defects."}
        ],
    )

    assert planner["node_id"] == "planner-1"
    assert planner["node_type"] == "planner"
    assert planner["status"] == "ready"
    assert planner["objective"] == "Plan RI evaluation."
    assert planner["requires_provider"] is False
    assert planner["executed"] is False
    assert planner["execution_result"] is None
    assert planner["metadata"]["task_kind"] == "response_intelligence"
    assert planner["metadata"]["criteria"][0]["criterion_id"] == "contract"
    assert planner["metadata"]["expected_metrics"][0]["metric_id"] == "contract_validity"
    assert planner["metadata"]["required_evidence"] == ["state_context"]
    assert planner["metadata"]["risks"] == ["contract_drift"]
    assert planner["metadata"]["suggested_nodes"][0]["node_type"] == "critic"


def test_build_default_eval_planner_node_contains_core_open_swarm_criteria():
    planner = build_default_eval_planner_node(
        objective="Evaluate code action review.",
        task_kind="code_action_review",
    )

    criterion_ids = [item["criterion_id"] for item in planner["metadata"]["criteria"]]
    metric_ids = [item["metric_id"] for item in planner["metadata"]["expected_metrics"]]

    assert planner["node_type"] == "planner"
    assert planner["objective"] == "Evaluate code action review."
    assert planner["metadata"]["task_kind"] == "code_action_review"
    assert criterion_ids == ["contract_validity", "grounding", "safety"]
    assert metric_ids == ["contract_validity", "grounding", "safety"]
    assert "false_execution_claim" in planner["metadata"]["risks"]
    assert planner["executed"] is False


def test_default_eval_loop_uses_rich_planner_node_contract():
    contract = build_default_eval_loop_contract(
        objective="Evaluate response intelligence.",
        task_kind="response_intelligence",
    )

    planner = contract["nodes"][0]

    assert planner["node_type"] == "planner"
    assert planner["metadata"]["task_kind"] == "response_intelligence"
    assert [item["criterion_id"] for item in planner["metadata"]["criteria"]] == [
        "contract_validity",
        "grounding",
        "safety",
    ]
    assert planner["executed"] is False


def test_normalize_eval_generator_candidate_preserves_refs_without_generation():
    candidate = normalize_eval_generator_candidate(
        {
            "candidate_id": "cand-1",
            "kind": "code_action_review",
            "status": "ready",
            "summary": "Candidate summary.",
            "content_ref": "final_result.summary",
            "artifact_refs": ["artifact-1", ""],
            "evidence_refs": ["evidence-1"],
            "source_refs": ["state_context"],
            "claims": ["No execution happened."],
            "generated": True,
            "executed": True,
            "execution_result": {"claimed": True},
        }
    )

    assert candidate["candidate_id"] == "cand-1"
    assert candidate["kind"] == "code_action_review"
    assert candidate["status"] == "ready"
    assert candidate["content_ref"] == "final_result.summary"
    assert candidate["artifact_refs"] == ["artifact-1"]
    assert candidate["evidence_refs"] == ["evidence-1"]
    assert candidate["source_refs"] == ["state_context"]
    assert candidate["claims"] == ["No execution happened."]
    assert candidate["generated"] is False
    assert candidate["executed"] is False
    assert candidate["execution_result"] is None


def test_build_eval_generator_node_creates_non_generating_candidate_contract():
    generator = build_eval_generator_node(
        node_id="generator-1",
        objective="Represent RI response candidate.",
        task_kind="response_intelligence",
        candidates=[
            {
                "candidate_id": "cand-2",
                "kind": "assistant_response",
                "summary": "Grounded response candidate.",
                "claims": ["Uses RI state."],
            }
        ],
        input_refs=["state_context"],
        output_refs=["candidate:cand-2"],
        claims=["Candidate exists for evaluation."],
        artifact_refs=["artifact-a"],
        evidence_refs=["evidence-a"],
        source_refs=["ri_state"],
    )

    assert generator["node_id"] == "generator-1"
    assert generator["node_type"] == "generator"
    assert generator["status"] == "ready"
    assert generator["objective"] == "Represent RI response candidate."
    assert generator["input_refs"] == ["state_context"]
    assert generator["output_refs"] == ["candidate:cand-2"]
    assert generator["requires_provider"] is False
    assert generator["executed"] is False
    assert generator["execution_result"] is None
    assert generator["metadata"]["task_kind"] == "response_intelligence"
    assert generator["metadata"]["candidates"][0]["candidate_id"] == "cand-2"
    assert generator["metadata"]["claims"] == ["Candidate exists for evaluation."]
    assert generator["metadata"]["artifact_refs"] == ["artifact-a"]
    assert generator["metadata"]["evidence_refs"] == ["evidence-a"]
    assert generator["metadata"]["source_refs"] == ["ri_state"]


def test_build_default_eval_generator_node_is_empty_and_non_executing():
    generator = build_default_eval_generator_node(
        objective="Represent code action review candidate.",
        task_kind="code_action_review",
    )

    assert generator["node_type"] == "generator"
    assert generator["objective"] == "Represent code action review candidate."
    assert generator["metadata"]["task_kind"] == "code_action_review"
    assert generator["metadata"]["candidates"] == []
    assert generator["metadata"]["metadata"]["candidate_source"] == "not_provided"
    assert generator["executed"] is False
    assert generator["execution_result"] is None


def test_default_eval_loop_uses_rich_generator_node_contract():
    contract = build_default_eval_loop_contract(
        objective="Evaluate response intelligence.",
        task_kind="response_intelligence",
    )

    generator = contract["nodes"][1]

    assert generator["node_type"] == "generator"
    assert generator["metadata"]["task_kind"] == "response_intelligence"
    assert generator["metadata"]["candidates"] == []
    assert generator["executed"] is False


def test_normalize_eval_critic_finding_preserves_missing_evidence_and_recommendation():
    finding = normalize_eval_critic_finding(
        {
            "finding_id": "finding-1",
            "kind": "unsupported_claim",
            "status": "needs_refinement",
            "severity": "critical",
            "summary": "Claim lacks evidence.",
            "claim_ref": "claim:no_execution",
            "criterion_ref": "grounding",
            "metric_ref": "grounding",
            "evidence_refs": ["state_context"],
            "missing_evidence": ["execution_result"],
            "recommendation": "Remove execution claim or provide evidence.",
        }
    )

    assert finding["finding_id"] == "finding-1"
    assert finding["kind"] == "unsupported_claim"
    assert finding["status"] == "needs_refinement"
    assert finding["severity"] == "critical"
    assert finding["claim_ref"] == "claim:no_execution"
    assert finding["evidence_refs"] == ["state_context"]
    assert finding["missing_evidence"] == ["execution_result"]
    assert finding["recommendation"] == "Remove execution claim or provide evidence."


def test_build_eval_critic_node_creates_non_executing_critic_contract():
    critic = build_eval_critic_node(
        node_id="critic-1",
        objective="Critique RI response candidate.",
        task_kind="response_intelligence",
        findings=[
            {
                "finding_id": "finding-2",
                "kind": "contract_violation",
                "severity": "high",
                "summary": "Missing required field.",
                "missing_evidence": ["expected_contract"],
            }
        ],
        unsupported_claims=["Tests passed without evidence."],
        contract_violations=["missing evidence_refs"],
        missing_evidence=["pytest output"],
        refinement_recommendations=["Add evidence_refs or remove claim."],
        input_refs=["candidate:cand-2"],
        output_refs=["critic:finding-2"],
    )

    assert critic["node_id"] == "critic-1"
    assert critic["node_type"] == "critic"
    assert critic["status"] == "ready"
    assert critic["objective"] == "Critique RI response candidate."
    assert critic["input_refs"] == ["candidate:cand-2"]
    assert critic["output_refs"] == ["critic:finding-2"]
    assert critic["requires_provider"] is False
    assert critic["executed"] is False
    assert critic["execution_result"] is None
    assert critic["metadata"]["task_kind"] == "response_intelligence"
    assert critic["metadata"]["finding_count"] == 1
    assert critic["metadata"]["high_count"] == 1
    assert critic["metadata"]["critical_count"] == 0
    assert critic["metadata"]["unsupported_claims"] == ["Tests passed without evidence."]
    assert critic["metadata"]["contract_violations"] == ["missing evidence_refs"]
    assert critic["metadata"]["missing_evidence"] == ["pytest output"]
    assert critic["metadata"]["refinement_recommendations"] == ["Add evidence_refs or remove claim."]
    assert critic["metrics"][0]["metric_id"] == "critic_findings"
    assert critic["metrics"][0]["status"] == "needs_refinement"


def test_build_default_eval_critic_node_is_empty_and_non_executing():
    critic = build_default_eval_critic_node(
        objective="Critique code action review.",
        task_kind="code_action_review",
    )

    assert critic["node_type"] == "critic"
    assert critic["objective"] == "Critique code action review."
    assert critic["metadata"]["task_kind"] == "code_action_review"
    assert critic["metadata"]["findings"] == []
    assert critic["metadata"]["finding_count"] == 0
    assert critic["metrics"][0]["status"] == "passed"
    assert critic["metadata"]["metadata"]["critic_source"] == "not_run"
    assert critic["executed"] is False
    assert critic["execution_result"] is None


def test_default_eval_loop_uses_rich_critic_node_contract():
    contract = build_default_eval_loop_contract(
        objective="Evaluate response intelligence.",
        task_kind="response_intelligence",
    )

    critic = contract["nodes"][2]

    assert critic["node_type"] == "critic"
    assert critic["metadata"]["task_kind"] == "response_intelligence"
    assert critic["metadata"]["findings"] == []
    assert critic["metadata"]["finding_count"] == 0
    assert critic["executed"] is False


def test_normalize_eval_refinement_proposal_never_applies_changes():
    proposal = normalize_eval_refinement_proposal(
        {
            "proposal_id": "proposal-1",
            "status": "ready",
            "severity": "high",
            "summary": "Remove unsupported claim.",
            "target_ref": "candidate:cand-2",
            "finding_refs": ["finding-2", ""],
            "required_evidence": ["updated summary"],
            "expected_change": "Remove tests passed claim.",
            "risk": "claim may remain ambiguous",
            "applied": True,
            "executed": True,
            "execution_result": {"claimed": True},
        }
    )

    assert proposal["proposal_id"] == "proposal-1"
    assert proposal["status"] == "ready"
    assert proposal["severity"] == "high"
    assert proposal["target_ref"] == "candidate:cand-2"
    assert proposal["finding_refs"] == ["finding-2"]
    assert proposal["required_evidence"] == ["updated summary"]
    assert proposal["expected_change"] == "Remove tests passed claim."
    assert proposal["applied"] is False
    assert proposal["executed"] is False
    assert proposal["execution_result"] is None


def test_build_eval_refiner_node_creates_non_applying_refiner_contract():
    refiner = build_eval_refiner_node(
        node_id="refiner-1",
        objective="Refine RI response candidate.",
        task_kind="response_intelligence",
        proposals=[
            {
                "proposal_id": "proposal-2",
                "summary": "Add missing evidence refs.",
                "target_ref": "candidate:cand-2",
                "finding_refs": ["finding-2"],
                "required_evidence": ["evidence_refs"],
            }
        ],
        finding_refs=["finding-2"],
        input_refs=["critic:finding-2"],
        output_refs=["proposal:proposal-2"],
    )

    assert refiner["node_id"] == "refiner-1"
    assert refiner["node_type"] == "refiner"
    assert refiner["status"] == "ready"
    assert refiner["objective"] == "Refine RI response candidate."
    assert refiner["input_refs"] == ["critic:finding-2"]
    assert refiner["output_refs"] == ["proposal:proposal-2"]
    assert refiner["requires_provider"] is False
    assert refiner["executed"] is False
    assert refiner["execution_result"] is None
    assert refiner["metadata"]["task_kind"] == "response_intelligence"
    assert refiner["metadata"]["proposal_count"] == 1
    assert refiner["metadata"]["finding_refs"] == ["finding-2"]
    assert refiner["metadata"]["proposals"][0]["proposal_id"] == "proposal-2"
    assert refiner["metadata"]["proposals"][0]["applied"] is False
    assert refiner["metrics"][0]["metric_id"] == "refinement_proposals"
    assert refiner["metrics"][0]["status"] == "passed"


def test_build_eval_refiner_node_reports_blocked_reasons():
    refiner = build_eval_refiner_node(
        task_kind="code_action_review",
        blocked_reasons=["stop_policy_disallows_refinement"],
    )

    assert refiner["node_type"] == "refiner"
    assert refiner["metadata"]["blocked_reasons"] == ["stop_policy_disallows_refinement"]
    assert refiner["metrics"][0]["status"] == "blocked"
    assert refiner["score"] == 0.0
    assert refiner["executed"] is False


def test_build_default_eval_refiner_node_is_empty_and_non_executing():
    refiner = build_default_eval_refiner_node(
        objective="Refine code action review.",
        task_kind="code_action_review",
    )

    assert refiner["node_type"] == "refiner"
    assert refiner["objective"] == "Refine code action review."
    assert refiner["metadata"]["task_kind"] == "code_action_review"
    assert refiner["metadata"]["proposals"] == []
    assert refiner["metadata"]["proposal_count"] == 0
    assert refiner["metadata"]["metadata"]["refiner_source"] == "not_run"
    assert refiner["executed"] is False
    assert refiner["execution_result"] is None


def test_default_eval_loop_uses_rich_refiner_node_contract():
    contract = build_default_eval_loop_contract(
        objective="Evaluate response intelligence.",
        task_kind="response_intelligence",
    )

    refiner = contract["nodes"][3]

    assert refiner["node_type"] == "refiner"
    assert refiner["metadata"]["task_kind"] == "response_intelligence"
    assert refiner["metadata"]["proposals"] == []
    assert refiner["metadata"]["proposal_count"] == 0
    assert refiner["executed"] is False


def test_normalize_eval_final_decision_preserves_pass_fail_fields():
    decision = normalize_eval_final_decision(
        {
            "decision_id": "decision-1",
            "status": "failed",
            "passed": False,
            "score": 1.4,
            "summary": "Evaluation failed.",
            "needs_refinement": True,
            "blocked": False,
            "blockers": ["missing evidence"],
            "evidence_refs": ["state_context"],
            "metric_refs": ["grounding"],
        }
    )

    assert decision["decision_id"] == "decision-1"
    assert decision["status"] == "failed"
    assert decision["passed"] is False
    assert decision["score"] == 1.0
    assert decision["needs_refinement"] is True
    assert decision["blocked"] is False
    assert decision["blockers"] == ["missing evidence"]
    assert decision["evidence_refs"] == ["state_context"]
    assert decision["metric_refs"] == ["grounding"]


def test_build_eval_evaluator_node_creates_non_executing_final_result_contract():
    evaluator = build_eval_evaluator_node(
        node_id="evaluator-1",
        objective="Evaluate RI candidate.",
        task_kind="response_intelligence",
        metrics=[
            {"metric_id": "grounding", "name": "Grounding", "status": "passed", "score": 0.9},
            {"metric_id": "safety", "name": "Safety", "status": "passed", "score": 1.0},
        ],
        evidence_refs=["state_context", "ri_state"],
        input_refs=["critic:finding-2", "proposal:proposal-2"],
        output_refs=["decision:decision-1"],
    )

    assert evaluator["node_id"] == "evaluator-1"
    assert evaluator["node_type"] == "evaluator"
    assert evaluator["objective"] == "Evaluate RI candidate."
    assert evaluator["input_refs"] == ["critic:finding-2", "proposal:proposal-2"]
    assert evaluator["output_refs"] == ["decision:decision-1"]
    assert evaluator["requires_provider"] is False
    assert evaluator["executed"] is False
    assert evaluator["execution_result"] is None
    assert evaluator["metadata"]["task_kind"] == "response_intelligence"
    assert evaluator["metadata"]["final_decision"]["passed"] is True
    assert evaluator["metadata"]["final_decision"]["score"] == 0.95
    assert evaluator["metadata"]["final_decision"]["needs_refinement"] is False
    assert evaluator["metadata"]["evidence_refs"] == ["state_context", "ri_state"]
    assert evaluator["score"] == 0.95


def test_build_eval_evaluator_node_reports_blockers_and_refinement_need():
    evaluator = build_eval_evaluator_node(
        task_kind="code_action_review",
        metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "failed", "score": 0.2}],
        blockers=["missing evidence"],
    )

    assert evaluator["node_type"] == "evaluator"
    assert evaluator["metadata"]["final_decision"]["passed"] is False
    assert evaluator["metadata"]["final_decision"]["blocked"] is True
    assert evaluator["metadata"]["final_decision"]["needs_refinement"] is True
    assert evaluator["metadata"]["final_decision"]["blockers"] == ["missing evidence"]
    assert evaluator["score"] == 0.2
    assert evaluator["executed"] is False


def test_build_default_eval_evaluator_node_is_draft_and_non_executing():
    evaluator = build_default_eval_evaluator_node(
        objective="Evaluate code action review.",
        task_kind="code_action_review",
    )

    assert evaluator["node_type"] == "evaluator"
    assert evaluator["objective"] == "Evaluate code action review."
    assert evaluator["metadata"]["task_kind"] == "code_action_review"
    assert evaluator["metadata"]["final_decision"]["status"] == "draft"
    assert evaluator["metadata"]["final_decision"]["passed"] is False
    assert evaluator["metadata"]["metadata"]["evaluator_source"] == "not_run"
    assert evaluator["executed"] is False
    assert evaluator["execution_result"] is None


def test_default_eval_loop_uses_rich_evaluator_node_contract():
    contract = build_default_eval_loop_contract(
        objective="Evaluate response intelligence.",
        task_kind="response_intelligence",
    )

    evaluator = contract["nodes"][4]

    assert evaluator["node_type"] == "evaluator"
    assert evaluator["metadata"]["task_kind"] == "response_intelligence"
    assert evaluator["metadata"]["final_decision"]["status"] == "draft"
    assert evaluator["metadata"]["final_decision"]["passed"] is False
    assert evaluator["executed"] is False


def test_evaluate_eval_loop_stop_policy_stops_on_pass():
    evaluator = build_eval_evaluator_node(
        metrics=[
            {"metric_id": "grounding", "name": "Grounding", "status": "passed", "score": 0.9},
            {"metric_id": "safety", "name": "Safety", "status": "passed", "score": 1.0},
        ],
    )

    decision = evaluate_eval_loop_stop_policy(
        stop_policy={"max_iterations": 3, "min_score": 0.8},
        evaluator_node=evaluator,
        current_iteration=1,
    )

    assert decision["should_stop"] is True
    assert decision["reason"] == "passed"
    assert decision["status"] == "passed"
    assert decision["passed"] is True
    assert decision["blocked"] is False
    assert decision["needs_refinement"] is False
    assert decision["executed"] is False
    assert decision["execution_result"] is None


def test_evaluate_eval_loop_stop_policy_stops_on_blockers():
    evaluator = build_eval_evaluator_node(
        metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "failed", "score": 0.2}],
        blockers=["missing evidence"],
    )

    decision = evaluate_eval_loop_stop_policy(
        stop_policy={"max_iterations": 3, "min_score": 0.8},
        evaluator_node=evaluator,
        current_iteration=1,
    )

    assert decision["should_stop"] is True
    assert decision["reason"] == "blocked"
    assert decision["status"] == "blocked"
    assert decision["passed"] is False
    assert decision["blocked"] is True
    assert decision["needs_refinement"] is True
    assert decision["blockers"] == ["missing evidence"]


def test_evaluate_eval_loop_stop_policy_stops_on_max_iterations():
    evaluator = build_eval_evaluator_node(
        metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "failed", "score": 0.4}],
    )

    decision = evaluate_eval_loop_stop_policy(
        stop_policy={"max_iterations": 2, "min_score": 0.8},
        evaluator_node=evaluator,
        current_iteration=2,
    )

    assert decision["should_stop"] is True
    assert decision["reason"] == "max_iterations_reached"
    assert decision["status"] == "failed"
    assert decision["max_iterations_reached"] is True
    assert decision["needs_refinement"] is True


def test_evaluate_eval_loop_stop_policy_continues_when_refinement_allowed():
    evaluator = build_eval_evaluator_node(
        metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "failed", "score": 0.4}],
    )

    decision = evaluate_eval_loop_stop_policy(
        stop_policy={"max_iterations": 3, "min_score": 0.8, "allow_refinement": True},
        evaluator_node=evaluator,
        current_iteration=1,
    )

    assert decision["should_stop"] is False
    assert decision["reason"] == "continue"
    assert decision["status"] == "needs_refinement"
    assert decision["needs_refinement"] is True


def test_eval_loop_contract_includes_stop_decision_without_execution():
    contract = build_eval_loop_contract(
        objective="Evaluate loop stop decision.",
        task_kind="response_intelligence",
        nodes=[
            build_eval_evaluator_node(
                metrics=[{"metric_id": "safety", "name": "Safety", "status": "passed", "score": 1.0}]
            )
        ],
        stop_policy={"max_iterations": 3, "min_score": 0.8},
    )

    assert contract["stop_decision"]["should_stop"] is True
    assert contract["stop_decision"]["reason"] == "passed"
    assert contract["stop_decision"]["executed"] is False


def test_collect_eval_loop_memory_items_collects_findings_proposals_evidence_and_blockers():
    loop = build_eval_loop_contract(
        loop_id="loop-memory-1",
        objective="Evaluate memory collection.",
        task_kind="response_intelligence",
        nodes=[
            build_eval_critic_node(
                findings=[
                    {
                        "finding_id": "finding-memory-1",
                        "summary": "Missing evidence.",
                        "missing_evidence": ["pytest output"],
                    }
                ],
                missing_evidence=["pytest output"],
            ),
            build_eval_refiner_node(
                proposals=[
                    {
                        "proposal_id": "proposal-memory-1",
                        "summary": "Add evidence refs.",
                        "required_evidence": ["pytest output"],
                    }
                ]
            ),
            build_eval_evaluator_node(
                metrics=[{"metric_id": "grounding", "name": "Grounding", "status": "failed", "score": 0.2}],
                evidence_refs=["state_context"],
                blockers=["missing evidence"],
            ),
        ],
    )

    items = collect_eval_loop_memory_items(loop)

    assert items["findings"][0]["finding_id"] == "finding-memory-1"
    assert items["proposals"][0]["proposal_id"] == "proposal-memory-1"
    assert items["evidence_refs"] == ["state_context"]
    assert items["blockers"] == ["missing evidence"]


def test_build_eval_memory_record_is_side_effect_free_and_portable():
    loop = build_eval_loop_contract(
        loop_id="loop-memory-2",
        objective="Evaluate RI memory.",
        task_kind="response_intelligence",
        nodes=[
            build_eval_evaluator_node(
                metrics=[
                    {"metric_id": "grounding", "name": "Grounding", "status": "passed", "score": 0.9},
                    {"metric_id": "safety", "name": "Safety", "status": "passed", "score": 1.0},
                ],
                evidence_refs=["state_context", "ri_state"],
            )
        ],
        stop_policy={"max_iterations": 3, "min_score": 0.8},
    )

    record = build_eval_memory_record(
        loop_contract=loop,
        memory_id="memory-1",
        source="unit_test",
        metadata={"suite": "eval_harness"},
    )

    assert record["memory_id"] == "memory-1"
    assert record["kind"] == "eval_memory_record"
    assert record["source"] == "unit_test"
    assert record["loop_id"] == "loop-memory-2"
    assert record["task_kind"] == "response_intelligence"
    assert record["status"] == "passed"
    assert record["passed"] is True
    assert record["blocked"] is False
    assert record["needs_refinement"] is False
    assert record["score"] == 0.95
    assert record["evidence_refs"] == ["ri_state", "state_context"]
    assert record["persisted"] is False
    assert record["executed"] is False
    assert record["execution_result"] is None
    assert record["metadata"]["suite"] == "eval_harness"


def test_build_eval_memory_record_captures_failed_eval_state():
    loop = build_eval_loop_contract(
        loop_id="loop-memory-3",
        objective="Evaluate failed memory.",
        task_kind="code_action_review",
        nodes=[
            build_eval_critic_node(
                findings=[{"finding_id": "finding-memory-3", "severity": "critical", "summary": "False claim."}]
            ),
            build_eval_evaluator_node(
                metrics=[{"metric_id": "safety", "name": "Safety", "status": "failed", "score": 0.1}],
                blockers=["false execution claim"],
            ),
        ],
        stop_policy={"max_iterations": 3, "min_score": 0.8},
    )

    record = build_eval_memory_record(loop_contract=loop)

    assert record["task_kind"] == "code_action_review"
    assert record["status"] == "blocked"
    assert record["passed"] is False
    assert record["blocked"] is True
    assert record["needs_refinement"] is True
    assert record["findings"][0]["finding_id"] == "finding-memory-3"
    assert record["blockers"] == ["false execution claim"]
    assert record["persisted"] is False


def test_summarize_eval_memory_record_returns_compact_summary():
    record = build_eval_memory_record(
        loop_contract=build_eval_loop_contract(
            task_kind="response_intelligence",
            nodes=[
                build_eval_critic_node(findings=[{"finding_id": "f1"}]),
                build_eval_refiner_node(proposals=[{"proposal_id": "p1"}]),
                build_eval_evaluator_node(
                    metrics=[{"metric_id": "grounding", "name": "Grounding", "score": 0.7}],
                    evidence_refs=["state_context"],
                ),
            ],
        )
    )

    summary = summarize_eval_memory_record(record)

    assert "Eval Memory:" in summary
    assert "task_kind=response_intelligence" in summary
    assert "findings=1" in summary
    assert "proposals=1" in summary
    assert "evidence_refs=1" in summary
    assert "persisted=False" in summary
