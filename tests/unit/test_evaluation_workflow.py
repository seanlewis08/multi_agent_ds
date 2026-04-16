from __future__ import annotations

import json

import pytest

from multi_agent_ds.workflows import evaluation as evaluation_workflow

run_evaluation_workflow = evaluation_workflow.run_evaluation_workflow


def test_run_evaluation_workflow_returns_contract_for_reviewer_and_mlflow() -> None:
    settings = {
        "model": {
            "primary_metric": "gini",
        }
    }
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41, "mse_vs_ground_truth": 0.08},
            "validation_scores": {"gini": 0.39},
            "y_prob": [0.2, 0.3, 0.5],
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
        "logistic_regression": {
            "test_scores": {"gini": 0.37, "mse_vs_ground_truth": 0.06},
            "validation_scores": {"gini": 0.37},
            "y_prob": [0.05, 0.25, 0.35],
            "phase": "baseline",
            "elapsed_seconds": 0.6,
        },
    }
    data = {
        "true_prob_test": [0.1, 0.2, 0.3],
    }

    output = run_evaluation_workflow(results, data, settings)

    evaluation_result = output["evaluation_result"]
    reviewer_summary = output["reviewer_summary"]
    mlflow_payload = output["mlflow_payload"]

    assert evaluation_result["winner"] == "lightgbm"
    assert evaluation_result["runner_up"] == "logistic_regression"
    assert evaluation_result["primary_metric"] == "gini"
    assert [item["algorithm"] for item in evaluation_result["rankings"]] == [
        "lightgbm",
        "logistic_regression",
    ]
    assert evaluation_result["metric_rankings"]["gini"] == [
        {"algorithm": "lightgbm", "metric": "gini", "value": 0.41, "rank": 1},
        {
            "algorithm": "logistic_regression",
            "metric": "gini",
            "value": 0.37,
            "rank": 2,
        },
    ]
    assert evaluation_result["metric_rankings"]["mse_vs_ground_truth"] == [
        {
            "algorithm": "logistic_regression",
            "metric": "mse_vs_ground_truth",
            "value": 0.06,
            "rank": 1,
        },
        {"algorithm": "lightgbm", "metric": "mse_vs_ground_truth", "value": 0.08, "rank": 2},
    ]
    assert evaluation_result["algorithm_summaries"] == [
        {
            "algorithm": "lightgbm",
            "rank": 1,
            "phase": "baseline",
            "elapsed_seconds": 1.2,
            "primary_metric": "gini",
            "primary_metric_value": 0.41,
            "test_scores": {"gini": 0.41, "mse_vs_ground_truth": 0.08},
            "validation_scores": {"gini": 0.39},
            "ground_truth_metrics": {
                "mse_vs_ground_truth": pytest.approx(0.02),
                "mae_vs_ground_truth": pytest.approx(0.1333333333),
                "rmse_vs_ground_truth": pytest.approx(0.1414213562),
                "correlation_to_ground_truth": pytest.approx(0.9819805061),
                "rank": 2,
            },
        },
        {
            "algorithm": "logistic_regression",
            "rank": 2,
            "phase": "baseline",
            "elapsed_seconds": 0.6,
            "primary_metric": "gini",
            "primary_metric_value": 0.37,
            "test_scores": {"gini": 0.37, "mse_vs_ground_truth": 0.06},
            "validation_scores": {"gini": 0.37},
            "ground_truth_metrics": {
                "mse_vs_ground_truth": pytest.approx(0.0025),
                "mae_vs_ground_truth": pytest.approx(0.05),
                "rmse_vs_ground_truth": pytest.approx(0.05),
                "correlation_to_ground_truth": pytest.approx(0.9819805061),
                "rank": 1,
            },
        },
    ]
    assert evaluation_result["tie_break"] == {"used": False, "reason": None}
    assert evaluation_result["model_selection_summary"] == {
        "winner": {
            "algorithm": "lightgbm",
            "primary_metric": "gini",
            "primary_metric_value": 0.41,
            "test_scores": {"gini": 0.41, "mse_vs_ground_truth": 0.08},
            "validation_scores": {"gini": 0.39},
            "reasoning": (
                "lightgbm ranked first on gini at 0.4100, ahead of "
                "logistic_regression at 0.3700."
            ),
        },
        "runner_up": {
            "algorithm": "logistic_regression",
            "primary_metric": "gini",
            "primary_metric_value": 0.37,
            "test_scores": {"gini": 0.37, "mse_vs_ground_truth": 0.06},
            "validation_scores": {"gini": 0.37},
        },
        "trade_off_summary": {
            "runner_up": "logistic_regression",
            "primary_metric_gap": pytest.approx(0.04),
            "summary": "logistic_regression was the runner-up with gini 0.3700.",
        },
        "what_was_tested": {
            "algorithms": ["lightgbm", "logistic_regression"],
            "primary_metric": "gini",
            "used_ground_truth": True,
            "used_shap": False,
        },
        "key_results": [
            "lightgbm ranked first on gini (0.4100).",
            "logistic_regression ranked second on gini (0.3700).",
            "logistic_regression was closest to ground truth by mse_vs_ground_truth (0.002500).",
        ],
        "caveats": ["shap summary unavailable"],
    }

    assert reviewer_summary == {
        "winner": "lightgbm",
        "runner_up": "logistic_regression",
        "primary_metric": "gini",
        "winner_score": 0.41,
        "runner_up_score": 0.37,
        "reasoning": (
            "lightgbm ranked first on gini at 0.4100, ahead of "
            "logistic_regression at 0.3700."
        ),
        "trade_off_summary": {
            "runner_up": "logistic_regression",
            "primary_metric_gap": pytest.approx(0.04),
            "summary": "logistic_regression was the runner-up with gini 0.3700.",
        },
        "what_was_tested": {
            "algorithms": ["lightgbm", "logistic_regression"],
            "primary_metric": "gini",
            "used_ground_truth": True,
            "used_shap": False,
        },
        "key_results": [
            "lightgbm ranked first on gini (0.4100).",
            "logistic_regression ranked second on gini (0.3700).",
            "logistic_regression was closest to ground truth by mse_vs_ground_truth (0.002500).",
        ],
        "caveats": ["shap summary unavailable"],
    }

    ground_truth = evaluation_result["ground_truth_comparison"]
    assert ground_truth["available"] is True
    assert ground_truth["ranking_metric"] == "mse_vs_ground_truth"
    assert [item["algorithm"] for item in ground_truth["rankings"]] == [
        "logistic_regression",
        "lightgbm",
    ]
    assert ground_truth["rankings"][0]["rank"] == 1
    assert ground_truth["rankings"][1]["rank"] == 2
    assert ground_truth["algorithms"][0]["algorithm"] == "lightgbm"
    assert ground_truth["algorithms"][1]["algorithm"] == "logistic_regression"
    assert ground_truth["expectation_checks"] == {
        "top_tier_expected": [
            "credit_score",
            "num_prior_claims",
            "annual_income",
        ],
        "lowest_tier_expected": [
            "state",
            "coverage_tier",
            "marital_status",
            "vehicle_type",
            "education_level",
        ],
        "feature_ranking_validation": "deferred_until_shap",
        "notes": (
            "Ground_Truth_Feature_Importance.md is a validation guide. "
            "Feature-level validation is deferred until SHAP or another "
            "attribution method is available."
        ),
    }
    assert ground_truth["rankings"][0]["mse_vs_ground_truth"] == pytest.approx(0.0025)
    assert ground_truth["rankings"][0]["mae_vs_ground_truth"] == pytest.approx(0.05)
    assert ground_truth["rankings"][0]["rmse_vs_ground_truth"] == pytest.approx(0.05)
    assert ground_truth["rankings"][0]["correlation_to_ground_truth"] == pytest.approx(0.9819805061)
    assert ground_truth["rankings"][1]["mse_vs_ground_truth"] == pytest.approx(0.02)
    assert ground_truth["rankings"][1]["mae_vs_ground_truth"] == pytest.approx(0.1333333333)
    assert ground_truth["rankings"][1]["rmse_vs_ground_truth"] == pytest.approx(0.1414213562)
    assert ground_truth["rankings"][1]["correlation_to_ground_truth"] == pytest.approx(0.9819805061)

    assert output["shap_results"]["available"] is False
    assert output["shap_results"]["reason"] == "shap_unavailable: Winner 'lightgbm' has no fitted model for SHAP"
    assert output["shap_artifacts"] == {
        "content_types": {},
        "metadata": {
            "available": False,
            "reason": "shap_unavailable: Winner 'lightgbm' has no fitted model for SHAP",
        },
    }

    assert mlflow_payload == {
        "metrics": {
            "winner_primary_metric": 0.41,
            "winner_rank": 1,
            "ground_truth_available": True,
        },
        "params": {
            "primary_metric": "gini",
            "winner_algorithm": "lightgbm",
            "runner_up_algorithm": "logistic_regression",
        },
        "tags": {
            "evaluation_phase": "post_training",
            "evaluation_status": "success",
            "winner_algorithm": "lightgbm",
            "runner_up_algorithm": "logistic_regression",
            "primary_metric": "gini",
            "has_ground_truth": "true",
            "shap_available": "false",
        },
        "context": {
            "algorithms_evaluated": ["lightgbm", "logistic_regression"],
            "algorithm_count": 2,
            "algorithm_summaries": evaluation_result["algorithm_summaries"],
            "tie_break": {"used": False, "reason": None},
        },
        "artifacts": [],
    }


