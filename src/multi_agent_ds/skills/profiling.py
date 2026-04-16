"""Pure profiling helpers for the EDA agent and discovery workflow."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def _excluded_feature_columns(df: pd.DataFrame, target_col: str) -> list[str]:
    """Return internal columns that should not appear in EDA feature summaries."""
    return [col for col in df.columns if col != target_col and col.startswith("_")]


def _feature_frame(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """Return features only, validating the target column exists."""
    if target_col not in df.columns:
        raise KeyError(f"Target column '{target_col}' not found in DataFrame.")
    excluded = [target_col, *_excluded_feature_columns(df, target_col)]
    return df.drop(columns=excluded)


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    """Return numeric columns from a DataFrame."""
    return df.select_dtypes(include=[np.number, "bool"]).columns.tolist()


def _categorical_columns(df: pd.DataFrame) -> list[str]:
    """Return non-numeric columns from a DataFrame."""
    return [col for col in df.columns if col not in _numeric_columns(df)]


def _features_with_missing(distributions: dict[str, Any]) -> list[dict[str, Any]]:
    """Return features with any missing values, sorted by missing rate."""
    flagged: list[dict[str, Any]] = []
    for bucket in ("numerical", "categorical"):
        for feature, summary in distributions[bucket].items():
            if summary["missing_count"] > 0:
                flagged.append(
                    {
                        "feature": feature,
                        "missing_count": summary["missing_count"],
                        "missing_rate": summary["missing_rate"],
                    }
                )
    flagged.sort(key=lambda item: item["missing_rate"], reverse=True)
    return flagged


def _top_skewed_numeric(distributions: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the most skewed numeric features."""
    skewed = [
        {"feature": feature, "skew": summary["skew"]}
        for feature, summary in distributions["numerical"].items()
        if abs(summary["skew"]) >= 1.0
    ]
    skewed.sort(key=lambda item: abs(item["skew"]), reverse=True)
    return skewed[:10]


def _high_cardinality_categoricals(distributions: dict[str, Any]) -> list[dict[str, Any]]:
    """Return categorical features with many distinct values."""
    high_cardinality = [
        {"feature": feature, "n_unique": summary["n_unique"]}
        for feature, summary in distributions["categorical"].items()
        if summary["n_unique"] > 10
    ]
    high_cardinality.sort(key=lambda item: item["n_unique"], reverse=True)
    return high_cardinality[:10]


def compute_distributions(df: pd.DataFrame, target_col: str) -> dict[str, Any]:
    """Summarize numeric and categorical feature distributions."""
    features = _feature_frame(df, target_col)
    numeric_cols = _numeric_columns(features)
    categorical_cols = _categorical_columns(features)

    numeric_summary: dict[str, dict[str, Any]] = {}
    for col in numeric_cols:
        series = features[col]
        numeric_summary[col] = {
            "dtype": str(series.dtype),
            "missing_count": int(series.isna().sum()),
            "missing_rate": float(series.isna().mean()),
            "mean": float(series.mean()),
            "std": float(series.std(ddof=0)),
            "min": float(series.min()),
            "p25": float(series.quantile(0.25)),
            "median": float(series.median()),
            "p75": float(series.quantile(0.75)),
            "max": float(series.max()),
            "skew": float(series.skew()),
        }

    categorical_summary: dict[str, dict[str, Any]] = {}
    for col in categorical_cols:
        series = features[col]
        top_values = series.astype("object").fillna("__missing__").value_counts().head(5)
        categorical_summary[col] = {
            "dtype": str(series.dtype),
            "missing_count": int(series.isna().sum()),
            "missing_rate": float(series.isna().mean()),
            "n_unique": int(series.nunique(dropna=True)),
            "top_values": [
                {"value": str(value), "count": int(count)}
                for value, count in top_values.items()
            ],
        }

    return {
        "n_features": int(features.shape[1]),
        "numeric_feature_count": len(numeric_cols),
        "categorical_feature_count": len(categorical_cols),
        "numerical": numeric_summary,
        "categorical": categorical_summary,
    }


def compute_correlations(df: pd.DataFrame, target_col: str) -> dict[str, Any]:
    """Summarize numeric feature correlations and target associations."""
    filtered_df = _feature_frame(df, target_col).assign(**{target_col: df[target_col]})
    numeric_cols = _numeric_columns(filtered_df)
    feature_numeric_cols = [col for col in numeric_cols if col != target_col]

    if not feature_numeric_cols:
        return {"high_correlation_pairs": [], "target_correlations": []}

    corr_df = filtered_df[feature_numeric_cols].corr()
    high_pairs: list[dict[str, Any]] = []

    for idx, left in enumerate(feature_numeric_cols):
        for right in feature_numeric_cols[idx + 1 :]:
            corr_value = corr_df.at[left, right]
            if pd.notna(corr_value) and abs(corr_value) >= 0.7:
                high_pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "correlation": float(corr_value),
                    }
                )

    target_correlations: list[dict[str, Any]] = []
    if target_col in numeric_cols:
        target_corr = filtered_df[feature_numeric_cols + [target_col]].corr()[target_col].drop(target_col)
        target_correlations = [
            {"feature": feature, "correlation": float(value)}
            for feature, value in target_corr.abs().sort_values(ascending=False).items()
            if pd.notna(value)
        ]
        for item in target_correlations:
            feature = item["feature"]
            item["correlation"] = float(target_corr[feature])

    return {
        "high_correlation_pairs": sorted(
            high_pairs, key=lambda item: abs(item["correlation"]), reverse=True
        ),
        "target_correlations": target_correlations[:10],
    }


