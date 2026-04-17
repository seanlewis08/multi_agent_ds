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
        title = schema.get("title")

        if title == "EDAReviewOutput":
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

        canned: dict[str, dict[str, Any]] = {
            "PreparationExecutionPlan": {
                "summary": "The plan is feasible.",
                "ready_for_execution": True,
                "cleaning_actions": [
                    {
                        "area": "cleaning",
                        "action": "clip_outliers_iqr",
                        "rationale": "Reduce extreme leverage points.",
                        "params": {"columns": ["claim_amount_avg"]},
                    }
                ],
                "feature_actions": [
                    {
                        "area": "feature_engineering",
                        "action": "ratio",
                        "rationale": "Surface per-unit ratios.",
                        "params": {"numerator": "a", "denominator": "b"},
                    }
                ],
                "action_feedback": [
                    {
                        "action": "clip_outliers_iqr",
                        "feasible": True,
                        "reason": "The feature is numeric.",
                    }
                ],
                "execution_notes": ["Run the approved plan once."],
            },
            # Back-compat: some older schema lookups may still use the alias.
            "PreparationFeedbackOutput": {
                "summary": "The plan is feasible.",
                "ready_for_execution": True,
                "cleaning_actions": [
                    {
                        "area": "cleaning",
                        "action": "clip_outliers_iqr",
                        "rationale": "Reduce extreme leverage points.",
                        "params": {"columns": ["claim_amount_avg"]},
                    }
                ],
                "feature_actions": [],
                "action_feedback": [
                    {
                        "action": "clip_outliers_iqr",
                        "feasible": True,
                        "reason": "The feature is numeric.",
                    }
                ],
                "execution_notes": ["Run the approved plan once."],
            },
            "BaselineDecision": {
                "summary": "LightGBM leads; both algorithms are worth tuning.",
                "algorithms_to_tune": ["lightgbm", "logistic_regression"],
                "algorithms_to_drop": [],
                "reasoning": "Baseline scores are within tuning range for both models.",
            },
            "TuningDecision": {
                "algorithm": "lightgbm",
                "accept_tuned_params": True,
                "chosen_params": {"max_depth": 7, "num_leaves": 63},
                "reasoning": "CV gini improved by 0.03 with flat convergence slope.",
            },
            "LearningRateDecision": {
                "algorithm": "lightgbm",
                "keep_adjustment": True,
                "chosen_learning_rate": 0.005,
                "chosen_n_estimators": 1000,
                "reasoning": "Lower lr improved test gini beyond prior CV std.",
            },
            "FeatureSelectionDecision": {
                "algorithm": "lightgbm",
                "accept_subset": True,
                "kept_features": ["age", "income"],
                "dropped_features": ["postal_code"],
                "reasoning": "Subset score held within one CV std of prior.",
            },
            "ModelingVerdict": {
                "summary": "LightGBM leads across every metric.",
                "best_algorithm": "lightgbm",
                "ranked_algorithms": ["lightgbm", "logistic_regression"],
                "final_metrics": {
                    "lightgbm": {"gini": 0.66},
                    "logistic_regression": {"gini": 0.52},
                },
                "justification": "LightGBM primary-metric lead is larger than either model's CV std.",
                "next_action": "proceed_to_evaluation",
            },
            "MLReviewOutput": {
                "summary": "Decisions hold up against the CV evidence.",
                "approved": True,
                "next_action": "accept",
                "decisions": [
                    {
                        "decision": "Keep both algorithms in the tuning set",
                        "classification": "scientific",
                        "mathematical_basis": "Baseline scores within tuning range for both.",
                        "reasoning_quality": "adequate",
                        "revision_questions": [],
                    }
                ],
                "phase": None,
            },
        }

        if title in canned:
            return {"parsed": canned[title]}

        raise AssertionError(f"Unexpected schema: {schema.get('title')}")