def test_run_evaluation_workflow_handles_missing_ground_truth_cleanly() -> None:
    settings = {
        "model": {
            "primary_metric": "gini",
        }
    }
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
    }

    output = run_evaluation_workflow(results, {}, settings)

    assert output["evaluation_result"]["ground_truth_comparison"] == {
        "available": False,
        "reason": "true_prob_test not provided",
        "rankings": [],
    }
    assert output["evaluation_result"]["algorithm_summaries"] == [
        {
            "algorithm": "lightgbm",
            "rank": 1,
            "phase": "baseline",
            "elapsed_seconds": 1.2,
            "primary_metric": "gini",
            "primary_metric_value": 0.41,
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "ground_truth_metrics": None,
        }
    ]
    assert output["evaluation_result"]["model_selection_summary"] == {
        "winner": {
            "algorithm": "lightgbm",
            "primary_metric": "gini",
            "primary_metric_value": 0.41,
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "reasoning": "lightgbm is the only evaluated algorithm and ranked first on gini at 0.4100.",
        },
        "runner_up": None,
        "trade_off_summary": {
            "runner_up": None,
            "primary_metric_gap": None,
            "summary": "No runner-up was available for trade-off comparison.",
        },
        "what_was_tested": {
            "algorithms": ["lightgbm"],
            "primary_metric": "gini",
            "used_ground_truth": False,
            "used_shap": False,
        },
        "key_results": ["lightgbm ranked first on gini (0.4100)."],
        "caveats": [
            "ground truth comparison unavailable",
            "shap summary unavailable",
        ],
    }
    assert output["reviewer_summary"]["caveats"] == [
        "ground truth comparison unavailable",
        "shap summary unavailable",
    ]


