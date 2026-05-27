from backend.apps.swarms.eval_harness import (
    build_default_eval_loop_contract,
    build_default_eval_planner_node,
    build_eval_loop_contract,
    build_eval_planner_node,
    normalize_eval_metric,
    normalize_eval_node,
    normalize_eval_planner_criterion,
    normalize_eval_stop_policy,
    summarize_eval_loop,
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
    assert policy["stop_on_blocked"] is True
    assert policy["allow_refinement"] is True


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
