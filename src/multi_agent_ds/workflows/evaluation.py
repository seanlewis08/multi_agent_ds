"""Post-training evaluation workflow.

This workflow turns modeling outputs into a compact evaluation summary that is:
- safe to place into orchestration state
- compatible with the reviewer agent's prompt input needs
- ready for later MLflow logging without reshaping the payload

The initial implementation slice focuses on:
- ranking algorithms by the configured primary metric
- identifying winner and runner-up
- summarizing ground-truth comparison when true probabilities are available
- returning a stable contract for later SHAP and artifact expansion
"""

from __future__ import annotations

import importlib
import io
from typing import Any

import numpy as np


_DESCENDING_METRICS = {
    "gini",
    "roc_auc",
    "f1",
    "precision",
    "recall",
    "accuracy",
}
_ASCENDING_METRICS = {
    "ase",
    "mse_vs_ground_truth",
}


def _metric_direction(metric_name: str) -> str:
    """Return whether higher or lower values are better for a metric."""
    if metric_name in _ASCENDING_METRICS:
        return "asc"
    return "desc"


def _sort_value(metric_name: str, value: float) -> float:
    """Return a sortable value where smaller is always better."""
    if _metric_direction(metric_name) == "asc":
        return value
    return -value


def _extract_primary_rankings(
    results: dict[str, dict[str, Any]],
    primary_metric: str,
) -> tuple[list[dict[str, Any]], str, str | None, dict[str, Any]]:
    """Rank algorithms by the configured primary metric."""
    ranked: list[dict[str, Any]] = []
    missing_algorithms: list[str] = []

    for algorithm, result in results.items():
        test_scores = result.get("test_scores", {})
        validation_scores = result.get("validation_scores", {})
        if primary_metric not in test_scores:
            missing_algorithms.append(algorithm)
            continue

        ranked.append(
            {
                "algorithm": algorithm,
                "phase": result.get("phase"),
                "primary_metric": primary_metric,
                "primary_metric_value": float(test_scores[primary_metric]),
                "test_scores": test_scores,
                "validation_scores": validation_scores,
                "elapsed_seconds": result.get("elapsed_seconds"),
            }
        )

    if missing_algorithms:
        missing_text = ", ".join(sorted(missing_algorithms))
        raise ValueError(
            f"Primary metric '{primary_metric}' missing from test_scores for: {missing_text}"
        )

    if not ranked:
        raise ValueError("No algorithm results were available for evaluation")

    ranked.sort(
        key=lambda item: (
            _sort_value(primary_metric, item["primary_metric_value"]),
            _sort_value(
                primary_metric,
                float(item["validation_scores"].get(primary_metric, item["primary_metric_value"])),
            ),
            item["algorithm"],
        )
    )

    for index, item in enumerate(ranked, start=1):
        item["rank"] = index

    winner = ranked[0]["algorithm"]
    runner_up = ranked[1]["algorithm"] if len(ranked) > 1 else None
    tie_break = {
        "used": False,
        "reason": None,
    }
    if len(ranked) > 1:
        winner_entry = ranked[0]
        runner_up_entry = ranked[1]
        if winner_entry["primary_metric_value"] == runner_up_entry["primary_metric_value"]:
            winner_validation = float(
                winner_entry["validation_scores"].get(primary_metric, winner_entry["primary_metric_value"])
            )
            runner_validation = float(
                runner_up_entry["validation_scores"].get(primary_metric, runner_up_entry["primary_metric_value"])
            )
            tie_break["used"] = True
            if winner_validation != runner_validation:
                tie_break["reason"] = f"validation_scores.{primary_metric}"
            else:
                tie_break["reason"] = "algorithm_name"
    return ranked, winner, runner_up, tie_break