def test_run_evaluation_workflow_uses_validation_score_as_tie_breaker() -> None:
    settings = {
        "model": {
            "primary_metric": "gini",
        }
    }
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.40},
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
        "logistic_regression": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "phase": "baseline",
            "elapsed_seconds": 0.6,
        },
    }

    output = run_evaluation_workflow(results, {}, settings)

    assert output["evaluation_result"]["winner"] == "lightgbm"
    assert output["evaluation_result"]["runner_up"] == "logistic_regression"
    assert output["evaluation_result"]["tie_break"] == {
        "used": True,
        "reason": "validation_scores.gini",
    }
    assert output["reviewer_summary"]["caveats"] == [
        "ground truth comparison unavailable",
        "winner selected using tie-break: validation_scores.gini",
        "shap summary unavailable",
    ]


def test_run_evaluation_workflow_supports_ascending_primary_metric() -> None:
    settings = {
        "model": {
            "primary_metric": "ase",
        }
    }
    results = {
        "lightgbm": {
            "test_scores": {"ase": 1.2},
            "validation_scores": {"ase": 1.1},
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
        "logistic_regression": {
            "test_scores": {"ase": 0.9},
            "validation_scores": {"ase": 1.0},
            "phase": "baseline",
            "elapsed_seconds": 0.6,
        },
    }

    output = run_evaluation_workflow(results, {}, settings)

    assert output["evaluation_result"]["winner"] == "logistic_regression"
    assert output["evaluation_result"]["runner_up"] == "lightgbm"
    assert output["evaluation_result"]["model_selection_summary"]["winner"]["algorithm"] == "logistic_regression"
    assert output["evaluation_result"]["model_selection_summary"]["trade_off_summary"] == {
        "runner_up": "lightgbm",
        "primary_metric_gap": pytest.approx(-0.3),
        "summary": "lightgbm was the runner-up with ase 1.2000.",
    }
    assert [item["algorithm"] for item in output["evaluation_result"]["metric_rankings"]["ase"]] == [
        "logistic_regression",
        "lightgbm",
    ]


def test_run_evaluation_workflow_builds_shap_results_for_lightgbm(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeExplanation:
        def __init__(self, values):
            self.values = values

    class FakeTreeExplainer:
        def __init__(self, model):
            self.model = model

        def shap_values(self, X_test):
            return FakeExplanation([[0.1, -0.2], [0.3, -0.4]])

    class FakeLinearExplainer:
        def __init__(self, model, X_test):
            self.model = model
            self.X_test = X_test

        def shap_values(self, X_test):
            return [[[0.0, 0.0]], [[0.0, 0.0]]]

    class FakeExplainer:
        def __init__(self, model, X_test):
            self.model = model
            self.X_test = X_test

        def __call__(self, X_test):
            return FakeExplanation([[0.0, 0.0]])

    class FakeShapModule:
        TreeExplainer = FakeTreeExplainer
        LinearExplainer = FakeLinearExplainer
        Explainer = FakeExplainer

    monkeypatch.setattr(evaluation_workflow, "_load_shap_module", lambda: FakeShapModule)

    settings = {"model": {"primary_metric": "gini"}}
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "model": object(),
            "feature_names": ["credit_score", "annual_income"],
            "encoding": "native",
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        }
    }
    data = {
        "X_test": [[1.0, 2.0], [3.0, 4.0]],
    }

    output = run_evaluation_workflow(results, data, settings)

    assert output["evaluation_result"]["shap_available"] is True
    assert output["shap_results"] == {
        "available": True,
        "target_algorithm": "lightgbm",
        "explainer_type": "FakeTreeExplainer",
        "n_rows": 2,
        "n_features": 2,
        "feature_ranking": [
            {
                "feature": "annual_income",
                "mean_abs_shap": pytest.approx(0.3),
                "mean_signed_shap": pytest.approx(-0.3),
                "direction": "negative",
            },
            {
                "feature": "credit_score",
                "mean_abs_shap": pytest.approx(0.2),
                "mean_signed_shap": pytest.approx(0.2),
                "direction": "positive",
            },
        ],
        "top_features": [
            {
                "feature": "annual_income",
                "mean_abs_shap": pytest.approx(0.3),
                "mean_signed_shap": pytest.approx(-0.3),
                "direction": "negative",
            },
            {
                "feature": "credit_score",
                "mean_abs_shap": pytest.approx(0.2),
                "mean_signed_shap": pytest.approx(0.2),
                "direction": "positive",
            },
        ],
        "directional_summary": [
            {
                "feature": "annual_income",
                "mean_abs_shap": pytest.approx(0.3),
                "mean_signed_shap": pytest.approx(-0.3),
                "direction": "negative",
            },
            {
                "feature": "credit_score",
                "mean_abs_shap": pytest.approx(0.2),
                "mean_signed_shap": pytest.approx(0.2),
                "direction": "positive",
            },
        ],
        "encoding": "native",
    }
    assert output["mlflow_payload"]["tags"]["shap_available"] == "true"
    assert output["shap_artifacts"]["content_types"] == {
        "shap_beeswarm.png": "image/png",
        "shap_waterfall.png": "image/png",
        "shap_summary.json": "application/json",
    }
    assert output["shap_artifacts"]["metadata"] == {
        "available": True,
        "artifact_category": "shap",
        "filenames": [
            "shap_beeswarm.png",
            "shap_waterfall.png",
            "shap_summary.json",
        ],
        "representative_row_strategy": "largest_total_abs_shap",
    }
    assert isinstance(output["shap_artifacts"]["shap_beeswarm.png"], bytes)
    assert isinstance(output["shap_artifacts"]["shap_waterfall.png"], bytes)
    assert output["shap_artifacts"]["shap_summary.json"]["artifact_type"] == "shap_summary"
    assert output["shap_artifacts"]["shap_summary.json"]["target_algorithm"] == "lightgbm"
    assert output["shap_artifacts"]["shap_summary.json"]["reviewer_safe_summary"]["summary"] == (
        "Top SHAP features for lightgbm: annual_income, credit_score"
    )
    assert output["shap_artifacts"]["shap_summary.json"]["waterfall"] == {
        "representative_row": 1,
        "selection_strategy": "largest_total_abs_shap",
        "top_row_contributions": [
            {"feature": "annual_income", "value": -0.4},
            {"feature": "credit_score", "value": 0.3},
        ],
    }
    assert [artifact["name"] for artifact in output["mlflow_payload"]["artifacts"]] == [
        "shap_beeswarm.png",
        "shap_waterfall.png",
        "shap_summary.json",
    ]
    assert output["mlflow_payload"]["artifacts"][0]["type"] == "image/png"
    assert output["mlflow_payload"]["artifacts"][0]["content_mode"] == "inline"
    assert isinstance(output["mlflow_payload"]["artifacts"][0]["content"], bytes)
    assert output["mlflow_payload"]["artifacts"][2]["type"] == "application/json"
    assert output["mlflow_payload"]["tags"]["evaluation_status"] == "success"
    assert output["mlflow_payload"]["tags"]["has_ground_truth"] == "false"
    assert output["mlflow_payload"]["context"]["algorithms_evaluated"] == ["lightgbm"]
    assert output["mlflow_payload"]["context"]["algorithm_count"] == 1
    assert output["mlflow_payload"]["context"]["algorithm_summaries"] == output["evaluation_result"]["algorithm_summaries"]
    assert output["mlflow_payload"]["artifacts"][2]["content"]["artifact_type"] == "shap_summary"