def _settings() -> dict[str, Any]:
    """Minimal routing-shaped settings dict.

    The tests patch ``build_adapter`` to return a ``FakeReviewAdapter`` directly,
    so the resolver is never exercised at runtime — but a well-formed block
    here makes the harness robust if a patch ever regresses and the real
    resolver runs.
    """
    return {
        "llm": {
            "default_provider": "openai",
            "model_matrix": {
                "balanced": {"cheap": "gpt-4.1-mini", "moderate": "gpt-4.1", "expensive": "gpt-4.1"},
                "coding": {"cheap": "gpt-4.1-mini", "moderate": "gpt-4.1", "expensive": "gpt-4.1"},
                "reasoning": {"cheap": "o4-mini", "moderate": "o3", "expensive": "o3"},
            },
            "capability_settings": {
                "balanced": {"temperature": 0.2, "max_tokens": 1000},
                "coding": {"temperature": 0.1, "max_tokens": 1000},
                "reasoning": {"temperature": None, "max_tokens": 2000},
            },
            "routes": {
                "default": {"capability": "balanced", "cost": "cheap"},
                "eda_analyst": {"capability": "balanced", "cost": "cheap"},
                "ml_reviewer": {"capability": "balanced", "cost": "cheap"},
                "business_stakeholder": {"capability": "balanced", "cost": "cheap"},
                "data_engineer": {
                    "default": {"capability": "balanced", "cost": "cheap"},
                },
                "ml_modeler": {
                    "default": {"capability": "balanced", "cost": "cheap"},
                },
            },
        }
    }


def _fake_build_adapter_factory(cls: type) -> Any:
    """Return a build_adapter stand-in that instantiates ``cls(settings)``."""

    def _build(settings: dict[str, Any], *, agent: str, task: str | None) -> Any:
        return cls(settings)

    return _build


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
            "baseline_review": "phase={phase}; payload={payload_json}",
            "tuning_review": "phase={phase}; payload={payload_json}",
            "lr_adjustment_review": "phase={phase}; payload={payload_json}",
            "feature_selection_review": "phase={phase}; payload={payload_json}",
            "final_recommendation_review": "phase={phase}; payload={payload_json}",
        },
        "business_stakeholder": {
            "system": "You are a business stakeholder.",
            "eda_review": "stage={review_stage}; eda={eda_json}",
        },
    }


def test_data_engineer_feedback_returns_structured_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "multi_agent_ds.agents.data_engineer.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
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
    # Engineer's executable plan carries cleaning + feature actions now.
    assert result["prep_feedback"]["cleaning_actions"][0]["action"] == "clip_outliers_iqr"
    assert result["prep_feedback"]["feature_actions"][0]["action"] == "ratio"
    assert result["agent_decisions"][0]["summary"] == "The plan is feasible."
    assert result["agent_decisions"][0]["action_feedback_count"] == 1
    assert result["agent_decisions"][0]["cleaning_action_count"] == 1
    assert result["agent_decisions"][0]["feature_action_count"] == 1
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


def test_data_engineer_execute_uses_feedback_plan_not_analyst_plan(monkeypatch) -> None:
    """``execute`` must run the engineer's plan (``prep_feedback``), not the analyst's."""
    captured: dict[str, Any] = {}

    def fake_run_preparation_workflow(
        data_path: str,
        prep_plan: dict[str, Any],
        settings: dict[str, Any],
        local_only: bool = False,
    ) -> dict[str, Any]:
        captured["prep_plan"] = prep_plan
        return {
            "source_data_path": data_path,
            "target_column": "binary_target",
            "artifact_filename": "example_processed.parquet",
            "processed_data_path": "s3://bucket/processed.parquet",
            "source_n_rows": 10,
            "source_n_features": 3,
            "n_rows": 10,
            "n_features": 4,
            "processed_n_rows": 10,
            "processed_n_features": 4,
            "cleaning_summary": [],
            "feature_summary": [],
        }

    monkeypatch.setattr(
        "multi_agent_ds.agents.data_engineer.run_preparation_workflow",
        fake_run_preparation_workflow,
    )

    analyst_actions = [{"area": "cleaning", "action": "analyst_only_action", "rationale": "analyst", "params": {}}]
    engineer_actions = [{"area": "cleaning", "action": "engineer_refined_action", "rationale": "engineer", "params": {}}]

    data_engineer_node(
        {
            "settings": _settings(),
            "data_path": "data/raw/example.parquet",
            "prep_plan": {
                "cleaning_actions": analyst_actions,
                "feature_actions": [],
            },
            "prep_feedback": {
                "summary": "Engineer refined plan.",
                "ready_for_execution": True,
                "cleaning_actions": engineer_actions,
                "feature_actions": [],
                "action_feedback": [],
                "execution_notes": [],
            },
            "agent_decisions": [],
        },
        mode="execute",
    )

    # The engineer's plan — not the analyst's — must be what ran.
    assert captured["prep_plan"]["cleaning_actions"] == engineer_actions
    assert captured["prep_plan"]["cleaning_actions"] != analyst_actions