def _build_metric_rankings(results: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build per-metric rankings using test scores currently present in results."""
    metric_names = sorted(
        {
            metric_name
            for result in results.values()
            for metric_name in result.get("test_scores", {}).keys()
        }
    )

    metric_rankings: dict[str, list[dict[str, Any]]] = {}
    for metric_name in metric_names:
        ranked: list[dict[str, Any]] = []
        for algorithm, result in results.items():
            test_scores = result.get("test_scores", {})
            if metric_name not in test_scores:
                continue
            ranked.append(
                {
                    "algorithm": algorithm,
                    "metric": metric_name,
                    "value": float(test_scores[metric_name]),
                }
            )

        ranked.sort(
            key=lambda item: (
                _sort_value(metric_name, item["value"]),
                item["algorithm"],
            )
        )
        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
        metric_rankings[metric_name] = ranked

    return metric_rankings


def _build_ground_truth_comparison(
    results: dict[str, dict[str, Any]],
    ranked_algorithms: list[dict[str, Any]],
    data: dict[str, Any],
) -> dict[str, Any]:
    """Summarize closeness to deterministic ground truth when available."""
    if data.get("true_prob_test") is None:
        return {
            "available": False,
            "reason": "true_prob_test not provided",
            "rankings": [],
        }

    true_prob = np.asarray(data["true_prob_test"], dtype=float)
    algorithm_summaries: list[dict[str, Any]] = []
    for item in ranked_algorithms:
        algorithm = item["algorithm"]
        y_prob = results[algorithm].get("y_prob")
        if y_prob is None:
            continue
        predicted_prob = np.asarray(y_prob, dtype=float)
        if predicted_prob.shape[0] != true_prob.shape[0]:
            raise ValueError(
                f"Ground truth comparison length mismatch for {algorithm}: "
                f"y_prob has {predicted_prob.shape[0]} rows while true_prob_test has {true_prob.shape[0]}"
            )

        errors = predicted_prob - true_prob
        mse_value = float(np.mean(errors**2))
        mae_value = float(np.mean(np.abs(errors)))
        rmse_value = float(np.sqrt(mse_value))
        correlation_value = float(np.corrcoef(predicted_prob, true_prob)[0, 1])
        algorithm_summaries.append(
            {
                "algorithm": algorithm,
                "mse_vs_ground_truth": mse_value,
                "mae_vs_ground_truth": mae_value,
                "rmse_vs_ground_truth": rmse_value,
                "correlation_to_ground_truth": correlation_value,
            }
        )

    comparison_rankings = sorted(
        algorithm_summaries,
        key=lambda item: (item["mse_vs_ground_truth"], item["algorithm"]),
    )
    for index, item in enumerate(comparison_rankings, start=1):
        item["rank"] = index

    ranked_lookup = {item["algorithm"]: item for item in comparison_rankings}
    ordered_algorithms = [ranked_lookup[item["algorithm"]] for item in ranked_algorithms if item["algorithm"] in ranked_lookup]

    return {
        "available": True,
        "ranking_metric": "mse_vs_ground_truth",
        "algorithms": ordered_algorithms,
        "rankings": comparison_rankings,
        "expectation_checks": {
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
        },
    }


def _build_reviewer_summary(
    ranked_algorithms: list[dict[str, Any]],
    winner: str,
    runner_up: str | None,
    primary_metric: str,
    ground_truth_comparison: dict[str, Any],
    tie_break: dict[str, Any],
    model_selection_summary: dict[str, Any],
) -> dict[str, Any]:
    """Return a prompt-safe summary for the reviewer agent."""
    return {
        "winner": winner,
        "runner_up": runner_up,
        "primary_metric": primary_metric,
        "winner_score": model_selection_summary["winner"]["primary_metric_value"],
        "runner_up_score": model_selection_summary["runner_up"]["primary_metric_value"]
        if model_selection_summary["runner_up"] is not None
        else None,
        "reasoning": model_selection_summary["winner"]["reasoning"],
        "trade_off_summary": model_selection_summary["trade_off_summary"],
        "what_was_tested": model_selection_summary["what_was_tested"],
        "key_results": model_selection_summary["key_results"],
        "caveats": model_selection_summary["caveats"],
    }


def _build_model_selection_summary(
    ranked_algorithms: list[dict[str, Any]],
    winner: str,
    runner_up: str | None,
    primary_metric: str,
    ground_truth_comparison: dict[str, Any],
    tie_break: dict[str, Any],
    shap_results: dict[str, Any],
) -> dict[str, Any]:
    """Build a structured winner / trade-off summary for downstream agents."""
    winner_entry = ranked_algorithms[0]
    runner_up_entry = ranked_algorithms[1] if len(ranked_algorithms) > 1 else None

    caveats: list[str] = []
    if not ground_truth_comparison.get("available", False):
        caveats.append("ground truth comparison unavailable")
    if tie_break.get("used"):
        caveats.append(f"winner selected using tie-break: {tie_break['reason']}")
    if not shap_results.get("available", False):
        caveats.append("shap summary unavailable")

    what_was_tested = {
        "algorithms": [item["algorithm"] for item in ranked_algorithms],
        "primary_metric": primary_metric,
        "used_ground_truth": bool(ground_truth_comparison.get("available", False)),
        "used_shap": bool(shap_results.get("available", False)),
    }

    if runner_up_entry is not None:
        reasoning = (
            f"{winner} ranked first on {primary_metric} at "
            f"{winner_entry['primary_metric_value']:.4f}, ahead of {runner_up} at "
            f"{runner_up_entry['primary_metric_value']:.4f}."
        )
        trade_off_summary = {
            "runner_up": runner_up,
            "primary_metric_gap": float(
                winner_entry["primary_metric_value"] - runner_up_entry["primary_metric_value"]
            ),
            "summary": (
                f"{runner_up} was the runner-up with {primary_metric} "
                f"{runner_up_entry['primary_metric_value']:.4f}."
            ),
        }
    else:
        reasoning = (
            f"{winner} is the only evaluated algorithm and ranked first on "
            f"{primary_metric} at {winner_entry['primary_metric_value']:.4f}."
        )
        trade_off_summary = {
            "runner_up": None,
            "primary_metric_gap": None,
            "summary": "No runner-up was available for trade-off comparison.",
        }

    key_results: list[str] = [
        f"{winner} ranked first on {primary_metric} ({winner_entry['primary_metric_value']:.4f})."
    ]
    if runner_up_entry is not None:
        key_results.append(
            f"{runner_up} ranked second on {primary_metric} ({runner_up_entry['primary_metric_value']:.4f})."
        )
    if ground_truth_comparison.get("available") and ground_truth_comparison.get("rankings"):
        best_ground_truth = ground_truth_comparison["rankings"][0]
        key_results.append(
            f"{best_ground_truth['algorithm']} was closest to ground truth by "
            f"mse_vs_ground_truth ({best_ground_truth['mse_vs_ground_truth']:.6f})."
        )
    if shap_results.get("available") and shap_results.get("top_features"):
        top_names = ", ".join(feature["feature"] for feature in shap_results["top_features"][:3])
        key_results.append(
            f"Top SHAP features for {winner}: {top_names}."
        )

    return {
        "winner": {
            "algorithm": winner,
            "primary_metric": primary_metric,
            "primary_metric_value": winner_entry["primary_metric_value"],
            "test_scores": winner_entry["test_scores"],
            "validation_scores": winner_entry["validation_scores"],
            "reasoning": reasoning,
        },
        "runner_up": {
            "algorithm": runner_up,
            "primary_metric": primary_metric,
            "primary_metric_value": runner_up_entry["primary_metric_value"],
            "test_scores": runner_up_entry["test_scores"],
            "validation_scores": runner_up_entry["validation_scores"],
        }
        if runner_up_entry is not None
        else None,
        "trade_off_summary": trade_off_summary,
        "what_was_tested": what_was_tested,
        "key_results": key_results,
        "caveats": caveats,
    }


def _build_algorithm_summaries(
    rankings: list[dict[str, Any]],
    ground_truth_comparison: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build state-safe per-algorithm metadata without raw model objects."""
    ground_truth_lookup = {
        item["algorithm"]: item
        for item in ground_truth_comparison.get("rankings", [])
    }
    summaries: list[dict[str, Any]] = []
    for item in rankings:
        ground_truth_metrics = ground_truth_lookup.get(item["algorithm"])
        summaries.append(
            {
                "algorithm": item["algorithm"],
                "rank": item["rank"],
                "phase": item["phase"],
                "elapsed_seconds": item["elapsed_seconds"],
                "primary_metric": item["primary_metric"],
                "primary_metric_value": item["primary_metric_value"],
                "test_scores": item["test_scores"],
                "validation_scores": item["validation_scores"],
                "ground_truth_metrics": {
                    "mse_vs_ground_truth": ground_truth_metrics["mse_vs_ground_truth"],
                    "mae_vs_ground_truth": ground_truth_metrics["mae_vs_ground_truth"],
                    "rmse_vs_ground_truth": ground_truth_metrics["rmse_vs_ground_truth"],
                    "correlation_to_ground_truth": ground_truth_metrics["correlation_to_ground_truth"],
                    "rank": ground_truth_metrics["rank"],
                }
                if ground_truth_metrics is not None
                else None,
            }
        )
    return summaries


def _load_shap_module() -> Any:
    """Import shap lazily so tests can stub it cleanly."""
    return importlib.import_module("shap")


def _load_pyplot() -> Any:
    """Import matplotlib.pyplot with a non-interactive backend."""
    matplotlib = importlib.import_module("matplotlib")
    matplotlib.use("Agg")
    return importlib.import_module("matplotlib.pyplot")


def _select_shap_target(
    results: dict[str, dict[str, Any]],
    winner: str,
    data: dict[str, Any],
) -> tuple[dict[str, Any], Any, Any, list[str]]:
    """Select the winning model and aligned feature matrix for SHAP."""
    winner_result = results.get(winner)
    if winner_result is None:
        raise ValueError(f"Winner '{winner}' missing from results")

    model = winner_result.get("model")
    if model is None:
        raise ValueError(f"Winner '{winner}' has no fitted model for SHAP")

    X_test = data.get("X_test")
    if X_test is None:
        raise ValueError("X_test not provided for SHAP evaluation")

    feature_names = winner_result.get("feature_names") or data.get("feature_names")
    if feature_names is None:
        raise ValueError(f"Feature names unavailable for SHAP target '{winner}'")

    return winner_result, model, X_test, list(feature_names)


def _make_shap_explainer(shap_module: Any, algorithm: str, model: Any, X_test: Any) -> Any:
    """Create the algorithm-appropriate SHAP explainer."""
    if algorithm == "lightgbm":
        return shap_module.TreeExplainer(model)
    if algorithm == "logistic_regression":
        return shap_module.LinearExplainer(model, X_test)
    return shap_module.Explainer(model, X_test)


def _normalize_shap_values(raw_shap_values: Any) -> np.ndarray:
    """Normalize common SHAP return types into a 2D rows-by-features array."""
    explanation_like = hasattr(raw_shap_values, "values")
    if explanation_like:
        raw_shap_values = raw_shap_values.values

    if isinstance(raw_shap_values, list) and not explanation_like:
        if not raw_shap_values:
            raise ValueError("Received empty SHAP values list")
        raw_shap_values = raw_shap_values[-1]

    values = np.asarray(raw_shap_values, dtype=float)

    if values.ndim == 3:
        values = values[:, :, -1]
    if values.ndim == 1:
        values = values.reshape(-1, 1)
    if values.ndim != 2:
        raise ValueError(f"Unsupported SHAP output shape: {values.shape}")

    return values


def _compute_shap_analysis(
    results: dict[str, dict[str, Any]],
    winner: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Compute SHAP analysis for the winning model when possible."""
    try:
        winner_result, model, X_test, feature_names = _select_shap_target(results, winner, data)
        shap_module = _load_shap_module()
        explainer = _make_shap_explainer(shap_module, winner, model, X_test)
        if hasattr(explainer, "shap_values"):
            raw_shap_values = explainer.shap_values(X_test)
        else:
            raw_shap_values = explainer(X_test)

        normalized_values = _normalize_shap_values(raw_shap_values)
        if normalized_values.shape[1] != len(feature_names):
            raise ValueError(
                f"SHAP feature alignment mismatch: values have {normalized_values.shape[1]} "
                f"columns but feature_names has {len(feature_names)} entries"
            )

        mean_abs_values = np.mean(np.abs(normalized_values), axis=0)
        mean_signed_values = np.mean(normalized_values, axis=0)
        ranked_features = sorted(
            (
                {
                    "feature": feature_name,
                    "mean_abs_shap": float(mean_abs_value),
                    "mean_signed_shap": float(mean_signed_value),
                    "direction": (
                        "positive"
                        if mean_signed_value > 0
                        else "negative"
                        if mean_signed_value < 0
                        else "neutral"
                    ),
                }
                for feature_name, mean_abs_value, mean_signed_value in zip(
                    feature_names,
                    mean_abs_values,
                    mean_signed_values,
                )
            ),
            key=lambda item: (-item["mean_abs_shap"], item["feature"]),
        )

        top_features = ranked_features[:5]
        return {
            "available": True,
            "target_algorithm": winner,
            "explainer_type": type(explainer).__name__,
            "n_rows": int(normalized_values.shape[0]),
            "n_features": int(normalized_values.shape[1]),
            "feature_ranking": ranked_features,
            "top_features": top_features,
            "directional_summary": top_features,
            "encoding": winner_result.get("encoding"),
            "feature_names": feature_names,
            "normalized_values": normalized_values,
        }
    except Exception as exc:
        return {
            "available": False,
            "reason": f"shap_unavailable: {exc}",
        }


def _build_shap_results(shap_analysis: dict[str, Any]) -> dict[str, Any]:
    """Convert SHAP analysis into the public state-friendly summary."""
    if not shap_analysis.get("available"):
        return {
            "available": False,
            "reason": shap_analysis["reason"],
        }

    return {
        "available": True,
        "target_algorithm": shap_analysis["target_algorithm"],
        "explainer_type": shap_analysis["explainer_type"],
        "n_rows": shap_analysis["n_rows"],
        "n_features": shap_analysis["n_features"],
        "feature_ranking": shap_analysis["feature_ranking"],
        "top_features": shap_analysis["top_features"],
        "directional_summary": shap_analysis["directional_summary"],
        "encoding": shap_analysis["encoding"],
    }


def _fig_to_png_bytes(fig: Any) -> bytes:
    """Serialize a matplotlib figure to PNG bytes."""
    plt = _load_pyplot()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()


def _build_beeswarm_png(shap_analysis: dict[str, Any]) -> bytes:
    """Build a simple SHAP beeswarm-style scatter plot as PNG bytes."""
    plt = _load_pyplot()
    normalized_values = np.asarray(shap_analysis["normalized_values"], dtype=float)
    top_features = shap_analysis["top_features"]
    feature_names = [feature["feature"] for feature in top_features]
    feature_indices = [shap_analysis["feature_names"].index(name) for name in feature_names]

    fig, ax = plt.subplots(figsize=(8, max(4, len(feature_names) * 0.5)))
    for y_index, feature_index in enumerate(reversed(feature_indices)):
        values = normalized_values[:, feature_index]
        y_values = np.full(values.shape[0], y_index, dtype=float)
        ax.scatter(values, y_values, alpha=0.7, s=20)

    ax.axvline(0.0, color="black", linewidth=1, alpha=0.5)
    ax.set_yticks(range(len(feature_names)))
    ax.set_yticklabels(list(reversed(feature_names)))
    ax.set_xlabel("SHAP value")
    ax.set_title(f"SHAP Beeswarm — {shap_analysis['target_algorithm']}")
    ax.grid(True, axis="x", alpha=0.2)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _build_waterfall_png(shap_analysis: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """Build a simple SHAP waterfall-style plot for one representative row."""
    plt = _load_pyplot()
    normalized_values = np.asarray(shap_analysis["normalized_values"], dtype=float)
    total_abs = np.sum(np.abs(normalized_values), axis=1)
    representative_row = int(np.argmax(total_abs))
    row_values = normalized_values[representative_row]

    ranked_row = sorted(
        zip(shap_analysis["feature_names"], row_values.tolist()),
        key=lambda item: (-abs(item[1]), item[0]),
    )[:5]

    names = [item[0] for item in reversed(ranked_row)]
    values = [item[1] for item in reversed(ranked_row)]
    colors = ["#16a34a" if value >= 0 else "#dc2626" for value in values]

    fig, ax = plt.subplots(figsize=(8, max(4, len(names) * 0.5)))
    ax.barh(names, values, color=colors)
    ax.axvline(0.0, color="black", linewidth=1, alpha=0.5)
    ax.set_xlabel("SHAP contribution")
    ax.set_title(
        f"SHAP Waterfall — {shap_analysis['target_algorithm']} row {representative_row}"
    )
    ax.grid(True, axis="x", alpha=0.2)
    fig.tight_layout()
    return _fig_to_png_bytes(fig), {
        "representative_row": representative_row,
        "selection_strategy": "largest_total_abs_shap",
        "top_row_contributions": [
            {
                "feature": feature,
                "value": float(value),
            }
            for feature, value in ranked_row
        ],
    }


def _build_shap_artifacts(shap_analysis: dict[str, Any]) -> dict[str, Any]:
    """Build SHAP artifact payloads with stable filenames and metadata."""
    if not shap_analysis.get("available"):
        return {
            "content_types": {},
            "metadata": {
                "available": False,
                "reason": shap_analysis["reason"],
            },
        }

    beeswarm_filename = "shap_beeswarm.png"
    waterfall_filename = "shap_waterfall.png"
    summary_filename = "shap_summary.json"
    beeswarm_png = _build_beeswarm_png(shap_analysis)
    waterfall_png, waterfall_metadata = _build_waterfall_png(shap_analysis)
    summary_json = {
        "artifact_type": "shap_summary",
        "target_algorithm": shap_analysis["target_algorithm"],
        "explainer_type": shap_analysis["explainer_type"],
        "global_importance": shap_analysis["feature_ranking"],
        "directional_effects": shap_analysis["directional_summary"],
        "reviewer_safe_summary": {
            "top_features": shap_analysis["top_features"],
            "summary": (
                f"Top SHAP features for {shap_analysis['target_algorithm']}: "
                + ", ".join(feature["feature"] for feature in shap_analysis["top_features"])
            ),
        },
        "mlflow_safe_summary": {
            "target_algorithm": shap_analysis["target_algorithm"],
            "explainer_type": shap_analysis["explainer_type"],
            "n_rows": shap_analysis["n_rows"],
            "n_features": shap_analysis["n_features"],
            "top_features": shap_analysis["top_features"],
        },
        "waterfall": waterfall_metadata,
    }

    return {
        beeswarm_filename: beeswarm_png,
        waterfall_filename: waterfall_png,
        summary_filename: summary_json,
        "content_types": {
            beeswarm_filename: "image/png",
            waterfall_filename: "image/png",
            summary_filename: "application/json",
        },
        "metadata": {
            "available": True,
            "artifact_category": "shap",
            "filenames": [
                beeswarm_filename,
                waterfall_filename,
                summary_filename,
            ],
            "representative_row_strategy": "largest_total_abs_shap",
        },
    }


def _build_mlflow_payload(
    primary_metric: str,
    winner: str,
    runner_up: str | None,
    rankings: list[dict[str, Any]],
    algorithm_summaries: list[dict[str, Any]],
    tie_break: dict[str, Any],
    ground_truth_comparison: dict[str, Any],
    shap_results: dict[str, Any],
    shap_artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Build a future logging bundle without performing MLflow side effects."""
    winner_entry = rankings[0]

    return {
        "metrics": {
            "winner_primary_metric": winner_entry["primary_metric_value"],
            "winner_rank": 1,
            "ground_truth_available": bool(ground_truth_comparison.get("available", False)),
        },
        "params": {
            "primary_metric": primary_metric,
            "winner_algorithm": winner,
            "runner_up_algorithm": runner_up,
        },
        "tags": {
            "evaluation_phase": "post_training",
            "evaluation_status": "success",
            "winner_algorithm": winner,
            "runner_up_algorithm": runner_up or "",
            "primary_metric": primary_metric,
            "has_ground_truth": "true" if ground_truth_comparison.get("available") else "false",
            "shap_available": "true" if shap_results.get("available") else "false",
        },
        "context": {
            "algorithms_evaluated": [item["algorithm"] for item in rankings],
            "algorithm_count": len(rankings),
            "algorithm_summaries": algorithm_summaries,
            "tie_break": tie_break,
        },
        "artifacts": [
            {
                "name": filename,
                "type": shap_artifacts["content_types"][filename],
                "content_mode": "inline",
                "content": shap_artifacts[filename],
            }
            for filename in shap_artifacts.get("metadata", {}).get("filenames", [])
        ],
    }


def run_evaluation_workflow(
    results: dict[str, dict[str, Any]],
    data: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Post-training evaluation contract for reviewer and future MLflow use."""
    if not results:
        raise ValueError("results must contain at least one algorithm output")

    primary_metric = settings["model"]["primary_metric"]
    rankings, winner, runner_up, tie_break = _extract_primary_rankings(results, primary_metric)
    metric_rankings = _build_metric_rankings(results)
    ground_truth_comparison = _build_ground_truth_comparison(results, rankings, data)
    shap_analysis = _compute_shap_analysis(results, winner, data)
    shap_results = _build_shap_results(shap_analysis)
    algorithm_summaries = _build_algorithm_summaries(rankings, ground_truth_comparison)
    model_selection_summary = _build_model_selection_summary(
        ranked_algorithms=rankings,
        winner=winner,
        runner_up=runner_up,
        primary_metric=primary_metric,
        ground_truth_comparison=ground_truth_comparison,
        tie_break=tie_break,
        shap_results=shap_results,
    )
    reviewer_summary = _build_reviewer_summary(
        ranked_algorithms=rankings,
        winner=winner,
        runner_up=runner_up,
        primary_metric=primary_metric,
        ground_truth_comparison=ground_truth_comparison,
        tie_break=tie_break,
        model_selection_summary=model_selection_summary,
    )

    evaluation_result = {
        "winner": winner,
        "runner_up": runner_up,
        "primary_metric": primary_metric,
        "rankings": rankings,
        "algorithm_summaries": algorithm_summaries,
        "metric_rankings": metric_rankings,
        "tie_break": tie_break,
        "ground_truth_comparison": ground_truth_comparison,
        "model_selection_summary": model_selection_summary,
        "reviewer_summary": reviewer_summary,
        "shap_available": bool(shap_results.get("available")),
    }

    shap_artifacts = _build_shap_artifacts(shap_analysis)
    mlflow_payload = _build_mlflow_payload(
        primary_metric=primary_metric,
        winner=winner,
        runner_up=runner_up,
        rankings=rankings,
        algorithm_summaries=algorithm_summaries,
        tie_break=tie_break,
        ground_truth_comparison=ground_truth_comparison,
        shap_results=shap_results,
        shap_artifacts=shap_artifacts,
    )

    return {
        "evaluation_result": evaluation_result,
        "reviewer_summary": reviewer_summary,
        "shap_results": shap_results,
        "shap_artifacts": shap_artifacts,
        "mlflow_payload": mlflow_payload,
    }