def test_run_evaluation_workflow_normalizes_binary_class_shap_list(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTreeExplainer:
        def __init__(self, model):
            self.model = model

        def shap_values(self, X_test):
            return [[0.0, 0.0]]

    class FakeLinearExplainer:
        def __init__(self, model, X_test):
            self.model = model
            self.X_test = X_test

        def shap_values(self, X_test):
            return [
                [[0.01, -0.02], [0.03, -0.01]],
                [[0.2, -0.1], [0.4, -0.3]],
            ]

    class FakeExplainer:
        def __init__(self, model, X_test):
            self.model = model
            self.X_test = X_test

        def __call__(self, X_test):
            return [[0.0, 0.0]]

    class FakeShapModule:
        TreeExplainer = FakeTreeExplainer
        LinearExplainer = FakeLinearExplainer
        Explainer = FakeExplainer

    monkeypatch.setattr(evaluation_workflow, "_load_shap_module", lambda: FakeShapModule)

    settings = {"model": {"primary_metric": "gini"}}
    results = {
        "logistic_regression": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "model": object(),
            "feature_names": ["credit_score", "annual_income"],
            "encoding": "onehot",
            "phase": "baseline",
            "elapsed_seconds": 0.6,
        }
    }
    data = {
        "X_test": [[1.0, 2.0], [3.0, 4.0]],
    }

    output = run_evaluation_workflow(results, data, settings)

    assert output["shap_results"]["available"] is True
    assert output["shap_results"]["target_algorithm"] == "logistic_regression"
    assert output["shap_results"]["explainer_type"] == "FakeLinearExplainer"
    assert output["shap_results"]["feature_ranking"] == [
        {
            "feature": "credit_score",
            "mean_abs_shap": pytest.approx(0.3),
            "mean_signed_shap": pytest.approx(0.3),
            "direction": "positive",
        },
        {
            "feature": "annual_income",
            "mean_abs_shap": pytest.approx(0.2),
            "mean_signed_shap": pytest.approx(-0.2),
            "direction": "negative",
        },
    ]
    assert output["shap_artifacts"]["metadata"]["representative_row_strategy"] == "largest_total_abs_shap"


