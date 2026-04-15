"""Artifact generation for MLflow logging — dual output for agents and humans.

Every artifact function produces:
    - A structured dict (logged as .json) for LLM agents to read and reason over
    - A matplotlib figure (logged as .png) for human-in-the-loop review

This module has NO MLflow dependency. It returns dicts of {filename: content}
that the workflow layer logs via mlflow.log_artifact().
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for artifact generation

import matplotlib.pyplot as plt
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    RocCurveDisplay,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────

def _fig_to_png_bytes(fig: plt.Figure) -> bytes:
    """Convert a matplotlib figure to PNG bytes and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── 1. ROC Curve ──────────────────────────────────────────────────────

def roc_curve_artifact(
    y_test: np.ndarray,
    y_prob: np.ndarray,
) -> dict[str, Any]:
    """Generate ROC curve JSON (for agents) and PNG (for humans).

    JSON includes AUC, optimal threshold (Youden's J), and sampled
    curve points for agent analysis.
    """
    fpr, tpr, thresholds = roc_curve(y_test, y_prob)
    auc = float(roc_auc_score(y_test, y_prob))

    # Optimal threshold via Youden's J statistic
    j_scores = tpr - fpr
    optimal_idx = int(np.argmax(j_scores))
    optimal_threshold = float(thresholds[optimal_idx])

    # Downsample curve points for JSON (keep at most 200 points)
    n_points = len(fpr)
    if n_points > 200:
        indices = np.linspace(0, n_points - 1, 200, dtype=int)
    else:
        indices = np.arange(n_points)

    structured = {
        "artifact_type": "roc_curve",
        "auc": auc,
        "gini": 2 * auc - 1,
        "optimal_threshold": optimal_threshold,
        "sensitivity_at_optimal": float(tpr[optimal_idx]),
        "specificity_at_optimal": float(1 - fpr[optimal_idx]),
        "n_curve_points": int(len(indices)),
        "fpr": [float(fpr[i]) for i in indices],
        "tpr": [float(tpr[i]) for i in indices],
        "thresholds": [float(thresholds[i]) for i in indices],
        "summary": (
            f"AUC={auc:.4f}, Gini={2*auc-1:.4f}. "
            f"Optimal threshold={optimal_threshold:.3f} "
            f"(sensitivity={tpr[optimal_idx]:.3f}, specificity={1-fpr[optimal_idx]:.3f})."
        ),
    }

    # Visual
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(fpr, tpr, color="#2563eb", lw=2, label=f"ROC (AUC = {auc:.4f})")
    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="Random")
    ax.scatter(
        [fpr[optimal_idx]], [tpr[optimal_idx]],
        color="#dc2626", s=80, zorder=5,
        label=f"Optimal (t={optimal_threshold:.3f})",
    )
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(f"ROC Curve — AUC = {auc:.4f}")
    ax.legend(loc="lower right")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)

    return {
        "roc_curve.json": structured,
        "roc_curve.png": _fig_to_png_bytes(fig),
    }


# ── 2. Confusion Matrix ──────────────────────────────────────────────

def confusion_matrix_artifact(
    y_test: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    """Generate confusion matrix JSON and PNG."""
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel().tolist()
    total = tn + fp + fn + tp

    structured = {
        "artifact_type": "confusion_matrix",
        "threshold": 0.5,
        "matrix": cm.tolist(),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "total": total,
        "accuracy": (tp + tn) / total if total else 0,
        "precision": tp / (tp + fp) if (tp + fp) else 0,
        "recall": tp / (tp + fn) if (tp + fn) else 0,
        "f1": 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0,
        "false_positive_rate": fp / (fp + tn) if (fp + tn) else 0,
        "false_negative_rate": fn / (fn + tp) if (fn + tp) else 0,
        "summary": (
            f"TP={tp}, FP={fp}, FN={fn}, TN={tn} (total={total}). "
            f"Precision={tp/(tp+fp) if (tp+fp) else 0:.4f}, "
            f"Recall={tp/(tp+fn) if (tp+fn) else 0:.4f}."
        ),
    }

    # Visual
    fig, ax = plt.subplots(figsize=(6, 5))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["0", "1"])
    disp.plot(ax=ax, cmap="Blues", values_format="d")
    ax.set_title("Confusion Matrix (threshold=0.5)")

    return {
        "confusion_matrix.json": structured,
        "confusion_matrix.png": _fig_to_png_bytes(fig),
    }