def test_data_engineer_execute_falls_back_to_analyst_plan_when_feedback_empty(monkeypatch) -> None:
    """When ``prep_feedback`` is missing or action-empty, fall back to ``prep_plan``."""
    captured: dict[str, Any] = {}

    def fake_run_preparation_workflow(
        data_path: str,
        prep_plan: dict[str, Any],
        settings: dict[str, Any],
        local_only: bool = False,
    ) -> dict[str, Any]:
        captured["prep_plan"] = prep_plan
        return {
            "source_data_path": data_path,
            "target_column": "binary_target",
            "artifact_filename": "example_processed.parquet",
            "processed_data_path": "s3://bucket/processed.parquet",
            "source_n_rows": 10,
            "source_n_features": 3,
            "n_rows": 10,
            "n_features": 4,
            "processed_n_rows": 10,
            "processed_n_features": 4,
            "cleaning_summary": [],
            "feature_summary": [],
        }

    monkeypatch.setattr(
        "multi_agent_ds.agents.data_engineer.run_preparation_workflow",
        fake_run_preparation_workflow,
    )

    analyst_actions = [{"area": "cleaning", "action": "analyst_action", "rationale": "r", "params": {}}]

    # Case 1: prep_feedback missing entirely.
    data_engineer_node(
        {
            "settings": _settings(),
            "data_path": "data/raw/example.parquet",
            "prep_plan": {"cleaning_actions": analyst_actions, "feature_actions": []},
            "agent_decisions": [],
        },
        mode="execute",
    )
    assert captured["prep_plan"]["cleaning_actions"] == analyst_actions

    # Case 2: prep_feedback present but both action lists are empty.
    data_engineer_node(
        {
            "settings": _settings(),
            "data_path": "data/raw/example.parquet",
            "prep_plan": {"cleaning_actions": analyst_actions, "feature_actions": []},
            "prep_feedback": {
                "summary": "No concrete actions yet.",
                "ready_for_execution": False,
                "cleaning_actions": [],
                "feature_actions": [],
                "action_feedback": [],
                "execution_notes": [],
            },
            "agent_decisions": [],
        },
        mode="execute",
    )
    assert captured["prep_plan"]["cleaning_actions"] == analyst_actions


def test_ml_modeler_raw_review_returns_review_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
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

    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
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
    assert result["modeling_iteration"] == 1
    assert result["modeling_results"]["prior"] == "kept"
    assert "lightgbm" in result["modeling_results"]["baseline"]
    assert result["modeling_results"]["baseline_decision"]["algorithms_to_tune"] == [
        "lightgbm",
        "logistic_regression",
    ]
    decision_log = result["agent_decisions"][0]
    assert decision_log["phase"] == "baseline"
    assert decision_log["algorithms_to_tune"] == ["lightgbm", "logistic_regression"]