def test_run_evaluation_workflow_keeps_state_payload_serializable_and_byte_free() -> None:
    settings = {
        "model": {
            "primary_metric": "gini",
        }
    }
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
    }

    output = run_evaluation_workflow(results, {}, settings)

    state_payload = {
        "evaluation_result": output["evaluation_result"],
        "reviewer_summary": output["reviewer_summary"],
        "shap_results": output["shap_results"],
    }

    assert json.loads(json.dumps(state_payload)) == state_payload
    assert "content_types" not in state_payload["evaluation_result"]
    assert "shap_beeswarm.png" not in state_payload["evaluation_result"]
    assert "shap_waterfall.png" not in state_payload["evaluation_result"]
    assert "shap_summary.json" not in state_payload["evaluation_result"]


def test_run_evaluation_workflow_reviewer_summary_is_compact_and_serializable() -> None:
    settings = {
        "model": {
            "primary_metric": "gini",
        }
    }
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
        "logistic_regression": {
            "test_scores": {"gini": 0.37},
            "validation_scores": {"gini": 0.37},
            "phase": "baseline",
            "elapsed_seconds": 0.6,
        },
    }

    reviewer_summary = run_evaluation_workflow(results, {}, settings)["reviewer_summary"]

    assert sorted(reviewer_summary.keys()) == [
        "caveats",
        "key_results",
        "primary_metric",
        "reasoning",
        "runner_up",
        "runner_up_score",
        "trade_off_summary",
        "what_was_tested",
        "winner",
        "winner_score",
    ]
    assert json.loads(json.dumps(reviewer_summary)) == reviewer_summary
    assert "test_scores" not in reviewer_summary
    assert "validation_scores" not in reviewer_summary


