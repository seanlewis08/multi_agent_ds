"""Machine learning modeler agent for pre-fit EDA review and modeling handoff."""

from __future__ import annotations

import json
from typing import Any

from multi_agent_ds.adapters.llm import OpenAIAdapter
from multi_agent_ds.core import load_prompts_config, load_settings
from multi_agent_ds.core.contracts import (
    BaselineDecision,
    EDAReviewOutput,
    FeatureSelectionDecision,
    LearningRateDecision,
    ModelingVerdict,
    TuningDecision,
)
from multi_agent_ds.orchestration.state import PipelineState
from multi_agent_ds.skills.modeling import (
    ALGORITHM_REGISTRY,
    adjust_learning_rate,
    find_optimal_estimators,
    get_feature_importances,
    get_permutation_importances,
    train_with_defaults,
    train_with_feature_subset,
    train_with_params,
    tune_algorithm,
)

_BASELINE_PROMPT_DROP_KEYS = ("model", "y_pred", "y_prob")
_TUNING_PROMPT_DROP_KEYS = ("trial_history",)
_PHASE_PREFERENCE = ("feature_selection", "adjust_lr", "train_tuned", "baseline")


def _schema_for(model_cls: type[Any]) -> dict[str, Any]:
    if hasattr(model_cls, "model_json_schema"):
        return model_cls.model_json_schema()
    return model_cls.schema()


def _dump_model(model_cls: type[Any], payload: dict[str, Any]) -> dict[str, Any]:
    validated = model_cls(**payload)
    if hasattr(validated, "model_dump"):
        return validated.model_dump()
    return validated.dict()


def _append_decision(state: PipelineState, phase: str, **payload: Any) -> list[dict[str, Any]]:
    return state.get("agent_decisions", []) + [{"agent": "ml_modeler", "phase": phase, **payload}]


def _review_payload(state: PipelineState, review_stage: str) -> dict[str, Any]:
    if review_stage == "raw":
        return state["raw_eda_insights"]
    return state["processed_eda_insights"]


def _serialize_baseline_for_prompt(results: dict[str, Any]) -> dict[str, Any]:
    """Strip non-serializable objects so baseline results fit in a prompt."""
    summary = {}
    for algo_name, result in results.items():
        summary[algo_name] = {
            key: value for key, value in result.items() if key not in _BASELINE_PROMPT_DROP_KEYS
        }
    return summary


def _serialize_tuning_for_prompt(tuning_result: dict[str, Any]) -> dict[str, Any]:
    """Strip the verbose trial history so tuning results fit in a prompt."""
    return {k: v for k, v in tuning_result.items() if k not in _TUNING_PROMPT_DROP_KEYS}


def _baseline_score_for(state: PipelineState, algo_name: str, metric: str) -> float:
    baseline = state.get("modeling_results", {}).get("baseline", {}).get(algo_name, {})
    return float(baseline.get("cv_scores", {}).get(metric, 0.0))


def _boosting_inputs_for(state: PipelineState, algo_name: str) -> tuple[float | None, int | None]:
    """Pick (learning_rate, n_estimators) for tune_algorithm, preferring prior n_estimator_search."""
    algo_info = ALGORITHM_REGISTRY[algo_name]
    if not algo_info.get("supports_boosting_phases", False):
        return None, None
    defaults = algo_info.get("default_params", {})
    prior_search = state.get("modeling_results", {}).get("n_estimator_search", {}).get(algo_name, {})
    return (
        prior_search.get("learning_rate", defaults.get("learning_rate")),
        prior_search.get("optimal_n_estimators", defaults.get("n_estimators")),
    )


def _latest_result_for(state: PipelineState, algo_name: str) -> tuple[str, dict[str, Any]]:
    """Return (phase_name, result_dict) for the most recent fitted result of this algo."""
    results = state.get("modeling_results", {})
    for phase in _PHASE_PREFERENCE:
        phase_bucket = results.get(phase, {})
        if algo_name in phase_bucket:
            return phase, phase_bucket[algo_name]
    raise KeyError(f"No fitted result found for algorithm '{algo_name}'")


