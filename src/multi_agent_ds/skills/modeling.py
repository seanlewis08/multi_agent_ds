"""Model training skill with phased hyperparameter tuning for agentic use.

This module exposes discrete functions that an ML modeler agent calls
in sequence. The agent controls the overall strategy — this module
executes the math.

Agent workflow:
    1. prepare_data()                 → split and tag categoricals
    2. train_with_defaults()          → baseline run, all algorithms
    3. find_optimal_estimators()      → CV search for best n_estimators at a given lr
    4. tune_algorithm()               → Optuna on tree/reg params (not learning rate)
    5. train_with_params()            → re-train with chosen params
    6. adjust_learning_rate()         → lower rate, scale estimators, evaluate
    7. get_feature_importances()      → native importance (fast diagnostic)
    8. get_permutation_importances()  → held-out permutation importance (removal decisions)
    9. train_with_feature_subset()    → re-train on a reduced feature set
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_validate, train_test_split
from tqdm import tqdm

from multi_agent_ds.core import load_settings
from multi_agent_ds.tools.evaluation import evaluate_on_test, resolve_scorers

logger = logging.getLogger(__name__)


# ── Search space functions ─────────────────────────────────────────────
# Learning rate is NEVER in the search space. The agent controls it.

def _lightgbm_search_space(trial, focus_params=None, fixed_params=None):
    """LightGBM search space for Optuna. Learning rate excluded by design."""
    fixed = fixed_params or {}

    all_params = {
        "max_depth": lambda: trial.suggest_int("max_depth", 3, 12),
        "num_leaves": lambda: trial.suggest_int("num_leaves", 20, 150),
        "min_child_samples": lambda: trial.suggest_int("min_child_samples", 5, 100),
        "subsample": lambda: trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": lambda: trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": lambda: trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": lambda: trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
    }

    params = {}
    tune_these = focus_params or list(all_params.keys())

    for name, sampler in all_params.items():
        if name in fixed:
            params[name] = fixed[name]
        elif name in tune_these:
            params[name] = sampler()

    return params


def _logistic_regression_search_space(trial, focus_params=None, fixed_params=None):
    """Logistic regression search space for Optuna."""
    fixed = fixed_params or {}

    all_params = {
        "C": lambda: trial.suggest_float("C", 1e-4, 10.0, log=True),
        "penalty": lambda: trial.suggest_categorical("penalty", ["l1", "l2"]),
    }

    params = {}
    tune_these = focus_params or list(all_params.keys())

    for name, sampler in all_params.items():
        if name in fixed:
            params[name] = fixed[name]
        elif name in tune_these:
            params[name] = sampler()

    if params.get("penalty") == "l1":
        params["solver"] = "saga"
    else:
        params["solver"] = "lbfgs"

    return params


# ── Algorithm registry ─────────────────────────────────────────────────

ALGORITHM_REGISTRY = {
    "lightgbm": {
        "class": LGBMClassifier,
        "encoding": "native",
        "search_space": _lightgbm_search_space,
        "supports_boosting_phases": True,
        "constructor_args": {"verbose": -1},
        "default_params": {
            "n_estimators": 500,
            "max_depth": 6,
            "learning_rate": 0.01,
            "num_leaves": 31,
            "min_child_samples": 20,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        },
    },
    "logistic_regression": {
        "class": LogisticRegression,
        "encoding": "onehot",
        "search_space": _logistic_regression_search_space,
        "supports_boosting_phases": False,
        "constructor_args": {"verbose": 0},
        "default_params": {
            "C": 1.0,
            "penalty": "l2",
            "solver": "lbfgs",
            "max_iter": 1000,
        },
    },
}


# ── Helper: build model instance ───────────────────────────────────────

def _build_model(algo_name: str, params: dict):
    """Instantiate a model with the right constructor_args for its algorithm."""
    algo_info = ALGORITHM_REGISTRY[algo_name]
    model_class = algo_info["class"]
    constructor_args = algo_info.get("constructor_args", {})
    return model_class(random_state=42, **constructor_args, **params)


def _extract_training_history(model, algo_name: str) -> dict[str, Any] | None:
    """Normalize iterative training history into a model-agnostic structure."""
    evals_result = getattr(model, "evals_result_", None)
    if not evals_result:
        return None

    series = []
    max_iterations = 0

    for dataset_name, metrics in evals_result.items():
        for metric_name, values in metrics.items():
            values_list = [float(value) for value in values]
            if not values_list:
                continue
            max_iterations = max(max_iterations, len(values_list))
            series.append(
                {
                    "dataset": dataset_name,
                    "metric": metric_name,
                    "values": values_list,
                }
            )

    if not series:
        return None

    best_iteration = getattr(model, "best_iteration_", None)
    if isinstance(best_iteration, int) and best_iteration <= 0:
        best_iteration = None

    return {
        "algorithm": algo_name,
        "history_source": "evals_result_",
        "n_iterations": max_iterations,
        "best_iteration": best_iteration,
        "series": series,
    }


def _fit_model_and_capture_history(
    model,
    algo_name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_validation: pd.DataFrame | None = None,
    y_validation: pd.Series | None = None,
) -> dict[str, Any] | None:
    """Fit a model and capture iterative training history when supported."""
    algo_info = ALGORITHM_REGISTRY[algo_name]

    if algo_info.get("supports_boosting_phases", False):
        eval_set = [(X_train, y_train)]
        eval_names = ["train"]
        if X_validation is not None and y_validation is not None:
            eval_set.append((X_validation, y_validation))
            eval_names.append("validation")
        model.fit(
            X_train,
            y_train,
            eval_set=eval_set,
            eval_names=eval_names,
            eval_metric="binary_logloss",
        )
        return _extract_training_history(model, algo_name)

    model.fit(X_train, y_train)
    return None


# ── Data preparation ───────────────────────────────────────────────────

def prepare_data(
    df: pd.DataFrame,
    target_col: str = "target",
    test_size: float = 0.2,
    validation_size: float | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """Split data and tag categoricals. No encoding — deferred to per-algorithm logic.

    Args:
        df: Input DataFrame with features and target column.
        target_col: Name of the target column (read from settings).
        test_size: Fraction of data for the test set.
        validation_size: Fraction of data for the validation set. Defaults to
                         `test_size` when omitted.
        random_state: Random seed for reproducibility.

    Returns:
        Dict with X_train, X_validation, X_test, y_train, y_validation, y_test,
        feature_names, categorical_features, and data_summary for agent context.
    """
    has_true_prob = "_true_probability" in df.columns
    validation_size = test_size if validation_size is None else validation_size
    if test_size <= 0 or validation_size <= 0:
        raise ValueError("test_size and validation_size must both be greater than 0.")
    if test_size + validation_size >= 1:
        raise ValueError("test_size + validation_size must be less than 1.")

    drop_cols = [target_col]
    if has_true_prob:
        drop_cols.append("_true_probability")

    X = df.drop(columns=drop_cols)
    y = df[target_col]

    cat_cols = X.select_dtypes(include=["object"]).columns.tolist()
    for col in cat_cols:
        X[col] = X[col].astype("category")

    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y,
    )
    validation_size_relative = validation_size / (1 - test_size)
    X_train, X_validation, y_train, y_validation = train_test_split(
        X_train_full,
        y_train_full,
        test_size=validation_size_relative,
        random_state=random_state,
        stratify=y_train_full,
    )

    result = {
        "X_train": X_train,
        "X_validation": X_validation,
        "X_test": X_test,
        "y_train": y_train,
        "y_validation": y_validation,
        "y_test": y_test,
        "feature_names": X.columns.tolist(),
        "categorical_features": cat_cols,
        "data_summary": {
            "n_train": len(X_train),
            "n_validation": len(X_validation),
            "n_test": len(X_test),
            "n_features": len(X.columns),
            "n_categorical": len(cat_cols),
            "n_numerical": len(X.columns) - len(cat_cols),
            "target_rate_train": float(y_train.mean()),
            "target_rate_validation": float(y_validation.mean()),
            "target_rate_test": float(y_test.mean()),
            "has_ground_truth": has_true_prob,
        },
    }

    if has_true_prob:
        true_prob = df.loc[:, "_true_probability"]
        result["true_prob_validation"] = true_prob.iloc[X_validation.index]
        result["true_prob_test"] = true_prob.iloc[X_test.index]

    return result


def _encode_for_algorithm(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    encoding: str,
    cat_cols: list[str],
    X_validation: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, ...]:
    """Apply encoding strategy based on algorithm type."""
    if encoding == "native":
        if X_validation is None:
            return X_train, X_test
        return X_train, X_validation, X_test

    elif encoding == "onehot":
        X_train_enc = pd.get_dummies(X_train, columns=cat_cols, drop_first=True)
        encoded_frames: list[pd.DataFrame] = [X_train_enc]
        if X_validation is not None:
            X_validation_enc = pd.get_dummies(X_validation, columns=cat_cols, drop_first=True)
            X_validation_enc = X_validation_enc.reindex(columns=X_train_enc.columns, fill_value=0)
            encoded_frames.append(X_validation_enc)
        X_test_enc = pd.get_dummies(X_test, columns=cat_cols, drop_first=True)
        X_test_enc = X_test_enc.reindex(columns=X_train_enc.columns, fill_value=0)
        encoded_frames.append(X_test_enc)
        return tuple(encoded_frames)

    else:
        raise ValueError(f"Unknown encoding strategy: {encoding}")


# ── Phase 1: Baseline with defaults ───────────────────────────────────

def train_with_defaults(
    data: dict[str, Any],
    settings: dict | None = None,
    algorithms: list[str] | None = None,
) -> dict[str, Any]:
    """Train configured algorithms with curated default params.

    This is the agent's first move — fast baseline to evaluate.

    Args:
        data: Output from prepare_data().
        settings: Config dict. Loaded from disk if None.
        algorithms: Override list of algorithm names to train. When provided,
                    only these algorithms run instead of the full list from
                    settings["model"]["algorithms"]. Useful for testing a
                    single model or a custom subset.

    Returns:
        Dict keyed by algorithm name with cv_scores, cv_std, test_scores,
        model, params_used, and timing info.
    """
    settings = settings or load_settings()
    model_cfg = settings["model"]
    algorithms = algorithms or model_cfg["algorithms"]
    cv_folds = model_cfg["cv_folds"]
    metric_names = model_cfg["scoring_metrics"]
    primary_metric = model_cfg["primary_metric"]

    X_train_raw, X_validation_raw, X_test_raw = data["X_train"], data["X_validation"], data["X_test"]
    y_train, y_validation, y_test = data["y_train"], data["y_validation"], data["y_test"]
    true_prob_validation = data.get("true_prob_validation")
    true_prob_test = data.get("true_prob_test")
    cat_cols = data["categorical_features"]

    scorers = resolve_scorers(metric_names)
    results = {}
    algo_bar = tqdm(algorithms, desc="Baseline training", unit="algo")

    for algo_name in algo_bar:
        if algo_name not in ALGORITHM_REGISTRY:
            logger.warning("Unknown algorithm '%s', skipping", algo_name)
            continue

        algo_bar.set_postfix(algorithm=algo_name)
        algo_info = ALGORITHM_REGISTRY[algo_name]
        encoding = algo_info["encoding"]
        default_params = algo_info.get("default_params", {})

        X_train, X_validation, X_test = _encode_for_algorithm(
            X_train_raw.copy(), X_test_raw.copy(), encoding, cat_cols, X_validation=X_validation_raw.copy(),
        )

        logger.info("Baseline %s | encoding: %s", algo_name, encoding)
        start = time.time()

        model = _build_model(algo_name, default_params)

        cv_results = cross_validate(
            model, X_train, y_train,
            cv=cv_folds, scoring=scorers, return_train_score=False,
        )

        cv_scores = {}
        cv_std = {}
        for metric in metric_names:
            key = f"test_{metric}"
            fold_scores = cv_results[key]
            cv_scores[metric] = float(np.mean(fold_scores))
            cv_std[metric] = float(np.std(fold_scores))

        training_history = _fit_model_and_capture_history(
            model, algo_name, X_train, y_train, X_validation, y_validation,
        )
        validation_result = evaluate_on_test(
            model, X_validation, y_validation, metric_names, true_prob_validation,
        )
        eval_result = evaluate_on_test(model, X_test, y_test, metric_names, true_prob_test)
        test_scores = eval_result["scores"]
        elapsed = time.time() - start

        results[algo_name] = {
            "cv_scores": cv_scores,
            "cv_std": cv_std,
            "cv_results_raw": {k: v.tolist() for k, v in cv_results.items()},
            "validation_scores": validation_result["scores"],
            "test_scores": test_scores,
            "y_pred": eval_result["y_pred"],
            "y_prob": eval_result["y_prob"],
            "model": model,
            "params_used": default_params,
            "feature_names": X_train.columns.tolist(),
            "training_history": training_history,
            "encoding": encoding,
            "elapsed_seconds": elapsed,
            "phase": "baseline",
        }

        logger.info("  %s baseline done in %.1fs | test %s: %.4f",
                     algo_name, elapsed, primary_metric,
                     test_scores.get(primary_metric, 0))

    return results


# ── Phase 1b: Find optimal n_estimators ────────────────────────────────

def find_optimal_estimators(
    algo_name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    learning_rate: float,
    cv_folds: int,
    primary_metric: str,
    cat_cols: list[str] | None = None,
    param_overrides: dict | None = None,
    max_estimators: int = 2000,
    step: int = 50,
) -> dict[str, Any]:
    """Find optimal n_estimators for a given learning rate via CV.

    The agent calls this to establish the learning_rate / n_estimators
    pair before tuning tree structure params.

    Only applicable to boosting algorithms (lightgbm, xgboost).

    Returns:
        Dict with optimal_n_estimators, scores_by_n, best_score,
        and whether the search stopped early.
    """
    # Guard against non-boosting algorithms
    algo_info = ALGORITHM_REGISTRY[algo_name]
    if not algo_info.get("supports_boosting_phases", False):
        return {
            "error": f"find_optimal_estimators is only applicable to boosting "
                     f"algorithms. '{algo_name}' does not support boosting phases.",
            "algorithm": algo_name,
            "supported_algorithms": [
                name for name, info in ALGORITHM_REGISTRY.items()
                if info.get("supports_boosting_phases", False)
            ],
        }

    # Encode data for this algorithm
    encoding = algo_info["encoding"]
    cat_cols = cat_cols or []
    X_train_enc, _ = _encode_for_algorithm(
        X_train.copy(), X_train.copy(), encoding, cat_cols,
    )

    base_params = (param_overrides or algo_info.get("default_params", {})).copy()
    base_params["learning_rate"] = learning_rate

    scorers = resolve_scorers([primary_metric])
    candidates = list(range(step, max_estimators + 1, step))
    scores_by_n = []

    n_bar = tqdm(candidates, desc=f"n_estimators search ({algo_name})", unit="step")
    for n in n_bar:
        base_params["n_estimators"] = n
        model = _build_model(algo_name, base_params)

        cv_results = cross_validate(
            model, X_train_enc, y_train,
            cv=cv_folds, scoring=scorers, return_train_score=False,
        )

        mean_score = float(np.mean(cv_results[f"test_{primary_metric}"]))
        std_score = float(np.std(cv_results[f"test_{primary_metric}"]))
        scores_by_n.append({
            "n_estimators": n,
            "mean_score": mean_score,
            "std_score": std_score,
        })

        n_bar.set_postfix(n_est=n, score=f"{mean_score:.4f}")
        logger.info("  n_estimators=%d | %s: %.4f (+/- %.4f)",
                     n, primary_metric, mean_score, std_score)

        if len(scores_by_n) >= 4:
            recent = [s["mean_score"] for s in scores_by_n[-4:]]
            if all(recent[i] >= recent[i + 1] for i in range(3)):
                logger.info("  Early stop: score declining for 3 steps")
                break

    best = max(scores_by_n, key=lambda s: s["mean_score"])

    return {
        "algorithm": algo_name,
        "learning_rate": learning_rate,
        "optimal_n_estimators": best["n_estimators"],
        "best_score": best["mean_score"],
        "best_std": best["std_score"],
        "scores_by_n": scores_by_n,
        "search_stopped_early": len(scores_by_n) < len(candidates),
    }


# ── Phase 2: Optuna tuning (tree/regularization params) ───────────────

def tune_algorithm(
    algo_name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cv_folds: int,
    primary_metric: str,
    baseline_score: float,
    cat_cols: list[str] | None = None,
    learning_rate: float | None = None,
    n_estimators: int | None = None,
    focus_params: list[str] | None = None,
    fixed_params: dict | None = None,
    settings: dict | None = None,
) -> dict[str, Any]:
    """Run Optuna on tree/regularization params. Learning rate is fixed.

    For boosting models, learning_rate and n_estimators must be provided.
    For non-boosting models (logistic_regression), they are ignored.

    Returns full study results for agent analysis including every trial,
    parameter importances, convergence info, and score distributions.
    """
    import optuna

    settings = settings or load_settings()
    tuning_cfg = settings["model"].get("tuning", {})
    algo_info = ALGORITHM_REGISTRY[algo_name]
    search_space_fn = algo_info["search_space"]
    encoding = algo_info["encoding"]
    cat_cols = cat_cols or []

    # Encode ONCE outside the objective
    X_train_enc, _ = _encode_for_algorithm(
        X_train.copy(), X_train.copy(), encoding, cat_cols,
    )

    def objective(trial):
        params = search_space_fn(trial, focus_params=focus_params, fixed_params=fixed_params)

        # Add boosting-specific params if applicable
        if learning_rate is not None:
            params["learning_rate"] = learning_rate
        if n_estimators is not None:
            params["n_estimators"] = n_estimators

        model = _build_model(algo_name, params)
        scorers = resolve_scorers([primary_metric])
        cv_results = cross_validate(
            model, X_train_enc, y_train,
            cv=cv_folds, scoring=scorers, return_train_score=False,
        )
        return float(np.mean(cv_results[f"test_{primary_metric}"]))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize")

    max_trials = tuning_cfg.get("max_trials", 50)
    timeout = tuning_cfg.get("timeout", 300)
    trial_bar = tqdm(total=max_trials, desc=f"Optuna tuning ({algo_name})", unit="trial")

    def _tqdm_callback(study, trial):
        trial_bar.update(1)
        best = study.best_value
        trial_bar.set_postfix(best=f"{best:.4f}", trial=trial.number)

    start = time.time()
    study.optimize(
        objective,
        n_trials=max_trials,
        timeout=timeout,
        callbacks=[_tqdm_callback],
    )
    trial_bar.close()
    elapsed = time.time() - start

    # ── Full trial history ──
    trial_history = []
    for trial in study.trials:
        trial_history.append({
            "number": trial.number,
            "score": trial.value,
            "params": trial.params,
            "duration_seconds": trial.duration.total_seconds() if trial.duration else 0,
            "state": trial.state.name,
        })

    # ── Parameter importances ──
    try:
        importances = optuna.importance.get_param_importances(study)
    except Exception:
        importances = {}

    # ── Score analysis ──
    scores = [t["score"] for t in trial_history if t["score"] is not None]
    rolling_best = np.maximum.accumulate(scores).tolist() if scores else []

    return {
        "algorithm": algo_name,
        "best_params": study.best_params,
        "best_score": study.best_value,
        "baseline_score": baseline_score,
        "score_improvement": study.best_value - baseline_score,
        "learning_rate_used": learning_rate,
        "n_estimators_used": n_estimators,

        "best_trial_number": study.best_trial.number,
        "total_trials": len(study.trials),
        "convergence_reached": study.best_trial.number < len(study.trials) - 5,
        "rolling_best_scores": rolling_best,

        "trial_history": trial_history,

        "score_mean": float(np.mean(scores)) if scores else None,
        "score_std": float(np.std(scores)) if scores else None,
        "score_min": float(np.min(scores)) if scores else None,
        "score_max": float(np.max(scores)) if scores else None,
        "score_median": float(np.median(scores)) if scores else None,

        "param_importances": importances,

        "focus_params": focus_params,
        "fixed_params": fixed_params,

        "total_duration_seconds": elapsed,
        "avg_trial_duration_seconds": elapsed / max(len(study.trials), 1),
    }


# ── Phase 3: Train with specific params ───────────────────────────────

def train_with_params(
    algo_name: str,
    params: dict,
    data: dict[str, Any],
    settings: dict | None = None,
) -> dict[str, Any]:
    """Train a specific algorithm with explicit params and evaluate.

    The agent calls this after tuning or after adjusting learning rate.
    """
    settings = settings or load_settings()
    model_cfg = settings["model"]
    cv_folds = model_cfg["cv_folds"]
    metric_names = model_cfg["scoring_metrics"]
    primary_metric = model_cfg["primary_metric"]

    algo_info = ALGORITHM_REGISTRY[algo_name]
    encoding = algo_info["encoding"]
    cat_cols = data["categorical_features"]

    X_train, X_validation, X_test = _encode_for_algorithm(
        data["X_train"].copy(), data["X_test"].copy(), encoding, cat_cols, X_validation=data["X_validation"].copy(),
    )
    y_train, y_validation, y_test = data["y_train"], data["y_validation"], data["y_test"]
    true_prob_validation = data.get("true_prob_validation")
    true_prob_test = data.get("true_prob_test")

    scorers = resolve_scorers(metric_names)

    start = time.time()

    model = _build_model(algo_name, params)

    cv_results = cross_validate(
        model, X_train, y_train,
        cv=cv_folds, scoring=scorers, return_train_score=False,
    )

    cv_scores = {}
    cv_std = {}
    for metric in metric_names:
        key = f"test_{metric}"
        fold_scores = cv_results[key]
        cv_scores[metric] = float(np.mean(fold_scores))
        cv_std[metric] = float(np.std(fold_scores))

    training_history = _fit_model_and_capture_history(
        model, algo_name, X_train, y_train, X_validation, y_validation,
    )
    validation_result = evaluate_on_test(
        model, X_validation, y_validation, metric_names, true_prob_validation,
    )
    eval_result = evaluate_on_test(model, X_test, y_test, metric_names, true_prob_test)
    test_scores = eval_result["scores"]
    elapsed = time.time() - start

    return {
        "algorithm": algo_name,
        "cv_scores": cv_scores,
        "cv_std": cv_std,
        "cv_results_raw": {k: v.tolist() for k, v in cv_results.items()},
        "validation_scores": validation_result["scores"],
        "test_scores": test_scores,
        "y_pred": eval_result["y_pred"],
        "y_prob": eval_result["y_prob"],
        "model": model,
        "params_used": params,
        "feature_names": X_train.columns.tolist(),
        "training_history": training_history,
        "encoding": encoding,
        "elapsed_seconds": elapsed,
    }


# ── Phase 3b: Agent-driven learning rate adjustment ────────────────────

def adjust_learning_rate(
    algo_name: str,
    current_params: dict,
    current_score: float,
    new_learning_rate: float,
    data: dict[str, Any],
    settings: dict | None = None,
) -> dict[str, Any]:
    """Re-train with a new learning rate, scaling n_estimators proportionally.

    The agent decides the new learning rate (typically current - 0.05).
    n_estimators is scaled inversely: if rate halves, estimators double.

    Only applicable to boosting algorithms.

    Returns results plus a comparison against the previous score.
    """
    # Guard against non-boosting algorithms
    algo_info = ALGORITHM_REGISTRY[algo_name]
    if not algo_info.get("supports_boosting_phases", False):
        return {
            "error": f"adjust_learning_rate is only applicable to boosting "
                     f"algorithms. '{algo_name}' does not support boosting phases.",
            "algorithm": algo_name,
            "supported_algorithms": [
                name for name, info in ALGORITHM_REGISTRY.items()
                if info.get("supports_boosting_phases", False)
            ],
        }

    old_lr = current_params.get("learning_rate", 0.1)
    old_n = current_params.get("n_estimators", 500)

    scale_factor = old_lr / new_learning_rate
    new_n = int(old_n * scale_factor)

    new_params = current_params.copy()
    new_params["learning_rate"] = new_learning_rate
    new_params["n_estimators"] = new_n

    logger.info(
        "Adjusting learning rate: %.4f → %.4f | n_estimators: %d → %d",
        old_lr, new_learning_rate, old_n, new_n,
    )

    result = train_with_params(algo_name, new_params, data, settings)

    settings = settings or load_settings()
    primary_metric = settings["model"]["primary_metric"]

    result["learning_rate_adjustment"] = {
        "old_learning_rate": old_lr,
        "new_learning_rate": new_learning_rate,
        "old_n_estimators": old_n,
        "new_n_estimators": new_n,
        "scale_factor": scale_factor,
        "old_score": current_score,
        "new_score": result["test_scores"].get(primary_metric, 0),
        "improvement": result["test_scores"].get(primary_metric, 0) - current_score,
        "improved": result["test_scores"].get(primary_metric, 0) > current_score,
    }

    return result


# ── Feature importance and selection ───────────────────────────────────

def get_feature_importances(
    model,
    feature_names: list[str],
    algo_name: str,
) -> dict[str, Any]:
    """Extract feature importances from a fitted model.

    Works for both tree models (feature_importances_) and linear models
    (coef_). Returns a ranked list the agent can use to decide which
    features to drop.

    Returns:
        Dict with ranked_features (list of {name, importance, rank}),
        importance_type, and summary stats.
    """
    algo_info = ALGORITHM_REGISTRY.get(algo_name, {})
    encoding = algo_info.get("encoding", "unknown")

    if hasattr(model, "feature_importances_"):
        raw_importances = model.feature_importances_
        importance_type = "split_based"
    elif hasattr(model, "coef_"):
        raw_importances = np.abs(model.coef_[0])
        importance_type = "coefficient_magnitude"
    else:
        return {
            "error": f"Model type {type(model).__name__} does not expose "
                     f"feature importances or coefficients.",
            "algorithm": algo_name,
        }

    # Normalize to sum to 1 for easier comparison
    total = raw_importances.sum()
    if total > 0:
        normalized = raw_importances / total
    else:
        normalized = raw_importances

    # Build ranked list
    ranked = sorted(
        zip(feature_names, raw_importances.tolist(), normalized.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )

    ranked_features = []
    for rank, (name, raw, norm) in enumerate(ranked, 1):
        ranked_features.append({
            "rank": rank,
            "name": name,
            "importance_raw": raw,
            "importance_normalized": norm,
            "cumulative_importance": sum(r["importance_normalized"] for r in ranked_features) + norm,
        })

    # Summary for agent decision-making
    top_80_count = 0
    cumulative = 0.0
    for feat in ranked_features:
        cumulative += feat["importance_normalized"]
        top_80_count += 1
        if cumulative >= 0.80:
            break

    zero_importance = [f for f in ranked_features if f["importance_raw"] == 0]

    return {
        "algorithm": algo_name,
        "encoding": encoding,
        "importance_type": importance_type,
        "ranked_features": ranked_features,
        "n_features": len(feature_names),
        "top_80_pct_count": top_80_count,
        "zero_importance_features": [f["name"] for f in zero_importance],
        "n_zero_importance": len(zero_importance),
        "summary": (
            f"{top_80_count} of {len(feature_names)} features account for 80% "
            f"of importance. {len(zero_importance)} features have zero importance."
        ),
    }


def get_permutation_importances(
    model,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    feature_names: list[str],
    cat_cols: list[str],
    algo_name: str,
    scoring: str = "roc_auc",
    n_repeats: int = 20,
    removal_threshold: float = 0.005,
) -> dict[str, Any]:
    """Compute permutation importance on held-out data for feature removal decisions.

    Shuffles each original feature (pre-encoding) and measures performance drop.
    For onehot-encoded models, groups dummy columns so the full categorical
    feature is shuffled together — prevents impossible feature combinations.

    Use this to decide which features to drop. Features with near-zero or
    negative mean AUC drop (and small std) are safe candidates for removal.

    Args:
        model: Fitted model (already trained on encoded data).
        X_test: Test features (pre-encoding, with category dtypes).
        y_test: Test labels.
        feature_names: Original feature names (pre-encoding).
        cat_cols: Categorical column names.
        algo_name: Algorithm name for encoding lookup.
        scoring: Metric to evaluate (default roc_auc).
        n_repeats: Number of shuffles per feature (more = tighter std).
        removal_threshold: Features with mean_drop below this are safe to remove.

    Returns:
        Dict with ranked_features, safe_to_remove list, and summary for agent.
    """
    from sklearn.inspection import permutation_importance as sklearn_perm_imp

    algo_info = ALGORITHM_REGISTRY[algo_name]
    encoding = algo_info["encoding"]

    if encoding == "native":
        # For native encoding, sklearn permutation_importance works directly
        # because each column is already a meaningful original feature.
        # Note: sklearn runs n_features × n_repeats internally. We show a
        # simple progress note since sklearn doesn't support callbacks.
        logger.info(
            "Permutation importance (%s): %d features × %d repeats",
            algo_name, len(feature_names), n_repeats,
        )
        print(f"Computing permutation importance ({algo_name}): "
              f"{len(feature_names)} features × {n_repeats} repeats...")
        result = sklearn_perm_imp(
            model, X_test, y_test,
            scoring=scoring,
            n_repeats=n_repeats,
            random_state=42,
            n_jobs=-1,
        )

        ranked_data = sorted(
            zip(feature_names,
                result.importances_mean.tolist(),
                result.importances_std.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )

    elif encoding == "onehot":
        # For onehot encoding, we shuffle the ORIGINAL categorical column
        # before re-encoding, so all dummy columns derived from it move
        # together. This avoids creating impossible feature combinations
        # (e.g., region_A=1 and region_B=1 simultaneously).
        X_test_enc, _ = _encode_for_algorithm(
            X_test.copy(), X_test.copy(), encoding, cat_cols,
        )

        # Baseline score on properly encoded test data
        if scoring == "roc_auc":
            from sklearn.metrics import roc_auc_score
            y_prob = model.predict_proba(X_test_enc)[:, 1]
            baseline_score = roc_auc_score(y_test, y_prob)
        else:
            from sklearn.metrics import get_scorer
            scorer = get_scorer(scoring)
            baseline_score = scorer(model, X_test_enc, y_test)

        ranked_data = []
        rng = np.random.RandomState(42)
        feat_bar = tqdm(feature_names, desc=f"Permutation importance ({algo_name})", unit="feat")

        for feat in feat_bar:
            feat_bar.set_postfix(feature=feat)
            drops = []
            for r in range(n_repeats):
                X_shuffled = X_test.copy()
                # Shuffle this one feature's values across rows
                shuffled_values = X_shuffled[feat].values.copy()
                rng.shuffle(shuffled_values)
                X_shuffled[feat] = shuffled_values

                # Re-encode with the shuffled feature
                X_shuf_enc, _ = _encode_for_algorithm(
                    X_shuffled, X_shuffled, encoding, cat_cols,
                )
                # Align columns to match training encoding
                X_shuf_enc = X_shuf_enc.reindex(
                    columns=X_test_enc.columns, fill_value=0,
                )

                if scoring == "roc_auc":
                    y_prob_shuf = model.predict_proba(X_shuf_enc)[:, 1]
                    shuffled_score = roc_auc_score(y_test, y_prob_shuf)
                else:
                    shuffled_score = scorer(model, X_shuf_enc, y_test)

                drops.append(baseline_score - shuffled_score)

            ranked_data.append((feat, float(np.mean(drops)), float(np.std(drops))))

        ranked_data.sort(key=lambda x: x[1], reverse=True)

    else:
        raise ValueError(f"Unknown encoding: {encoding}")

    # Build structured output for agent
    ranked_features = []
    safe_to_remove = []

    for rank, (name, mean_drop, std_drop) in enumerate(ranked_data, 1):
        # Safe to remove: mean drop is negligible AND variance is low
        # (meaning the feature consistently doesn't matter, not just noisy)
        is_safe = (mean_drop <= removal_threshold) and (std_drop < removal_threshold * 2)
        entry = {
            "rank": rank,
            "name": name,
            "mean_auc_drop": round(mean_drop, 6),
            "std": round(std_drop, 6),
            "safe_to_remove": is_safe,
        }
        ranked_features.append(entry)
        if is_safe:
            safe_to_remove.append(name)

    return {
        "algorithm": algo_name,
        "encoding": encoding,
        "scoring": scoring,
        "n_repeats": n_repeats,
        "removal_threshold": removal_threshold,
        "ranked_features": ranked_features,
        "safe_to_remove": safe_to_remove,
        "n_safe_to_remove": len(safe_to_remove),
        "n_features": len(feature_names),
        "summary": (
            f"{len(safe_to_remove)} of {len(feature_names)} features are safe "
            f"to remove (mean AUC drop <= {removal_threshold} with low variance)."
        ),
    }


def train_with_feature_subset(
    algo_name: str,
    params: dict,
    data: dict[str, Any],
    keep_features: list[str],
    settings: dict | None = None,
) -> dict[str, Any]:
    """Re-train a model using only the specified feature subset.

    The agent calls this after reviewing get_feature_importances() to
    test whether dropping low-importance features improves performance.

    Args:
        keep_features: List of original feature names to retain.
                       For onehot-encoded models, pass the pre-encoding
                       column names — encoding is applied after subsetting.

    Returns:
        Same structure as train_with_params(), plus feature_selection
        metadata showing what was dropped.
    """
    settings = settings or load_settings()
    model_cfg = settings["model"]
    cv_folds = model_cfg["cv_folds"]
    metric_names = model_cfg["scoring_metrics"]
    primary_metric = model_cfg["primary_metric"]

    algo_info = ALGORITHM_REGISTRY[algo_name]
    encoding = algo_info["encoding"]
    cat_cols = data["categorical_features"]

    all_features = data["feature_names"]
    dropped_features = [f for f in all_features if f not in keep_features]

    # Subset to kept features only
    X_train_sub = data["X_train"][keep_features].copy()
    X_test_sub = data["X_test"][keep_features].copy()

    # Only encode categoricals that are still in the subset
    remaining_cat_cols = [c for c in cat_cols if c in keep_features]

    X_validation_sub = data["X_validation"][keep_features].copy()
    X_train, X_validation, X_test = _encode_for_algorithm(
        X_train_sub, X_test_sub, encoding, remaining_cat_cols, X_validation=X_validation_sub,
    )
    y_train, y_validation, y_test = data["y_train"], data["y_validation"], data["y_test"]
    true_prob_validation = data.get("true_prob_validation")
    true_prob_test = data.get("true_prob_test")

    scorers = resolve_scorers(metric_names)

    start = time.time()

    model = _build_model(algo_name, params)

    cv_results = cross_validate(
        model, X_train, y_train,
        cv=cv_folds, scoring=scorers, return_train_score=False,
    )

    cv_scores = {}
    cv_std = {}
    for metric in metric_names:
        key = f"test_{metric}"
        fold_scores = cv_results[key]
        cv_scores[metric] = float(np.mean(fold_scores))
        cv_std[metric] = float(np.std(fold_scores))

    training_history = _fit_model_and_capture_history(
        model, algo_name, X_train, y_train, X_validation, y_validation,
    )
    validation_result = evaluate_on_test(
        model, X_validation, y_validation, metric_names, true_prob_validation,
    )
    eval_result = evaluate_on_test(model, X_test, y_test, metric_names, true_prob_test)
    test_scores = eval_result["scores"]
    elapsed = time.time() - start

    return {
        "algorithm": algo_name,
        "cv_scores": cv_scores,
        "cv_std": cv_std,
        "cv_results_raw": {k: v.tolist() for k, v in cv_results.items()},
        "validation_scores": validation_result["scores"],
        "test_scores": test_scores,
        "y_pred": eval_result["y_pred"],
        "y_prob": eval_result["y_prob"],
        "model": model,
        "params_used": params,
        "feature_names": X_train.columns.tolist(),
        "training_history": training_history,
        "encoding": encoding,
        "elapsed_seconds": elapsed,
        "feature_selection": {
            "original_features": all_features,
            "kept_features": keep_features,
            "dropped_features": dropped_features,
            "n_original": len(all_features),
            "n_kept": len(keep_features),
            "n_dropped": len(dropped_features),
        },
    }