def test_run_evaluation_workflow_mlflow_payload_has_stable_sections() -> None:
    settings = {
        "model": {
            "primary_metric": "gini",
        }
    }
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
    }

    output = run_evaluation_workflow(results, {}, settings)

    mlflow_payload = output["mlflow_payload"]

    assert sorted(mlflow_payload.keys()) == ["artifacts", "context", "metrics", "params", "tags"]
    assert sorted(mlflow_payload["metrics"].keys()) == [
        "ground_truth_available",
        "winner_primary_metric",
        "winner_rank",
    ]
    assert sorted(mlflow_payload["params"].keys()) == [
        "primary_metric",
        "runner_up_algorithm",
        "winner_algorithm",
    ]
    assert sorted(mlflow_payload["tags"].keys()) == [
        "evaluation_phase",
        "evaluation_status",
        "has_ground_truth",
        "primary_metric",
        "runner_up_algorithm",
        "shap_available",
        "winner_algorithm",
    ]
    assert sorted(mlflow_payload["context"].keys()) == [
        "algorithm_count",
        "algorithm_summaries",
        "algorithms_evaluated",
        "tie_break",
    ]


def test_run_evaluation_workflow_raises_for_empty_results() -> None:
    settings = {"model": {"primary_metric": "gini"}}

    with pytest.raises(ValueError, match="results must contain at least one algorithm output"):
        run_evaluation_workflow({}, {}, settings)