def _next_modeling_iteration(state: PipelineState, phase_name: str) -> int:
    """Return the next modeling_iteration value for a reviewed phase.

    Resets to 1 on fresh entry (first run or advance from a different phase)
    and increments on loop-back (reviewer set should_revise_modeling=True and
    the router sent us back to the same phase). The router's iteration cap is
    therefore evaluated per-phase, so burning the budget on `baseline` does
    not starve `tune` of its own revision budget.
    """
    if state.get("current_phase") == phase_name:
        return state.get("modeling_iteration", 0) + 1
    return 1


def _tuned_params_for(state: PipelineState, algo_name: str) -> dict[str, Any]:
    """Resolve the full parameter dict to use for post-tune retraining of this algo.

    Tune mode fixes learning_rate and n_estimators outside Optuna, so the
    LLM's chosen_params only contains the searched params. Merge the fixed
    boosting inputs back in so downstream training uses the same rate/depth
    pair that tuning was evaluated against.
    """
    decision = state["modeling_results"]["tuning_decisions"][algo_name]
    params = dict(decision["chosen_params"])
    tuning_skill = state["modeling_results"].get("tuning", {}).get(algo_name, {})
    lr_used = tuning_skill.get("learning_rate_used")
    n_est_used = tuning_skill.get("n_estimators_used")
    if lr_used is not None:
        params.setdefault("learning_rate", lr_used)
    if n_est_used is not None:
        params.setdefault("n_estimators", n_est_used)
    return params


