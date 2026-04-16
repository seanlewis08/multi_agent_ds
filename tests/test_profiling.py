from __future__ import annotations

import pandas as pd

from multi_agent_ds.skills.profiling import (
    compute_correlations,
    compute_distributions,
    compute_feature_target_relationships,
    compute_target_analysis,
    detect_outliers,
    profile_dataset,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age": [22, 25, 47, 51, 60, 41],
            "annual_income": [32000, 40000, 70000, 82000, 120000, 76000],
            "vehicle_value": [5000, 8000, 18000, 22000, 90000, 20000],
            "state": ["OH", "OH", "CA", "TX", "TX", "CA"],
            "coverage_tier": ["basic", "basic", "standard", "premium", "premium", "standard"],
            "_true_probability": [0.1, 0.12, 0.32, 0.67, 0.81, 0.55],
            "binary_target": [0, 0, 0, 1, 1, 1],
        }
    )


def test_compute_distributions_summarizes_numeric_and_categorical_features() -> None:
    summary = compute_distributions(_sample_df(), "binary_target")

    assert summary["n_features"] == 5
    assert "age" in summary["numerical"]
    assert "state" in summary["categorical"]
    assert "_true_probability" not in summary["numerical"]


def test_compute_correlations_flags_high_pairs_and_target_correlations() -> None:
    summary = compute_correlations(_sample_df(), "binary_target")

    assert summary["target_correlations"]
    assert any(item["feature"] == "age" for item in summary["target_correlations"])
    assert not any(item["feature"] == "_true_probability" for item in summary["target_correlations"])


def test_compute_target_analysis_returns_class_balance_and_positive_rate() -> None:
    summary = compute_target_analysis(_sample_df(), "binary_target")

    assert summary["n_rows"] == 6
    assert summary["positive_rate"] == 0.5
    assert len(summary["class_balance"]) == 2


def test_compute_feature_target_relationships_returns_top_signals() -> None:
    summary = compute_feature_target_relationships(_sample_df(), "binary_target")

    assert summary["top_numerical_signals"]
    assert summary["top_categorical_signals"]
    assert any(item["feature"] == "state" for item in summary["categorical"])
    assert not any(item["feature"] == "_true_probability" for item in summary["numerical"])


def test_detect_outliers_returns_flagged_feature_summary() -> None:
    summary = detect_outliers(_sample_df(), ["vehicle_value", "age"])

    assert "vehicle_value" in summary["by_feature"]
    assert any(item["feature"] == "vehicle_value" for item in summary["flagged_features"])


def test_profile_dataset_returns_expected_sections() -> None:
    profile = profile_dataset(_sample_df(), "binary_target")

    assert sorted(profile.keys()) == [
        "correlations",
        "dataset_summary",
        "distributions",
        "feature_target_relationships",
        "outliers",
        "target_analysis",
    ]
    assert profile["dataset_summary"]["target_column"] == "binary_target"
    assert profile["dataset_summary"]["excluded_metadata_columns"] == ["_true_probability"]
    assert sorted(profile["distributions"].keys()) == [
        "feature_counts",
        "features_with_missing",
        "high_cardinality_categoricals",
        "top_skewed_numeric",
    ]
    assert sorted(profile["feature_target_relationships"].keys()) == [
        "top_categorical_signals",
        "top_numerical_signals",
    ]
    assert sorted(profile["outliers"].keys()) == ["flagged_features"]
