from backend.apps.swarms.eval_harness import (
    build_default_eval_loop_contract,
    build_eval_loop_contract,
    normalize_eval_metric,
    normalize_eval_node,
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
