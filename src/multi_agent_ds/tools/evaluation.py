"""Custom scoring metrics, scorer registry, and test-set evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    make_scorer,
    precision_score,
    recall_score,
    roc_auc_score,
)


# ── Custom metric functions ────────────────────────────────────────────

def average_squared_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    sample_weight: np.ndarray | None = None,
) -> float:
    """Average Squared Error (ASE).

    When sample_weight is None, uniform weights are used.
    Handles both 1-D probability vectors and 2-D predict_proba output.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    # Handle 2D predict_proba output — use column 1 (positive class)
    if y_pred.ndim == 2:
        y_pred = y_pred[:, 1]

    if sample_weight is None:
        sample_weight = np.ones_like(y_true)
    else:
        sample_weight = np.asarray(sample_weight, dtype=np.float64)

    y_bar = np.sum(sample_weight * y_true) / np.sum(sample_weight)

    result = (100 / y_bar) ** 2 * (
        np.sum(sample_weight * (y_true - y_pred) ** 2) / np.sum(sample_weight)
        - np.sum(sample_weight * (y_true - y_bar) ** 2) / np.sum(sample_weight)
    )
    return result


def gini_coefficient(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Gini coefficient: 2 * AUC - 1.

    Handles both 1-D probability vectors and 2-D predict_proba output.
    """
    y_prob = np.asarray(y_prob)
    if y_prob.ndim == 2:
        y_prob = y_prob[:, 1]
    auc = roc_auc_score(y_true, y_prob)
    return 2 * auc - 1


# ── Sklearn-compatible scorers ─────────────────────────────────────────

ase_scorer = make_scorer(
    average_squared_error,
    greater_is_better=False,
    response_method="predict_proba",
)

gini_scorer = make_scorer(
    gini_coefficient,
    greater_is_better=True,
    response_method="predict_proba",
)

CUSTOM_SCORERS = {
    "ase": ase_scorer,
    "gini": gini_scorer,
}


def resolve_scorers(metric_names: list[str]) -> dict[str, Any]:
    """Map metric names from config to sklearn scorer objects.

    Checks CUSTOM_SCORERS first, falls back to sklearn string names.
    """
    scorers = {}
    for name in metric_names:
        if name in CUSTOM_SCORERS:
            scorers[name] = CUSTOM_SCORERS[name]
        else:
            scorers[name] = name
    return scorers


def evaluate_on_test(
    model,
    X_test,
    y_test,
    metric_names: list[str],
    true_prob_test=None,
) -> dict[str, Any]:
    """Score a fitted model on a held-out test set.

    Returns a dict with:
        - scores: dict of metric_name -> float
        - y_pred: np.ndarray of class predictions
        - y_prob: np.ndarray of positive-class probabilities

    If true_prob_test is provided (deterministic DGP mode),
    scores also includes mse_vs_ground_truth.
    """
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    builtin = {
        "roc_auc": lambda: roc_auc_score(y_test, y_prob),
        "f1": lambda: f1_score(y_test, y_pred),
        "precision": lambda: precision_score(y_test, y_pred),
        "recall": lambda: recall_score(y_test, y_pred),
        "accuracy": lambda: accuracy_score(y_test, y_pred),
        "gini": lambda: gini_coefficient(y_test, y_prob),
        "ase": lambda: average_squared_error(y_test, y_prob),
    }

    scores = {}
    for name in metric_names:
        if name in builtin:
            scores[name] = builtin[name]()

    if true_prob_test is not None:
        scores["mse_vs_ground_truth"] = float(
            np.mean((y_prob - true_prob_test.values) ** 2)
        )

    return {
        "scores": scores,
        "y_pred": y_pred,
        "y_prob": y_prob,
    }