def ml_modeler_node(state: PipelineState, mode: str = "eda_review") -> dict[str, Any]:
    """Run the requested ml_modeler stage."""
    settings = state.get("settings") or load_settings()

    if mode in {"raw_review", "processed_review"}:
        prompts = load_prompts_config()["sean_ml_modeler"]
        review_stage = "raw" if mode == "raw_review" else "processed"
        adapter = OpenAIAdapter(settings)
        response = adapter.structured_output(
            messages=[
                {"role": "system", "content": prompts["system"]},
                {
                    "role": "user",
                    "content": prompts["eda_review"].format(
                        eda_json=json.dumps(_review_payload(state, review_stage), sort_keys=True),
                        review_stage=review_stage,
                    ),
                },
            ],
            schema=_schema_for(EDAReviewOutput),
        )
        review = _dump_model(EDAReviewOutput, response["parsed"])
        review_key = (
            "raw_eda_ml_modeler_review" if review_stage == "raw" else "processed_eda_ml_modeler_review"
        )
        return {
            review_key: review,
            "agent_decisions": _append_decision(
                state,
                f"{review_stage}_eda_review",
                review_key=review_key,
            ),
        }

    if mode == "baseline":
        prompts = load_prompts_config()["sean_ml_modeler"]
        data = state["data"]
        baseline_results = train_with_defaults(data, settings)
        prompt_payload = _serialize_baseline_for_prompt(baseline_results)

        adapter = OpenAIAdapter(settings)
        response = adapter.structured_output(
            messages=[
                {"role": "system", "content": prompts["system"]},
                {
                    "role": "user",
                    "content": prompts["baseline_review"].format(
                        results_json=json.dumps(prompt_payload, sort_keys=True, default=str),
                    ),
                },
            ],
            schema=_schema_for(BaselineDecision),
        )
        decision = _dump_model(BaselineDecision, response["parsed"])
        prior_results = state.get("modeling_results", {})
        return {
            "modeling_results": prior_results | {"baseline": baseline_results, "baseline_decision": decision},
            "agent_decisions": _append_decision(
                state,
                "baseline",
                summary=decision["summary"],
                algorithms_to_tune=decision["algorithms_to_tune"],
                algorithms_to_drop=decision["algorithms_to_drop"],
            ),
            "current_phase": "baseline",
            "modeling_iteration": _next_modeling_iteration(state, "baseline"),
        }

    if mode == "tune":
        prompts = load_prompts_config()["sean_ml_modeler"]
        data = state["data"]
        model_cfg = settings["model"]
        cv_folds = model_cfg["cv_folds"]
        primary_metric = model_cfg["primary_metric"]
        algos_to_tune = state["modeling_results"]["baseline_decision"]["algorithms_to_tune"]

        adapter = OpenAIAdapter(settings)
        tuning_skill_results: dict[str, Any] = {}
        tuning_decisions: dict[str, Any] = {}
        new_agent_entries: list[dict[str, Any]] = []

        for algo_name in algos_to_tune:
            learning_rate, n_estimators = _boosting_inputs_for(state, algo_name)
            baseline_score = _baseline_score_for(state, algo_name, primary_metric)
            skill_result = tune_algorithm(
                algo_name=algo_name,
                X_train=data["X_train"],
                y_train=data["y_train"],
                cv_folds=cv_folds,
                primary_metric=primary_metric,
                baseline_score=baseline_score,
                cat_cols=data["categorical_features"],
                learning_rate=learning_rate,
                n_estimators=n_estimators,
                settings=settings,
            )
            response = adapter.structured_output(
                messages=[
                    {"role": "system", "content": prompts["system"]},
                    {
                        "role": "user",
                        "content": prompts["tuning_review"].format(
                            algorithm=algo_name,
                            tuning_json=json.dumps(
                                _serialize_tuning_for_prompt(skill_result), sort_keys=True, default=str
                            ),
                        ),
                    },
                ],
                schema=_schema_for(TuningDecision),
            )
            decision = _dump_model(TuningDecision, response["parsed"])
            tuning_skill_results[algo_name] = skill_result
            tuning_decisions[algo_name] = decision
            new_agent_entries.append(
                {
                    "agent": "ml_modeler",
                    "phase": "tune",
                    "algorithm": algo_name,
                    "accept_tuned_params": decision["accept_tuned_params"],
                    "reasoning": decision["reasoning"],
                }
            )

        prior_results = state.get("modeling_results", {})
        return {
            "modeling_results": prior_results
            | {"tuning": tuning_skill_results, "tuning_decisions": tuning_decisions},
            "agent_decisions": state.get("agent_decisions", []) + new_agent_entries,
            "current_phase": "tune",
            "modeling_iteration": _next_modeling_iteration(state, "tune"),
        }

    if mode == "train_tuned":
        data = state["data"]
        primary_metric = settings["model"]["primary_metric"]
        tuning_decisions = state["modeling_results"]["tuning_decisions"]
        baseline_results = state["modeling_results"]["baseline"]

        retrained: dict[str, Any] = {}
        new_agent_entries: list[dict[str, Any]] = []

        for algo_name, decision in tuning_decisions.items():
            if not decision["accept_tuned_params"]:
                continue
            params = _tuned_params_for(state, algo_name)
            skill_result = train_with_params(
                algo_name=algo_name,
                params=params,
                data=data,
                settings=settings,
            )
            tuned_score = float(skill_result["test_scores"].get(primary_metric, 0.0))
            baseline_score = float(
                baseline_results[algo_name]["test_scores"].get(primary_metric, 0.0)
            )
            delta = tuned_score - baseline_score
            retrained[algo_name] = skill_result | {"test_score_delta_vs_baseline": delta}
            new_agent_entries.append(
                {
                    "agent": "ml_modeler",
                    "phase": "train_tuned",
                    "algorithm": algo_name,
                    "test_score_delta_vs_baseline": delta,
                }
            )

        prior_results = state.get("modeling_results", {})
        return {
            "modeling_results": prior_results | {"train_tuned": retrained},
            "agent_decisions": state.get("agent_decisions", []) + new_agent_entries,
            "current_phase": "train_tuned",
        }

    if mode == "n_estimator_search":
        data = state["data"]
        model_cfg = settings["model"]
        cv_folds = model_cfg["cv_folds"]
        primary_metric = model_cfg["primary_metric"]
        algos_to_tune = state["modeling_results"]["baseline_decision"]["algorithms_to_tune"]

        search_results: dict[str, Any] = {}
        skipped: list[str] = []
        new_agent_entries: list[dict[str, Any]] = []

        for algo_name in algos_to_tune:
            algo_info = ALGORITHM_REGISTRY[algo_name]
            if not algo_info.get("supports_boosting_phases", False):
                skipped.append(algo_name)
                continue
            learning_rate, _ = _boosting_inputs_for(state, algo_name)
            skill_result = find_optimal_estimators(
                algo_name=algo_name,
                X_train=data["X_train"],
                y_train=data["y_train"],
                learning_rate=learning_rate,
                cv_folds=cv_folds,
                primary_metric=primary_metric,
                cat_cols=data["categorical_features"],
            )
            search_results[algo_name] = skill_result
            new_agent_entries.append(
                {
                    "agent": "ml_modeler",
                    "phase": "n_estimator_search",
                    "algorithm": algo_name,
                    "optimal_n_estimators": skill_result.get("optimal_n_estimators"),
                    "best_score": skill_result.get("best_score"),
                }
            )

        prior_results = state.get("modeling_results", {})
        return {
            "modeling_results": prior_results | {"n_estimator_search": search_results},
            "agent_decisions": state.get("agent_decisions", []) + new_agent_entries,
            "current_phase": "n_estimator_search",
            "n_estimator_search_skipped": skipped,
        }

    if mode == "adjust_lr":
        prompts = load_prompts_config()["sean_ml_modeler"]
        data = state["data"]
        primary_metric = settings["model"]["primary_metric"]
        tuning_decisions = state["modeling_results"]["tuning_decisions"]

        adapter = OpenAIAdapter(settings)
        adjusted: dict[str, Any] = {}
        adjust_decisions: dict[str, Any] = {}
        skipped: list[str] = []
        new_agent_entries: list[dict[str, Any]] = []

        for algo_name, tune_decision in tuning_decisions.items():
            algo_info = ALGORITHM_REGISTRY[algo_name]
            if not algo_info.get("supports_boosting_phases", False):
                skipped.append(algo_name)
                continue
            if not tune_decision["accept_tuned_params"]:
                skipped.append(algo_name)
                continue
            current_params = _tuned_params_for(state, algo_name)
            current_lr = float(current_params["learning_rate"])
            lr_reduction_factor = settings["model"]["tuning"].get("lr_reduction_factor", 0.5)
            new_lr = current_lr * lr_reduction_factor
            current_score = float(
                state["modeling_results"]["train_tuned"][algo_name]["test_scores"].get(primary_metric, 0.0)
            )
            skill_result = adjust_learning_rate(
                algo_name=algo_name,
                current_params=current_params,
                current_score=current_score,
                new_learning_rate=new_lr,
                data=data,
                settings=settings,
            )
            prompt_payload = {
                k: v for k, v in skill_result.items() if k not in _BASELINE_PROMPT_DROP_KEYS
            }
            response = adapter.structured_output(
                messages=[
                    {"role": "system", "content": prompts["system"]},
                    {
                        "role": "user",
                        "content": prompts["lr_adjustment_review"].format(
                            algorithm=algo_name,
                            adjustment_json=json.dumps(prompt_payload, sort_keys=True, default=str),
                        ),
                    },
                ],
                schema=_schema_for(LearningRateDecision),
            )
            decision = _dump_model(LearningRateDecision, response["parsed"])
            adjusted[algo_name] = skill_result
            adjust_decisions[algo_name] = decision
            new_agent_entries.append(
                {
                    "agent": "ml_modeler",
                    "phase": "adjust_lr",
                    "algorithm": algo_name,
                    "keep_adjustment": decision["keep_adjustment"],
                    "chosen_learning_rate": decision["chosen_learning_rate"],
                    "chosen_n_estimators": decision["chosen_n_estimators"],
                }
            )

        prior_results = state.get("modeling_results", {})
        return {
            "modeling_results": prior_results
            | {"adjust_lr": adjusted, "adjust_lr_decisions": adjust_decisions},
            "agent_decisions": state.get("agent_decisions", []) + new_agent_entries,
            "current_phase": "adjust_lr",
            "adjust_lr_skipped": skipped,
            "modeling_iteration": _next_modeling_iteration(state, "adjust_lr"),
        }

    if mode == "importance_review":
        data = state["data"]
        primary_metric = settings["model"]["primary_metric"]
        baseline_decision = state["modeling_results"]["baseline_decision"]
        algos = [
            algo
            for algo in baseline_decision["algorithms_to_tune"]
            if any(algo in state["modeling_results"].get(phase, {}) for phase in _PHASE_PREFERENCE)
        ]

        importances: dict[str, Any] = {}
        new_agent_entries: list[dict[str, Any]] = []

        for algo_name in algos:
            phase, fitted = _latest_result_for(state, algo_name)
            model = fitted["model"]
            native = get_feature_importances(
                model=model,
                feature_names=fitted["feature_names"],
                algo_name=algo_name,
            )
            permutation = get_permutation_importances(
                model=model,
                X_test=data["X_test"],
                y_test=data["y_test"],
                feature_names=data["feature_names"],
                cat_cols=data["categorical_features"],
                algo_name=algo_name,
                scoring=primary_metric,
            )
            importances[algo_name] = {
                "source_phase": phase,
                "native": native,
                "permutation": permutation,
            }
            new_agent_entries.append(
                {
                    "agent": "ml_modeler",
                    "phase": "importance_review",
                    "algorithm": algo_name,
                    "source_phase": phase,
                    "safe_to_remove": permutation.get("safe_to_remove", []),
                }
            )

        prior_results = state.get("modeling_results", {})
        return {
            "modeling_results": prior_results | {"importances": importances},
            "agent_decisions": state.get("agent_decisions", []) + new_agent_entries,
            "current_phase": "importance_review",
        }

    if mode == "feature_selection":
        prompts = load_prompts_config()["sean_ml_modeler"]
        data = state["data"]
        primary_metric = settings["model"]["primary_metric"]
        importances = state["modeling_results"]["importances"]

        adapter = OpenAIAdapter(settings)
        subset_results: dict[str, Any] = {}
        subset_decisions: dict[str, Any] = {}
        skipped: list[str] = []
        new_agent_entries: list[dict[str, Any]] = []

        for algo_name, importance_bundle in importances.items():
            safe_to_remove = importance_bundle["permutation"].get("safe_to_remove", [])
            if not safe_to_remove:
                skipped.append(algo_name)
                continue
            all_features = data["feature_names"]
            keep_features = [f for f in all_features if f not in safe_to_remove]
            params = (
                _tuned_params_for(state, algo_name)
                if algo_name in state["modeling_results"].get("tuning_decisions", {})
                and state["modeling_results"]["tuning_decisions"][algo_name]["accept_tuned_params"]
                else state["modeling_results"]["baseline"][algo_name]["params_used"]
            )
            skill_result = train_with_feature_subset(
                algo_name=algo_name,
                params=params,
                data=data,
                keep_features=keep_features,
                settings=settings,
            )
            _, prior_fitted = _latest_result_for(state, algo_name)
            prior_score = float(prior_fitted["test_scores"].get(primary_metric, 0.0))
            subset_score = float(skill_result["test_scores"].get(primary_metric, 0.0))
            delta = subset_score - prior_score
            prompt_payload = {
                "algorithm": algo_name,
                "prior_phase": importance_bundle["source_phase"],
                "kept_features": keep_features,
                "dropped_features": safe_to_remove,
                "prior_test_score": prior_score,
                "subset_test_score": subset_score,
                "test_score_delta": delta,
                "subset_cv_scores": skill_result.get("cv_scores"),
                "subset_cv_std": skill_result.get("cv_std"),
            }
            response = adapter.structured_output(
                messages=[
                    {"role": "system", "content": prompts["system"]},
                    {
                        "role": "user",
                        "content": prompts["feature_selection_review"].format(
                            algorithm=algo_name,
                            selection_json=json.dumps(prompt_payload, sort_keys=True, default=str),
                        ),
                    },
                ],
                schema=_schema_for(FeatureSelectionDecision),
            )
            decision = _dump_model(FeatureSelectionDecision, response["parsed"])
            subset_results[algo_name] = skill_result | {"test_score_delta_vs_prior": delta}
            subset_decisions[algo_name] = decision
            new_agent_entries.append(
                {
                    "agent": "ml_modeler",
                    "phase": "feature_selection",
                    "algorithm": algo_name,
                    "accept_subset": decision["accept_subset"],
                    "dropped_features": decision["dropped_features"],
                    "test_score_delta_vs_prior": delta,
                }
            )

        prior_results = state.get("modeling_results", {})
        return {
            "modeling_results": prior_results
            | {"feature_selection": subset_results, "feature_selection_decisions": subset_decisions},
            "agent_decisions": state.get("agent_decisions", []) + new_agent_entries,
            "current_phase": "feature_selection",
            "feature_selection_skipped": skipped,
            "modeling_iteration": _next_modeling_iteration(state, "feature_selection"),
        }

    if mode == "final_recommendation":
        prompts = load_prompts_config()["sean_ml_modeler"]
        primary_metric = settings["model"]["primary_metric"]
        baseline_decision = state["modeling_results"]["baseline_decision"]
        algos = baseline_decision["algorithms_to_tune"]

        summary_payload: dict[str, Any] = {}
        for algo_name in algos:
            try:
                phase, fitted = _latest_result_for(state, algo_name)
            except KeyError:
                continue
            summary_payload[algo_name] = {
                "final_phase": phase,
                "params_used": fitted.get("params_used"),
                "cv_scores": fitted.get("cv_scores"),
                "test_scores": fitted.get("test_scores"),
            }

        adapter = OpenAIAdapter(settings)
        response = adapter.structured_output(
            messages=[
                {"role": "system", "content": prompts["system"]},
                {
                    "role": "user",
                    "content": prompts["final_recommendation"].format(
                        primary_metric=primary_metric,
                        candidates_json=json.dumps(summary_payload, sort_keys=True, default=str),
                    ),
                },
            ],
            schema=_schema_for(ModelingVerdict),
        )
        verdict = _dump_model(ModelingVerdict, response["parsed"])
        prior_results = state.get("modeling_results", {})
        return {
            "modeling_results": prior_results | {"final_candidates": summary_payload},
            "modeling_verdict": verdict,
            "agent_decisions": _append_decision(
                state,
                "final_recommendation",
                best_algorithm=verdict["best_algorithm"],
                next_action=verdict["next_action"],
            ),
            "current_phase": "final_recommendation",
            "modeling_iteration": _next_modeling_iteration(state, "final_recommendation"),
        }

    if mode == "modeling_handoff":
        modeling_context = {
            "processed_data_path": state.get("processed_data_path"),
            "processed_eda_insights": state.get("processed_eda_insights"),
            "raw_eda_reviews": {
                "ml_modeler": state.get("raw_eda_ml_modeler_review"),
                "ml_reviewer": state.get("raw_eda_ml_review"),
                "business_stakeholder": state.get("raw_eda_business_review"),
            },
            "processed_eda_reviews": {
                "ml_modeler": state.get("processed_eda_ml_modeler_review"),
                "ml_reviewer": state.get("processed_eda_ml_review"),
                "business_stakeholder": state.get("processed_eda_business_review"),
            },
        }
        return {
            "modeling_context": modeling_context,
            "agent_decisions": _append_decision(
                state,
                "modeling_handoff",
                processed_data_path=state.get("processed_data_path"),
            ),
            "current_phase": "modeling",
        }

    raise ValueError(f"Unsupported ml_modeler mode: {mode}")