def compute_target_analysis(df: pd.DataFrame, target_col: str) -> dict[str, Any]:
    """Summarize target distribution and class balance."""
    target = df[target_col]
    value_counts = target.value_counts(dropna=False).sort_index()

    class_balance = [
        {
            "class": str(label),
            "count": int(count),
            "rate": float(count / len(df)),
        }
        for label, count in value_counts.items()
    ]

    positive_mask = target == 1
    positive_rate = float(positive_mask.mean()) if len(target) else 0.0

    return {
        "target_column": target_col,
        "n_rows": int(len(df)),
        "missing_count": int(target.isna().sum()),
        "missing_rate": float(target.isna().mean()),
        "positive_rate": positive_rate,
        "class_balance": class_balance,
        "is_imbalanced": positive_rate < 0.2 or positive_rate > 0.8,
    }


def compute_feature_target_relationships(df: pd.DataFrame, target_col: str) -> dict[str, Any]:
    """Summarize compact feature-target signal diagnostics."""
    target = df[target_col]
    features = _feature_frame(df, target_col)
    numeric_cols = _numeric_columns(features)
    categorical_cols = _categorical_columns(features)

    numeric_relationships: list[dict[str, Any]] = []
    for col in numeric_cols:
        feature = features[col]
        correlation = feature.corr(target)
        auc_value = None
        valid = feature.notna() & target.notna()
        if valid.sum() > 1 and target[valid].nunique() == 2 and feature[valid].nunique() > 1:
            auc_value = float(roc_auc_score(target[valid], feature[valid]))
            auc_value = max(auc_value, 1 - auc_value)
        numeric_relationships.append(
            {
                "feature": col,
                "correlation": float(correlation) if pd.notna(correlation) else 0.0,
                "auc": auc_value,
            }
        )

    categorical_relationships: list[dict[str, Any]] = []
    for col in categorical_cols:
        feature = features[col].astype("object").fillna("__missing__")
        rate_by_category = target.groupby(feature).mean().sort_values(ascending=False)
        top_categories = [
            {"category": str(category), "target_rate": float(rate)}
            for category, rate in rate_by_category.head(5).items()
        ]
        gap = float(rate_by_category.max() - rate_by_category.min()) if not rate_by_category.empty else 0.0
        categorical_relationships.append(
            {
                "feature": col,
                "target_rate_gap": gap,
                "top_categories": top_categories,
            }
        )

    top_numeric = sorted(
        numeric_relationships,
        key=lambda item: max(abs(item["correlation"]), item["auc"] or 0.0),
        reverse=True,
    )[:10]
    top_categorical = sorted(
        categorical_relationships,
        key=lambda item: item["target_rate_gap"],
        reverse=True,
    )[:10]

    return {
        "numerical": numeric_relationships,
        "categorical": categorical_relationships,
        "top_numerical_signals": top_numeric,
        "top_categorical_signals": top_categorical,
    }


def detect_outliers(df: pd.DataFrame, numerical_cols: list[str]) -> dict[str, Any]:
    """Compute IQR-based outlier counts for selected numeric columns."""
    summary: dict[str, dict[str, Any]] = {}
    for col in numerical_cols:
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if series.empty:
            summary[col] = {"outlier_count": 0, "outlier_rate": 0.0, "lower_bound": None, "upper_bound": None}
            continue
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - (1.5 * iqr)
        upper = q3 + (1.5 * iqr)
        mask = (series < lower) | (series > upper)
        summary[col] = {
            "outlier_count": int(mask.sum()),
            "outlier_rate": float(mask.mean()),
            "lower_bound": float(lower),
            "upper_bound": float(upper),
        }

    flagged = [
        {"feature": feature, **values}
        for feature, values in summary.items()
        if values["outlier_count"] > 0
    ]
    flagged.sort(key=lambda item: item["outlier_rate"], reverse=True)

    return {
        "numerical_columns_checked": numerical_cols,
        "by_feature": summary,
        "flagged_features": flagged,
    }


def profile_dataset(df: pd.DataFrame, target_col: str) -> dict[str, Any]:
    """Return a compact structured EDA profile for downstream agent use."""
    features = _feature_frame(df, target_col)
    numeric_cols = _numeric_columns(features)
    categorical_cols = _categorical_columns(features)
    excluded_columns = _excluded_feature_columns(df, target_col)
    distributions = compute_distributions(df, target_col)
    correlations = compute_correlations(df, target_col)
    feature_target_relationships = compute_feature_target_relationships(df, target_col)
    outliers = detect_outliers(df, numeric_cols)

    return {
        "dataset_summary": {
            "n_rows": int(len(df)),
            "n_features": int(features.shape[1]),
            "target_column": target_col,
            "excluded_metadata_columns": excluded_columns,
            "numeric_features": numeric_cols,
            "categorical_features": categorical_cols,
        },
        "distributions": {
            "feature_counts": {
                "numeric": distributions["numeric_feature_count"],
                "categorical": distributions["categorical_feature_count"],
            },
            "features_with_missing": _features_with_missing(distributions),
            "top_skewed_numeric": _top_skewed_numeric(distributions),
            "high_cardinality_categoricals": _high_cardinality_categoricals(distributions),
        },
        "target_analysis": compute_target_analysis(df, target_col),
        "correlations": {
            "high_correlation_pairs": correlations["high_correlation_pairs"],
            "target_correlations": correlations["target_correlations"],
        },
        "feature_target_relationships": {
            "top_numerical_signals": feature_target_relationships["top_numerical_signals"],
            "top_categorical_signals": feature_target_relationships["top_categorical_signals"],
        },
        "outliers": {
            "flagged_features": outliers["flagged_features"][:10],
        },
    }