# ── 3. Calibration Curve ─────────────────────────────────────────────

def calibration_artifact(
    y_test: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Generate calibration curve JSON and PNG.

    Critical for insurance pricing — predicted probabilities must
    match actual event frequencies.
    """
    fraction_pos, mean_predicted = calibration_curve(
        y_test, y_prob, n_bins=n_bins, strategy="uniform",
    )
    brier = float(brier_score_loss(y_test, y_prob))

    # Expected Calibration Error (ECE)
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_prob, bin_edges[1:-1])
    ece = 0.0
    bins_data = []
    for i in range(n_bins):
        mask = bin_indices == i
        count = int(mask.sum())
        if count == 0:
            continue
        bin_center = float((bin_edges[i] + bin_edges[i + 1]) / 2)
        avg_pred = float(y_prob[mask].mean())
        frac_pos = float(y_test[mask].mean())
        ece += count * abs(frac_pos - avg_pred)
        bins_data.append({
            "bin_center": round(bin_center, 4),
            "fraction_positive": round(frac_pos, 6),
            "avg_predicted": round(avg_pred, 6),
            "count": count,
            "abs_error": round(abs(frac_pos - avg_pred), 6),
        })
    ece = ece / len(y_test) if len(y_test) > 0 else 0.0

    structured = {
        "artifact_type": "calibration",
        "n_bins": n_bins,
        "brier_score": round(brier, 6),
        "expected_calibration_error": round(ece, 6),
        "bins": bins_data,
        "summary": (
            f"Brier score={brier:.4f}, ECE={ece:.4f}. "
            f"{'Well calibrated' if ece < 0.05 else 'Calibration could be improved'} "
            f"(ECE {'<' if ece < 0.05 else '>='} 0.05)."
        ),
    }

    # Visual — calibration curve + histogram
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 8), gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(mean_predicted, fraction_pos, "o-", color="#2563eb", lw=2, label="Model")
    ax1.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="Perfect calibration")
    ax1.set_xlabel("Mean Predicted Probability")
    ax1.set_ylabel("Fraction of Positives")
    ax1.set_title(f"Calibration Curve — Brier={brier:.4f}, ECE={ece:.4f}")
    ax1.legend(loc="lower right")
    ax1.set_xlim(-0.02, 1.02)
    ax1.set_ylim(-0.02, 1.02)
    ax1.grid(True, alpha=0.3)

    ax2.hist(y_prob, bins=50, color="#93c5fd", edgecolor="#2563eb", alpha=0.8)
    ax2.set_xlabel("Predicted Probability")
    ax2.set_ylabel("Count")
    ax2.set_title("Prediction Distribution")

    fig.tight_layout()

    return {
        "calibration.json": structured,
        "calibration.png": _fig_to_png_bytes(fig),
    }


# ── 4. Feature Importance ────────────────────────────────────────────

def feature_importance_artifact(
    model,
    feature_names: list[str],
    algo_name: str,
    top_n: int = 20,
) -> dict[str, Any]:
    """Generate feature importance JSON and PNG.

    Supports tree models (feature_importances_) and linear models (coef_).
    """
    if hasattr(model, "feature_importances_"):
        raw = model.feature_importances_
        importance_type = "split_based"
    elif hasattr(model, "coef_"):
        raw = np.abs(model.coef_[0])
        importance_type = "coefficient_magnitude"
    else:
        return {
            "feature_importance.json": {
                "artifact_type": "feature_importance",
                "error": f"Model {type(model).__name__} has no importance attributes.",
                "algorithm": algo_name,
            },
        }

    total = raw.sum()
    normalized = (raw / total) if total > 0 else raw

    # Ranked features
    ranked = sorted(
        zip(feature_names, raw.tolist(), normalized.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )

    features = []
    cumulative = 0.0
    for rank, (name, raw_val, norm_val) in enumerate(ranked, 1):
        cumulative += norm_val
        features.append({
            "rank": rank,
            "name": name,
            "importance_raw": round(raw_val, 6),
            "importance_normalized": round(norm_val, 6),
            "cumulative_importance": round(cumulative, 6),
        })

    # Summary stats
    top_80_count = next(
        (f["rank"] for f in features if f["cumulative_importance"] >= 0.80),
        len(features),
    )
    zero_features = [f["name"] for f in features if f["importance_raw"] == 0]

    structured = {
        "artifact_type": "feature_importance",
        "algorithm": algo_name,
        "importance_type": importance_type,
        "n_features": len(feature_names),
        "top_80_pct_count": top_80_count,
        "zero_importance_features": zero_features,
        "n_zero_importance": len(zero_features),
        "features": features,
        "summary": (
            f"{top_80_count} of {len(feature_names)} features account for 80% of importance. "
            f"{len(zero_features)} features have zero importance."
        ),
    }

    # Visual — horizontal bar chart of top N
    display_n = min(top_n, len(features))
    top_features = features[:display_n]
    names = [f["name"] for f in reversed(top_features)]
    importances = [f["importance_normalized"] for f in reversed(top_features)]

    fig, ax = plt.subplots(figsize=(8, max(4, display_n * 0.35)))
    bars = ax.barh(names, importances, color="#2563eb", edgecolor="#1d4ed8")
    ax.set_xlabel("Normalized Importance")
    ax.set_title(f"Feature Importance — {algo_name} ({importance_type})")
    ax.grid(True, axis="x", alpha=0.3)

    # Annotate bars
    for bar, imp in zip(bars, importances):
        ax.text(
            bar.get_width() + 0.002, bar.get_y() + bar.get_height() / 2,
            f"{imp:.3f}", va="center", fontsize=8,
        )

    fig.tight_layout()

    return {
        "feature_importance.json": structured,
        "feature_importance.png": _fig_to_png_bytes(fig),
    }


# ── 5. Probability Distribution ──────────────────────────────────────

def probability_distribution_artifact(
    y_test: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 50,
) -> dict[str, Any]:
    """Generate predicted probability distribution JSON and PNG.

    Shows how well the model separates classes. Includes KS statistic.
    """
    from scipy.stats import ks_2samp

    prob_class_0 = y_prob[y_test == 0]
    prob_class_1 = y_prob[y_test == 1]

    ks_stat, ks_pvalue = ks_2samp(prob_class_0, prob_class_1)

    # Histogram bins for JSON
    bin_edges = np.linspace(0, 1, n_bins + 1)
    hist_0, _ = np.histogram(prob_class_0, bins=bin_edges)
    hist_1, _ = np.histogram(prob_class_1, bins=bin_edges)

    histogram = []
    for i in range(n_bins):
        histogram.append({
            "bin_start": round(float(bin_edges[i]), 4),
            "bin_end": round(float(bin_edges[i + 1]), 4),
            "count_class_0": int(hist_0[i]),
            "count_class_1": int(hist_1[i]),
        })

    structured = {
        "artifact_type": "probability_distribution",
        "class_0": {
            "n": int(len(prob_class_0)),
            "mean": round(float(prob_class_0.mean()), 6),
            "median": round(float(np.median(prob_class_0)), 6),
            "std": round(float(prob_class_0.std()), 6),
            "min": round(float(prob_class_0.min()), 6),
            "max": round(float(prob_class_0.max()), 6),
        },
        "class_1": {
            "n": int(len(prob_class_1)),
            "mean": round(float(prob_class_1.mean()), 6),
            "median": round(float(np.median(prob_class_1)), 6),
            "std": round(float(prob_class_1.std()), 6),
            "min": round(float(prob_class_1.min()), 6),
            "max": round(float(prob_class_1.max()), 6),
        },
        "ks_statistic": round(float(ks_stat), 6),
        "ks_pvalue": float(ks_pvalue),
        "histogram": histogram,
        "summary": (
            f"Class separation: KS={ks_stat:.4f} (p={ks_pvalue:.2e}). "
            f"Class 0 mean prob={prob_class_0.mean():.4f}, "
            f"Class 1 mean prob={prob_class_1.mean():.4f}."
        ),
    }

    # Visual
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(prob_class_0, bins=bin_edges, alpha=0.6, color="#3b82f6", label="Class 0", edgecolor="#1d4ed8")
    ax.hist(prob_class_1, bins=bin_edges, alpha=0.6, color="#ef4444", label="Class 1", edgecolor="#b91c1c")
    ax.set_xlabel("Predicted Probability")
    ax.set_ylabel("Count")
    ax.set_title(f"Probability Distribution by Class — KS={ks_stat:.4f}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    return {
        "probability_distribution.json": structured,
        "probability_distribution.png": _fig_to_png_bytes(fig),
    }


# ── 6. Classification Report ─────────────────────────────────────────

def classification_report_artifact(
    y_test: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    """Generate classification report JSON (no visual — JSON is human-readable)."""
    report = classification_report(y_test, y_pred, output_dict=True)

    structured = {
        "artifact_type": "classification_report",
        "threshold": 0.5,
        "classes": {
            "0": report.get("0", report.get("0.0", {})),
            "1": report.get("1", report.get("1.0", {})),
        },
        "macro_avg": report.get("macro avg", {}),
        "weighted_avg": report.get("weighted avg", {}),
        "accuracy": report.get("accuracy", 0),
        "summary": (
            f"Accuracy={report.get('accuracy', 0):.4f}. "
            f"Class 1: precision={report.get('1', report.get('1.0', {})).get('precision', 0):.4f}, "
            f"recall={report.get('1', report.get('1.0', {})).get('recall', 0):.4f}, "
            f"f1={report.get('1', report.get('1.0', {})).get('f1-score', 0):.4f}."
        ),
    }

    return {
        "classification_report.json": structured,
    }


# ── 7. Ground Truth Comparison (conditional) ─────────────────────────

def ground_truth_artifact(
    y_prob: np.ndarray,
    true_prob: np.ndarray,
) -> dict[str, Any]:
    """Generate ground truth comparison JSON and PNG.

    Only applicable when has_ground_truth=True (deterministic DGP mode).
    Compares predicted probabilities to the known true probabilities.
    """
    errors = y_prob - true_prob
    abs_errors = np.abs(errors)

    mse = float(np.mean(errors ** 2))
    mae = float(np.mean(abs_errors))
    correlation = float(np.corrcoef(y_prob, true_prob)[0, 1])

    # Binned analysis for agent reasoning
    n_bins = 10
    bin_edges = np.linspace(float(true_prob.min()), float(true_prob.max()), n_bins + 1)
    bin_indices = np.digitize(true_prob, bin_edges[1:-1])

    bins_data = []
    for i in range(n_bins):
        mask = bin_indices == i
        count = int(mask.sum())
        if count == 0:
            continue
        bins_data.append({
            "true_prob_range": f"[{bin_edges[i]:.3f}, {bin_edges[i+1]:.3f})",
            "mean_predicted": round(float(y_prob[mask].mean()), 6),
            "mean_true": round(float(true_prob[mask].mean()), 6),
            "mean_error": round(float(errors[mask].mean()), 6),
            "mean_abs_error": round(float(abs_errors[mask].mean()), 6),
            "count": count,
        })

    structured = {
        "artifact_type": "ground_truth_comparison",
        "mse": round(mse, 8),
        "mae": round(mae, 6),
        "rmse": round(float(np.sqrt(mse)), 6),
        "correlation": round(correlation, 6),
        "max_abs_error": round(float(abs_errors.max()), 6),
        "percentile_errors": {
            "p50": round(float(np.percentile(abs_errors, 50)), 6),
            "p90": round(float(np.percentile(abs_errors, 90)), 6),
            "p95": round(float(np.percentile(abs_errors, 95)), 6),
            "p99": round(float(np.percentile(abs_errors, 99)), 6),
        },
        "n_samples": int(len(y_prob)),
        "bins": bins_data,
        "summary": (
            f"MSE={mse:.6f}, MAE={mae:.4f}, correlation={correlation:.4f}. "
            f"P90 error={np.percentile(abs_errors, 90):.4f}, "
            f"P99 error={np.percentile(abs_errors, 99):.4f}."
        ),
    }

    # Visual — hexbin scatter for density at scale
    fig, ax = plt.subplots(figsize=(7, 6))

    if len(y_prob) > 5000:
        hb = ax.hexbin(true_prob, y_prob, gridsize=40, cmap="Blues", mincnt=1)
        fig.colorbar(hb, ax=ax, label="Count")
    else:
        ax.scatter(true_prob, y_prob, alpha=0.3, s=8, color="#2563eb")

    ax.plot([0, 1], [0, 1], "r--", lw=1.5, label="Perfect")
    ax.set_xlabel("True Probability (Ground Truth)")
    ax.set_ylabel("Predicted Probability")
    ax.set_title(f"Predicted vs. True — MSE={mse:.6f}, r={correlation:.4f}")
    ax.legend(loc="lower right")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)

    return {
        "ground_truth.json": structured,
        "ground_truth.png": _fig_to_png_bytes(fig),
    }


# ── Orchestrator ─────────────────────────────────────────────────────

def generate_run_artifacts(
    model,
    y_test: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
    feature_names: list[str],
    algo_name: str,
    true_prob_test: np.ndarray | None = None,
) -> dict[str, Any]:
    """Generate all applicable artifacts for a single model run.

    Returns a dict of {filename: content} where content is either
    a dict (for .json files) or bytes (for .png files).

    The workflow layer iterates this dict and logs each to MLflow.
    """
    artifacts: dict[str, Any] = {}

    y_test_arr = np.asarray(y_test)
    y_pred_arr = np.asarray(y_pred)
    y_prob_arr = np.asarray(y_prob)

    # 1. ROC Curve
    try:
        artifacts.update(roc_curve_artifact(y_test_arr, y_prob_arr))
    except Exception as e:
        logger.warning("Failed to generate ROC curve artifact: %s", e)

    # 2. Confusion Matrix
    try:
        artifacts.update(confusion_matrix_artifact(y_test_arr, y_pred_arr))
    except Exception as e:
        logger.warning("Failed to generate confusion matrix artifact: %s", e)

    # 3. Calibration Curve
    try:
        artifacts.update(calibration_artifact(y_test_arr, y_prob_arr))
    except Exception as e:
        logger.warning("Failed to generate calibration artifact: %s", e)

    # 4. Feature Importance
    try:
        artifacts.update(feature_importance_artifact(model, feature_names, algo_name))
    except Exception as e:
        logger.warning("Failed to generate feature importance artifact: %s", e)

    # 5. Probability Distribution
    try:
        artifacts.update(probability_distribution_artifact(y_test_arr, y_prob_arr))
    except Exception as e:
        logger.warning("Failed to generate probability distribution artifact: %s", e)

    # 6. Classification Report
    try:
        artifacts.update(classification_report_artifact(y_test_arr, y_pred_arr))
    except Exception as e:
        logger.warning("Failed to generate classification report artifact: %s", e)

    # 7. Ground Truth Comparison (only when available)
    if true_prob_test is not None:
        try:
            true_prob_arr = np.asarray(true_prob_test)
            artifacts.update(ground_truth_artifact(y_prob_arr, true_prob_arr))
        except Exception as e:
            logger.warning("Failed to generate ground truth artifact: %s", e)

    return artifacts