def test_ml_modeler_baseline_injects_reviewer_critique_on_loopback(monkeypatch) -> None:
    """On revise loop-back, the modeler's next prompt must include the reviewer's critique."""
    captured = {}

    class CapturingAdapter(FakeReviewAdapter):
        def structured_output(self, messages, schema):
            captured["user_content"] = messages[1]["content"]
            return super().structured_output(messages, schema)

    def fake_train_with_defaults(data, settings=None, algorithms=None):
        return {"lightgbm": {"cv_scores": {"gini": 0.6}, "test_scores": {"gini": 0.59},
                              "params_used": {}, "model": object(), "y_pred": "x", "y_prob": "x",
                              "elapsed_seconds": 0.1, "phase": "baseline"}}

    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.build_adapter",
        _fake_build_adapter_factory(CapturingAdapter),
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.train_with_defaults", fake_train_with_defaults)

    # Extend the _prompts fixture in-place for this test so {critique_section} is actually rendered
    prompts_with_critique = _prompts()
    prompts_with_critique["sean_ml_modeler"]["baseline_review"] = (
        "{critique_section}results={results_json}"
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.load_prompts_config", lambda: prompts_with_critique
    )

    state = {
        "settings": _settings(),
        "data": {"X_train": "fake"},
        "ml_review": {
            "baseline": {
                "summary": "Baseline pick ignored the CV/test gap for logistic_regression.",
                "approved": False,
                "next_action": "revise_modeling",
                "decisions": [
                    {
                        "decision": "Keep both algorithms in the tuning set",
                        "classification": "mixed",
                        "mathematical_basis": "CV/test gap not examined.",
                        "reasoning_quality": "weak",
                        "revision_questions": [
                            "What is the CV/test gini gap for logistic_regression?",
                            "Is the lightgbm lead larger than either model's CV std?",
                        ],
                    }
                ],
                "phase": "baseline",
            }
        },
        "agent_decisions": [],
        "modeling_iteration": 0,
    }

    ml_modeler_node(state, mode="baseline")

    prompt = captured["user_content"]
    assert "Prior reviewer critique" in prompt
    assert "Baseline pick ignored the CV/test gap" in prompt
    assert "What is the CV/test gini gap" in prompt
    assert "Is the lightgbm lead" in prompt


