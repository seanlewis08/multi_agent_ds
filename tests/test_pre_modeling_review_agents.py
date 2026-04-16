from __future__ import annotations

from typing import Any

import pytest

from multi_agent_ds.agents.business_stakeholder import business_stakeholder_node
from multi_agent_ds.agents.data_engineer import data_engineer_node
from multi_agent_ds.agents.ml_modeler import ml_modeler_node
from multi_agent_ds.agents.ml_reviewer import ml_reviewer_node


class FakeReviewAdapter:
    def __init__(self, settings: dict[str, Any]):
        self.settings = settings

    def structured_output(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        if "ready_for_execution" in schema["properties"]:
            return {
                "parsed": {
                    "summary": "The plan is feasible.",
                    "ready_for_execution": True,
                    "action_feedback": [
                        {
                            "action": "clip_outliers_iqr",
                            "feasible": True,
                            "reason": "The feature is numeric.",
                        }
                    ],
                    "execution_notes": ["Run the approved plan once."],
                }
            }

        if "algorithms_to_tune" in schema["properties"]:
            return {
                "parsed": {
                    "summary": "LightGBM leads; both algorithms are worth tuning.",
                    "algorithms_to_tune": ["lightgbm", "logistic_regression"],
                    "algorithms_to_drop": [],
                    "reasoning": "Baseline scores are within tuning range for both models.",
                }
            }

        if "accept_tuned_params" in schema["properties"]:
            return {
                "parsed": {
                    "algorithm": "lightgbm",
                    "accept_tuned_params": True,
                    "chosen_params": {"max_depth": 7, "num_leaves": 63},
                    "reasoning": "CV gini improved by 0.03 with flat convergence slope.",
                }
            }

        if "keep_adjustment" in schema["properties"]:
            return {
                "parsed": {
                    "algorithm": "lightgbm",
                    "keep_adjustment": True,
                    "chosen_learning_rate": 0.005,
                    "chosen_n_estimators": 1000,
                    "reasoning": "Lower lr improved test gini beyond prior CV std.",
                }
            }

        if "accept_subset" in schema["properties"]:
            return {
                "parsed": {
                    "algorithm": "lightgbm",
                    "accept_subset": True,
                    "kept_features": ["age", "income"],
                    "dropped_features": ["postal_code"],
                    "reasoning": "Subset score held within one CV std of prior.",
                }
            }

        if "best_algorithm" in schema["properties"]:
            return {
                "parsed": {
                    "summary": "LightGBM leads across every metric.",
                    "best_algorithm": "lightgbm",
                    "ranked_algorithms": ["lightgbm", "logistic_regression"],
                    "final_metrics": {
                        "lightgbm": {"gini": 0.66},
                        "logistic_regression": {"gini": 0.52},
                    },
                    "justification": "LightGBM primary-metric lead is larger than either model's CV std.",
                    "next_action": "proceed_to_evaluation",
                }
            }

        system_prompt = messages[0]["content"].lower()
        if "modeler agent" in system_prompt:
            reviewer_role = "ml_modeler"
        elif "business stakeholder" in system_prompt:
            reviewer_role = "business_stakeholder"
        else:
            reviewer_role = "ml_reviewer"

        return {
            "parsed": {
                "reviewer_role": reviewer_role,
                "summary": "The EDA review is acceptable.",
                "concerns": [],
                "recommendations": ["Proceed carefully."],
                "modeling_implications": ["Use robust validation."],
                "business_implications": [],
                "scientific_vs_art": [],
            }
        }


def _settings() -> dict[str, Any]:
    return {"llm": {"providers": {"openai": {"model": "gpt-4o", "temperature": 0.2, "max_tokens": 1000}}}}


def _prompts() -> dict[str, Any]:
    return {
        "data_engineer": {
            "system": "system prompt",
            "plan_feedback": "plan={prep_plan_json}; raw={raw_eda_json}",
        },
        "sean_ml_modeler": {
            "system": "You are an ML modeler agent.",
            "eda_review": "stage={review_stage}; eda={eda_json}",
            "baseline_review": "results={results_json}",
            "tuning_review": "algo={algorithm}; tuning={tuning_json}",
            "lr_adjustment_review": "algo={algorithm}; adjustment={adjustment_json}",
            "feature_selection_review": "algo={algorithm}; selection={selection_json}",
            "final_recommendation": "metric={primary_metric}; candidates={candidates_json}",
        },
        "ml_reviewer": {
            "system": "You are an ML reviewer.",
            "eda_review": "stage={review_stage}; eda={eda_json}",
        },
        "business_stakeholder": {
            "system": "You are a business stakeholder.",
            "eda_review": "stage={review_stage}; eda={eda_json}",
        },
    }


def test_data_engineer_feedback_returns_structured_output(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.data_engineer.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.data_engineer.load_prompts_config", _prompts)

    result = data_engineer_node(
        {
            "settings": _settings(),
            "prep_plan": {"cleaning_actions": [{"action": "clip_outliers_iqr"}]},
            "raw_eda_insights": {"needs_cleaning": True},
            "agent_decisions": [],
        },
        mode="feedback",
    )

    assert result["prep_feedback"]["ready_for_execution"] is True
    assert result["agent_decisions"][0]["summary"] == "The plan is feasible."
    assert result["agent_decisions"][0]["action_feedback_count"] == 1
    assert result["current_phase"] == "prep_feedback"


def test_data_engineer_execute_returns_preparation_result(monkeypatch) -> None:
    def fake_run_preparation_workflow(data_path: str, prep_plan: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
        assert data_path == "data/raw/example.parquet"
        assert prep_plan["cleaning_actions"][0]["action"] == "clip_outliers_iqr"
        return {
            "source_data_path": data_path,
            "target_column": "binary_target",
            "artifact_filename": "example_processed_20260416T010203Z.parquet",
            "processed_data_path": "s3://bucket/prefix/data/processed/example_processed_20260416T010203Z.parquet",
            "source_n_rows": 10,
            "source_n_features": 3,
            "n_rows": 10,
            "n_features": 4,
            "processed_n_rows": 10,
            "processed_n_features": 4,
            "cleaning_summary": [{"action": "clip_outliers_iqr"}],
            "feature_summary": [{"action": "ratio"}],
        }

    monkeypatch.setattr("multi_agent_ds.agents.data_engineer.run_preparation_workflow", fake_run_preparation_workflow)

    result = data_engineer_node(
        {
            "settings": _settings(),
            "data_path": "data/raw/example.parquet",
            "prep_plan": {"cleaning_actions": [{"action": "clip_outliers_iqr"}], "feature_actions": []},
            "agent_decisions": [],
        },
        mode="execute",
    )

    assert result["processed_data_path"].endswith(".parquet")
    assert result["prep_result"]["target_column"] == "binary_target"
    assert result["prep_result"]["processed_n_features"] == 4
    assert result["agent_decisions"][0]["artifact_filename"] == "example_processed_20260416T010203Z.parquet"
    assert result["agent_decisions"][0]["processed_n_rows"] == 10
    assert result["current_phase"] == "prep_execute"


def test_ml_modeler_raw_review_returns_review_payload(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)

    result = ml_modeler_node(
        {"settings": _settings(), "raw_eda_insights": {"needs_cleaning": True}, "agent_decisions": []},
        mode="raw_review",
    )

    assert result["raw_eda_ml_modeler_review"]["recommendations"] == ["Proceed carefully."]


def test_ml_modeler_baseline_runs_skill_and_records_decision(monkeypatch) -> None:
    captured = {}

    def fake_train_with_defaults(data: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
        captured["data"] = data
        captured["settings"] = settings
        return {
            "lightgbm": {
                "cv_scores": {"gini": 0.61},
                "test_scores": {"gini": 0.60},
                "params_used": {"n_estimators": 200},
                "elapsed_seconds": 1.2,
                "phase": "baseline",
                "model": object(),
                "y_pred": "numpy-array",
                "y_prob": "numpy-array",
            },
            "logistic_regression": {
                "cv_scores": {"gini": 0.52},
                "test_scores": {"gini": 0.51},
                "params_used": {"C": 1.0},
                "elapsed_seconds": 0.4,
                "phase": "baseline",
                "model": object(),
                "y_pred": "numpy-array",
                "y_prob": "numpy-array",
            },
        }

    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.train_with_defaults", fake_train_with_defaults)

    result = ml_modeler_node(
        {
            "settings": _settings(),
            "data": {"X_train": "fake"},
            "modeling_results": {"prior": "kept"},
            "agent_decisions": [],
        },
        mode="baseline",
    )

    assert captured["data"] == {"X_train": "fake"}
    assert result["current_phase"] == "baseline"
    assert result["modeling_results"]["prior"] == "kept"
    assert "lightgbm" in result["modeling_results"]["baseline"]
    assert result["modeling_results"]["baseline_decision"]["algorithms_to_tune"] == [
        "lightgbm",
        "logistic_regression",
    ]
    decision_log = result["agent_decisions"][0]
    assert decision_log["phase"] == "baseline"
    assert decision_log["algorithms_to_tune"] == ["lightgbm", "logistic_regression"]


def test_ml_modeler_tune_iterates_algorithms_and_records_decisions(monkeypatch) -> None:
    tune_calls = []

    def fake_tune_algorithm(**kwargs: Any) -> dict[str, Any]:
        tune_calls.append(kwargs)
        return {
            "algorithm": kwargs["algo_name"],
            "best_params": {"max_depth": 7, "num_leaves": 63},
            "best_score": 0.64,
            "baseline_score": kwargs["baseline_score"],
            "score_improvement": 0.03,
            "convergence_reached": True,
            "total_trials": 50,
            "param_importances": {"max_depth": 0.6},
            "trial_history": [{"number": i, "score": 0.5 + i * 0.001} for i in range(50)],
        }

    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.tune_algorithm", fake_tune_algorithm)

    result = ml_modeler_node(
        {
            "settings": {
                **_settings(),
                "model": {"cv_folds": 3, "primary_metric": "gini"},
            },
            "data": {
                "X_train": "X",
                "y_train": "y",
                "categorical_features": ["region"],
            },
            "modeling_results": {
                "baseline": {
                    "lightgbm": {"cv_scores": {"gini": 0.61}},
                    "logistic_regression": {"cv_scores": {"gini": 0.52}},
                },
                "baseline_decision": {
                    "algorithms_to_tune": ["lightgbm", "logistic_regression"],
                },
            },
            "agent_decisions": [],
        },
        mode="tune",
    )

    assert [call["algo_name"] for call in tune_calls] == ["lightgbm", "logistic_regression"]
    assert tune_calls[0]["learning_rate"] == 0.01
    assert tune_calls[0]["n_estimators"] == 500
    assert tune_calls[1]["learning_rate"] is None
    assert tune_calls[1]["n_estimators"] is None
    assert tune_calls[0]["baseline_score"] == 0.61
    assert tune_calls[1]["baseline_score"] == 0.52

    tuning = result["modeling_results"]["tuning"]
    decisions = result["modeling_results"]["tuning_decisions"]
    assert set(tuning.keys()) == {"lightgbm", "logistic_regression"}
    assert decisions["lightgbm"]["accept_tuned_params"] is True
    assert result["current_phase"] == "tune"
    assert len(result["agent_decisions"]) == 2
    assert result["agent_decisions"][0]["phase"] == "tune"
    assert result["agent_decisions"][0]["algorithm"] == "lightgbm"


def test_ml_modeler_train_tuned_only_refits_accepted_algorithms(monkeypatch) -> None:
    retrain_calls = []

    def fake_train_with_params(**kwargs: Any) -> dict[str, Any]:
        retrain_calls.append(kwargs)
        return {
            "algorithm": kwargs["algo_name"],
            "cv_scores": {"gini": 0.66},
            "test_scores": {"gini": 0.65},
            "params_used": kwargs["params"],
            "elapsed_seconds": 1.0,
        }

    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.train_with_params", fake_train_with_params)

    result = ml_modeler_node(
        {
            "settings": {**_settings(), "model": {"primary_metric": "gini"}},
            "data": {"X_train": "X", "y_train": "y", "categorical_features": []},
            "modeling_results": {
                "baseline": {
                    "lightgbm": {"test_scores": {"gini": 0.60}},
                    "logistic_regression": {"test_scores": {"gini": 0.51}},
                },
                "tuning_decisions": {
                    "lightgbm": {
                        "algorithm": "lightgbm",
                        "accept_tuned_params": True,
                        "chosen_params": {"max_depth": 7},
                        "reasoning": "Improved CV score.",
                    },
                    "logistic_regression": {
                        "algorithm": "logistic_regression",
                        "accept_tuned_params": False,
                        "chosen_params": {"C": 1.0},
                        "reasoning": "Improvement inside noise band.",
                    },
                },
            },
            "agent_decisions": [],
        },
        mode="train_tuned",
    )

    assert [call["algo_name"] for call in retrain_calls] == ["lightgbm"]
    assert retrain_calls[0]["params"] == {"max_depth": 7}
    train_tuned = result["modeling_results"]["train_tuned"]
    assert set(train_tuned.keys()) == {"lightgbm"}
    assert train_tuned["lightgbm"]["test_score_delta_vs_baseline"] == pytest.approx(0.05)
    assert result["current_phase"] == "train_tuned"
    assert result["agent_decisions"][0]["algorithm"] == "lightgbm"
    assert result["agent_decisions"][0]["test_score_delta_vs_baseline"] == pytest.approx(0.05)


def test_ml_modeler_n_estimator_search_runs_boosting_only(monkeypatch) -> None:
    calls = []

    def fake_find_optimal_estimators(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "algorithm": kwargs["algo_name"],
            "learning_rate": kwargs["learning_rate"],
            "optimal_n_estimators": 450,
            "best_score": 0.63,
            "best_std": 0.01,
            "scores_by_n": [],
            "search_stopped_early": False,
        }

    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.find_optimal_estimators", fake_find_optimal_estimators
    )

    result = ml_modeler_node(
        {
            "settings": {**_settings(), "model": {"cv_folds": 3, "primary_metric": "gini"}},
            "data": {"X_train": "X", "y_train": "y", "categorical_features": []},
            "modeling_results": {
                "baseline_decision": {
                    "algorithms_to_tune": ["lightgbm", "logistic_regression"],
                },
            },
            "agent_decisions": [],
        },
        mode="n_estimator_search",
    )

    assert [call["algo_name"] for call in calls] == ["lightgbm"]
    assert calls[0]["learning_rate"] == 0.01
    assert result["n_estimator_search_skipped"] == ["logistic_regression"]
    assert result["modeling_results"]["n_estimator_search"]["lightgbm"]["optimal_n_estimators"] == 450
    assert result["current_phase"] == "n_estimator_search"


def test_ml_modeler_adjust_lr_skips_non_boosting_and_runs_boosting(monkeypatch) -> None:
    adjust_calls = []

    def fake_adjust_learning_rate(**kwargs: Any) -> dict[str, Any]:
        adjust_calls.append(kwargs)
        return {
            "algorithm": kwargs["algo_name"],
            "test_scores": {"gini": 0.68},
            "cv_scores": {"gini": 0.67},
            "params_used": kwargs["current_params"] | {"learning_rate": kwargs["new_learning_rate"]},
            "learning_rate_adjustment": {
                "old_learning_rate": kwargs["current_params"]["learning_rate"],
                "new_learning_rate": kwargs["new_learning_rate"],
                "new_score": 0.68,
                "old_score": kwargs["current_score"],
                "improved": True,
            },
        }

    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.adjust_learning_rate", fake_adjust_learning_rate
    )

    result = ml_modeler_node(
        {
            "settings": {**_settings(), "model": {"primary_metric": "gini"}},
            "data": {"X_train": "X", "y_train": "y", "categorical_features": []},
            "modeling_results": {
                "tuning": {
                    "lightgbm": {"learning_rate_used": 0.01, "n_estimators_used": 500},
                },
                "tuning_decisions": {
                    "lightgbm": {
                        "algorithm": "lightgbm",
                        "accept_tuned_params": True,
                        "chosen_params": {"max_depth": 7},
                        "reasoning": "x",
                    },
                    "logistic_regression": {
                        "algorithm": "logistic_regression",
                        "accept_tuned_params": True,
                        "chosen_params": {"C": 0.5},
                        "reasoning": "x",
                    },
                },
                "train_tuned": {
                    "lightgbm": {"test_scores": {"gini": 0.65}},
                    "logistic_regression": {"test_scores": {"gini": 0.55}},
                },
            },
            "agent_decisions": [],
        },
        mode="adjust_lr",
    )

    assert [call["algo_name"] for call in adjust_calls] == ["lightgbm"]
    assert adjust_calls[0]["current_params"]["learning_rate"] == 0.01
    assert adjust_calls[0]["new_learning_rate"] == pytest.approx(0.005)
    assert adjust_calls[0]["current_score"] == 0.65
    assert result["adjust_lr_skipped"] == ["logistic_regression"]
    assert result["modeling_results"]["adjust_lr_decisions"]["lightgbm"]["keep_adjustment"] is True
    assert result["current_phase"] == "adjust_lr"


def test_ml_modeler_importance_review_collects_native_and_permutation(monkeypatch) -> None:
    def fake_native(**kwargs: Any) -> dict[str, Any]:
        return {"ranked_features": [{"feature": "age", "importance": 0.5}]}

    def fake_perm(**kwargs: Any) -> dict[str, Any]:
        return {
            "ranked_features": [{"feature": "age", "mean_drop": 0.05}],
            "safe_to_remove": ["postal_code"],
        }

    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.get_feature_importances", fake_native)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.get_permutation_importances", fake_perm)

    result = ml_modeler_node(
        {
            "settings": {**_settings(), "model": {"primary_metric": "gini"}},
            "data": {
                "X_test": "Xtest",
                "y_test": "ytest",
                "feature_names": ["age", "postal_code"],
                "categorical_features": [],
            },
            "modeling_results": {
                "baseline_decision": {"algorithms_to_tune": ["lightgbm"]},
                "train_tuned": {
                    "lightgbm": {
                        "model": object(),
                        "feature_names": ["age", "postal_code"],
                        "test_scores": {"gini": 0.65},
                    }
                },
                "baseline": {"lightgbm": {"model": object()}},
            },
            "agent_decisions": [],
        },
        mode="importance_review",
    )

    importances = result["modeling_results"]["importances"]
    assert importances["lightgbm"]["source_phase"] == "train_tuned"
    assert importances["lightgbm"]["permutation"]["safe_to_remove"] == ["postal_code"]
    assert result["agent_decisions"][0]["source_phase"] == "train_tuned"


def test_ml_modeler_feature_selection_uses_safe_to_remove_flags(monkeypatch) -> None:
    subset_calls = []

    def fake_train_with_feature_subset(**kwargs: Any) -> dict[str, Any]:
        subset_calls.append(kwargs)
        return {
            "algorithm": kwargs["algo_name"],
            "cv_scores": {"gini": 0.66},
            "cv_std": {"gini": 0.01},
            "test_scores": {"gini": 0.66},
            "params_used": kwargs["params"],
        }

    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.train_with_feature_subset", fake_train_with_feature_subset
    )

    result = ml_modeler_node(
        {
            "settings": {**_settings(), "model": {"primary_metric": "gini"}},
            "data": {
                "feature_names": ["age", "income", "postal_code"],
                "categorical_features": [],
            },
            "modeling_results": {
                "importances": {
                    "lightgbm": {
                        "source_phase": "train_tuned",
                        "native": {},
                        "permutation": {"safe_to_remove": ["postal_code"]},
                    },
                },
                "tuning": {
                    "lightgbm": {"learning_rate_used": 0.01, "n_estimators_used": 500},
                },
                "tuning_decisions": {
                    "lightgbm": {
                        "algorithm": "lightgbm",
                        "accept_tuned_params": True,
                        "chosen_params": {"max_depth": 7},
                        "reasoning": "x",
                    },
                },
                "baseline": {"lightgbm": {"params_used": {"n_estimators": 500}}},
                "train_tuned": {
                    "lightgbm": {
                        "test_scores": {"gini": 0.65},
                    }
                },
            },
            "agent_decisions": [],
        },
        mode="feature_selection",
    )

    assert subset_calls[0]["keep_features"] == ["age", "income"]
    assert subset_calls[0]["params"]["max_depth"] == 7
    assert subset_calls[0]["params"]["learning_rate"] == 0.01
    subset = result["modeling_results"]["feature_selection"]["lightgbm"]
    assert subset["test_score_delta_vs_prior"] == pytest.approx(0.01)
    decision = result["modeling_results"]["feature_selection_decisions"]["lightgbm"]
    assert decision["accept_subset"] is True
    assert result["current_phase"] == "feature_selection"