def test_run_evaluation_workflow_raises_when_primary_metric_is_missing() -> None:
    settings = {"model": {"primary_metric": "gini"}}
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
        "logistic_regression": {
            "test_scores": {"ase": 0.9},
            "validation_scores": {"ase": 1.0},
            "phase": "baseline",
            "elapsed_seconds": 0.6,
        },
    }

    with pytest.raises(
        ValueError,
        match="Primary metric 'gini' missing from test_scores for: logistic_regression",
    ):
        run_evaluation_workflow(results, {}, settings)


def test_run_evaluation_workflow_raises_for_ground_truth_length_mismatch() -> None:
    settings = {"model": {"primary_metric": "gini"}}
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "y_prob": [0.2, 0.3],
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
    }
    data = {"true_prob_test": [0.1, 0.2, 0.3]}

    with pytest.raises(
        ValueError,
        match="Ground truth comparison length mismatch for lightgbm",
    ):
        run_evaluation_workflow(results, data, settings)


def test_run_evaluation_workflow_uses_algorithm_name_when_all_tie_breakers_match() -> None:
    settings = {"model": {"primary_metric": "gini"}}
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.40},
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        },
        "xgboost": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.40},
            "phase": "baseline",
            "elapsed_seconds": 1.0,
        },
    }

    output = run_evaluation_workflow(results, {}, settings)

    assert output["evaluation_result"]["winner"] == "lightgbm"
    assert output["evaluation_result"]["runner_up"] == "xgboost"
    assert output["evaluation_result"]["tie_break"] == {
        "used": True,
        "reason": "algorithm_name",
    }
    assert output["reviewer_summary"]["caveats"] == [
        "ground truth comparison unavailable",
        "winner selected using tie-break: algorithm_name",
        "shap summary unavailable",
    ]


def test_run_evaluation_workflow_handles_shap_feature_alignment_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeExplanation:
        def __init__(self, values):
            self.values = values

    class FakeTreeExplainer:
        def __init__(self, model):
            self.model = model

        def shap_values(self, X_test):
            return FakeExplanation([[0.1, -0.2, 0.3], [0.3, -0.4, 0.5]])

    class FakeLinearExplainer:
        def __init__(self, model, X_test):
            self.model = model
            self.X_test = X_test

        def shap_values(self, X_test):
            return [[[0.0, 0.0]], [[0.0, 0.0]]]

    class FakeExplainer:
        def __init__(self, model, X_test):
            self.model = model
            self.X_test = X_test

        def __call__(self, X_test):
            return FakeExplanation([[0.0, 0.0]])

    class FakeShapModule:
        TreeExplainer = FakeTreeExplainer
        LinearExplainer = FakeLinearExplainer
        Explainer = FakeExplainer

    monkeypatch.setattr(evaluation_workflow, "_load_shap_module", lambda: FakeShapModule)

    settings = {"model": {"primary_metric": "gini"}}
    results = {
        "lightgbm": {
            "test_scores": {"gini": 0.41},
            "validation_scores": {"gini": 0.39},
            "model": object(),
            "feature_names": ["credit_score", "annual_income"],
            "encoding": "native",
            "phase": "baseline",
            "elapsed_seconds": 1.2,
        }
    }
    data = {"X_test": [[1.0, 2.0], [3.0, 4.0]]}

    output = run_evaluation_workflow(results, data, settings)

    assert output["shap_results"] == {
        "available": False,
        "reason": (
            "shap_unavailable: SHAP feature alignment mismatch: values have 3 "
            "columns but feature_names has 2 entries"
        ),
    }
    assert output["shap_artifacts"] == {
        "content_types": {},
        "metadata": {
            "available": False,
            "reason": (
                "shap_unavailable: SHAP feature alignment mismatch: values have 3 "
                "columns but feature_names has 2 entries"
            ),
        },
    }