def test_ml_modeler_baseline_omits_critique_on_fresh_entry(monkeypatch) -> None:
    """Without a prior ml_review entry, the critique section must be empty."""
    captured = {}

    class CapturingAdapter(FakeReviewAdapter):
        def structured_output(self, messages, schema):
            captured["user_content"] = messages[1]["content"]
            return super().structured_output(messages, schema)

    def fake_train_with_defaults(data, settings=None, algorithms=None):
        return {"lightgbm": {"cv_scores": {"gini": 0.6}, "test_scores": {"gini": 0.59},
                              "params_used": {}, "model": object(), "y_pred": "x", "y_prob": "x",
                              "elapsed_seconds": 0.1, "phase": "baseline"}}

    prompts_with_critique = _prompts()
    prompts_with_critique["sean_ml_modeler"]["baseline_review"] = (
        "{critique_section}results={results_json}"
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.build_adapter",
        _fake_build_adapter_factory(CapturingAdapter),
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.load_prompts_config", lambda: prompts_with_critique
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.train_with_defaults", fake_train_with_defaults)

    ml_modeler_node(
        {"settings": _settings(), "data": {"X_train": "fake"}, "agent_decisions": []},
        mode="baseline",
    )

    assert "Prior reviewer critique" not in captured["user_content"]


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

    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
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
    assert result["modeling_iteration"] == 1
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

    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.adjust_learning_rate", fake_adjust_learning_rate
    )

    result = ml_modeler_node(
        {
            "settings": {
                **_settings(),
                "model": {"primary_metric": "gini", "tuning": {"lr_reduction_factor": 0.5}},
            },
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
    assert result["modeling_iteration"] == 1


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

    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
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
    assert result["modeling_iteration"] == 1


def test_ml_modeler_final_recommendation_picks_best_with_latest_phase(monkeypatch) -> None:
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_modeler.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
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
    assert result["modeling_iteration"] == 1


def test_ml_reviewer_and_business_stakeholder_processed_reviews_return_payloads(monkeypatch) -> None:
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_reviewer.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.load_prompts_config", _prompts)
    monkeypatch.setattr("multi_agent_ds.agents.business_stakeholder.load_prompts_config", _prompts)

    state = {"settings": _settings(), "processed_eda_insights": {"needs_cleaning": False}, "agent_decisions": []}
    ml_review = ml_reviewer_node(state, mode="processed_review")
    biz_review = business_stakeholder_node(state, mode="processed_review")

    assert ml_review["processed_eda_ml_review"]["summary"] == "The EDA review is acceptable."
    assert biz_review["processed_eda_business_review"]["summary"] == "The EDA review is acceptable."


class RevisingReviewerAdapter(FakeReviewAdapter):
    """Returns a revise verdict on every MLReviewOutput request."""

    def structured_output(self, messages, schema):
        props = schema["properties"]
        if {"approved", "next_action", "decisions"}.issubset(props):
            return {
                "parsed": {
                    "summary": "Tuning accepted on noise-level CV improvement.",
                    "approved": False,
                    "next_action": "revise_modeling",
                    "decisions": [
                        {
                            "decision": "Accept tuned params",
                            "classification": "art",
                            "mathematical_basis": "Improvement inside one CV std.",
                            "reasoning_quality": "weak",
                            "revision_questions": [
                                "What is the CV std of the baseline score?",
                                "Does the test score track the CV score?",
                            ],
                        }
                    ],
                    "phase": None,
                }
            }
        return super().structured_output(messages, schema)


def _reviewer_state(phase_blocks: dict[str, Any]) -> dict[str, Any]:
    """Build the minimum state a reviewer modeling-review mode needs."""
    return {
        "settings": _settings(),
        "modeling_results": phase_blocks,
        "modeling_verdict": phase_blocks.get("_verdict"),
        "agent_decisions": [],
    }


def test_ml_reviewer_rejects_unknown_mode() -> None:
    try:
        ml_reviewer_node({"settings": _settings(), "agent_decisions": []}, mode="not_a_mode")
    except ValueError as exc:
        assert "Unsupported mode" in str(exc)
    else:
        raise AssertionError("ml_reviewer_node should reject unknown modes")


def test_ml_reviewer_baseline_review_approves_sound_decision(monkeypatch) -> None:
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_reviewer.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.load_prompts_config", _prompts)

    result = ml_reviewer_node(
        _reviewer_state(
            {
                "baseline": {
                    "lightgbm": {
                        "cv_scores": {"gini": 0.61},
                        "test_scores": {"gini": 0.60},
                        "params_used": {},
                        "model": object(),
                        "y_pred": "numpy",
                        "y_prob": "numpy",
                    },
                    "logistic_regression": {
                        "cv_scores": {"gini": 0.52},
                        "test_scores": {"gini": 0.51},
                        "params_used": {},
                        "model": object(),
                        "y_pred": "numpy",
                        "y_prob": "numpy",
                    },
                },
                "baseline_decision": {
                    "summary": "Keep both",
                    "algorithms_to_tune": ["lightgbm", "logistic_regression"],
                    "algorithms_to_drop": [],
                    "reasoning": "Within range",
                },
            }
        ),
        mode="baseline_review",
    )

    assert result["ml_review"]["baseline"]["approved"] is True
    assert result["ml_review"]["baseline"]["next_action"] == "accept"
    assert result["ml_review"]["baseline"]["phase"] == "baseline"
    assert result["should_revise_modeling"] is False
    assert result["agent_decisions"][0]["phase"] == "baseline_review"
    assert result["agent_decisions"][0]["review_phase"] == "baseline"
    assert result["agent_decisions"][0]["approved"] is True


def test_ml_reviewer_tuning_review_revises_weak_decision(monkeypatch) -> None:
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_reviewer.build_adapter",
        _fake_build_adapter_factory(RevisingReviewerAdapter),
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.load_prompts_config", _prompts)

    result = ml_reviewer_node(
        _reviewer_state(
            {
                "tuning": {
                    "lightgbm": {
                        "best_params": {"max_depth": 7},
                        "best_score": 0.614,
                        "baseline_score": 0.61,
                        "score_improvement": 0.004,
                        "trial_history": [{"number": i} for i in range(50)],
                    },
                },
                "tuning_decisions": {
                    "lightgbm": {
                        "algorithm": "lightgbm",
                        "accept_tuned_params": True,
                        "chosen_params": {"max_depth": 7},
                        "reasoning": "Small improvement.",
                    },
                },
            }
        ),
        mode="tuning_review",
    )

    assert result["ml_review"]["tune"]["approved"] is False
    assert result["ml_review"]["tune"]["next_action"] == "revise_modeling"
    assert result["should_revise_modeling"] is True
    payload_prompt = result["ml_review"]["tune"]
    # verbose trial history must not have propagated into the stored review
    assert "trial_history" not in payload_prompt


def test_ml_reviewer_lr_adjustment_review_returns_phase_verdict(monkeypatch) -> None:
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_reviewer.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.load_prompts_config", _prompts)

    result = ml_reviewer_node(
        _reviewer_state(
            {
                "adjust_lr": {
                    "lightgbm": {
                        "test_scores": {"gini": 0.68},
                        "params_used": {"learning_rate": 0.005},
                        "learning_rate_adjustment": {
                            "old_score": 0.65,
                            "new_score": 0.68,
                            "improved": True,
                        },
                        "model": object(),
                    },
                },
                "adjust_lr_decisions": {
                    "lightgbm": {
                        "algorithm": "lightgbm",
                        "keep_adjustment": True,
                        "chosen_learning_rate": 0.005,
                        "chosen_n_estimators": 1000,
                        "reasoning": "Better than prior CV std.",
                    },
                },
            }
        ),
        mode="lr_adjustment_review",
    )

    assert result["ml_review"]["adjust_lr"]["phase"] == "adjust_lr"
    assert result["should_revise_modeling"] is False


def test_ml_reviewer_feature_selection_review_receives_importances(monkeypatch) -> None:
    captured = {}

    class CapturingAdapter(FakeReviewAdapter):
        def structured_output(self, messages, schema):
            captured["user_content"] = messages[1]["content"]
            return super().structured_output(messages, schema)

    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_reviewer.build_adapter",
        _fake_build_adapter_factory(CapturingAdapter),
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.load_prompts_config", _prompts)

    ml_reviewer_node(
        _reviewer_state(
            {
                "feature_selection": {
                    "lightgbm": {
                        "test_scores": {"gini": 0.66},
                        "cv_scores": {"gini": 0.66},
                        "test_score_delta_vs_prior": 0.01,
                    },
                },
                "feature_selection_decisions": {
                    "lightgbm": {
                        "algorithm": "lightgbm",
                        "accept_subset": True,
                        "kept_features": ["age"],
                        "dropped_features": ["postal_code"],
                        "reasoning": "Held score.",
                    },
                },
                "importances": {
                    "lightgbm": {
                        "source_phase": "train_tuned",
                        "native": {},
                        "permutation": {"safe_to_remove": ["postal_code"]},
                    }
                },
            }
        ),
        mode="feature_selection_review",
    )

    assert "postal_code" in captured["user_content"]
    assert "importances" in captured["user_content"]


def test_ml_reviewer_final_recommendation_review_reads_verdict(monkeypatch) -> None:
    monkeypatch.setattr(
        "multi_agent_ds.agents.ml_reviewer.build_adapter",
        _fake_build_adapter_factory(FakeReviewAdapter),
    )
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.load_prompts_config", _prompts)

    state = _reviewer_state(
        {
            "final_candidates": {
                "lightgbm": {"final_phase": "feature_selection", "test_scores": {"gini": 0.66}},
                "logistic_regression": {"final_phase": "baseline", "test_scores": {"gini": 0.51}},
            },
        }
    )
    state["modeling_verdict"] = {
        "summary": "LightGBM leads.",
        "best_algorithm": "lightgbm",
        "ranked_algorithms": ["lightgbm", "logistic_regression"],
        "final_metrics": {"lightgbm": {"gini": 0.66}, "logistic_regression": {"gini": 0.51}},
        "justification": "Clear lead.",
        "next_action": "proceed_to_evaluation",
    }

    result = ml_reviewer_node(state, mode="final_recommendation_review")

    assert result["ml_review"]["final_recommendation"]["phase"] == "final_recommendation"
    assert result["should_revise_modeling"] is False