def test_ml_modeler_final_recommendation_picks_best_with_latest_phase(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)

    result = ml_modeler_node(
        {
            "settings": {**_settings(), "model": {"primary_metric": "gini"}},
            "modeling_results": {
                "baseline_decision": {
                    "algorithms_to_tune": ["lightgbm", "logistic_regression"],
                },
                "baseline": {
                    "lightgbm": {"test_scores": {"gini": 0.60}, "params_used": {}},
                    "logistic_regression": {"test_scores": {"gini": 0.51}, "params_used": {}},
                },
                "train_tuned": {
                    "lightgbm": {"test_scores": {"gini": 0.65}, "params_used": {"max_depth": 7}},
                },
                "feature_selection": {
                    "lightgbm": {"test_scores": {"gini": 0.66}, "params_used": {"max_depth": 7}},
                },
            },
            "agent_decisions": [],
        },
        mode="final_recommendation",
    )

    candidates = result["modeling_results"]["final_candidates"]
    assert candidates["lightgbm"]["final_phase"] == "feature_selection"
    assert candidates["logistic_regression"]["final_phase"] == "baseline"
    verdict = result["modeling_verdict"]
    assert verdict["best_algorithm"] == "lightgbm"
    assert verdict["next_action"] == "proceed_to_evaluation"
    assert result["current_phase"] == "final_recommendation"


def test_ml_reviewer_and_business_stakeholder_processed_reviews_return_payloads(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.business_stakeholder.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.load_prompts_config", _prompts)
    monkeypatch.setattr("multi_agent_ds.agents.business_stakeholder.load_prompts_config", _prompts)

    state = {"settings": _settings(), "processed_eda_insights": {"needs_cleaning": False}, "agent_decisions": []}
    ml_review = ml_reviewer_node(state, mode="processed_review")
    biz_review = business_stakeholder_node(state, mode="processed_review")

    assert ml_review["processed_eda_ml_review"]["summary"] == "The EDA review is acceptable."
    assert biz_review["processed_eda_business_review"]["summary"] == "The EDA review is acceptable."
