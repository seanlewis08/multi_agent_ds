"""Pure data-cleaning helpers used by the preparation workflow."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _new_summary(action_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Build a consistent summary payload for one cleaning action."""
    return {
        "action": action_name,
        "requested_columns": list(params.get("columns", [])),
        "applied_columns": [],
        "skipped_columns": [],
    }


def _mark_skipped(summary: dict[str, Any], column: str, reason: str) -> None:
    """Record why one requested column could not be acted on."""
    summary["skipped_columns"].append({"column": column, "reason": reason})


def apply_cleaning_actions(
    df: pd.DataFrame,
    actions: list[dict[str, Any]] | None,
    target_col: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Apply a compact set of cleaning actions to a dataframe."""
    if not actions:
        return df.copy(), []

    cleaned = df.copy()
    summaries: list[dict[str, Any]] = []

    for action in actions:
        action_name = action.get("action")
        params = action.get("params", {})
        summary = _new_summary(action_name, params)

        if action_name == "drop_columns":
            columns_to_drop: list[str] = []
            available_columns = set(cleaned.columns)
            for column in params.get("columns", []):
                if column == target_col:
                    _mark_skipped(summary, column, "target_column_protected")
                    continue
                if column not in available_columns:
                    _mark_skipped(summary, column, "missing_column")
                    continue
                columns_to_drop.append(column)
                summary["applied_columns"].append(column)
                available_columns.remove(column)
            if columns_to_drop:
                cleaned = cleaned.drop(columns=columns_to_drop)
            summary["status"] = "applied" if summary["applied_columns"] else "skipped"
            summaries.append(summary)
            continue

        if action_name == "impute_numeric_median":
            for column in params.get("columns", []):
                if column == target_col:
                    _mark_skipped(summary, column, "target_column_protected")
                    continue
                if column not in cleaned.columns:
                    _mark_skipped(summary, column, "missing_column")
                    continue
                if not pd.api.types.is_numeric_dtype(cleaned[column]):
                    _mark_skipped(summary, column, "non_numeric_column")
                    continue
                median = cleaned[column].median()
                if pd.isna(median):
                    _mark_skipped(summary, column, "median_unavailable")
                    continue
                filled_count = int(cleaned[column].isna().sum())
                cleaned[column] = cleaned[column].fillna(median)
                summary["applied_columns"].append(
                    {"column": column, "fill_value": float(median), "filled_count": filled_count}
                )
            summary["status"] = "applied" if summary["applied_columns"] else "skipped"
            summaries.append(summary)
            continue

        if action_name == "impute_categorical_mode":
            for column in params.get("columns", []):
                if column == target_col:
                    _mark_skipped(summary, column, "target_column_protected")
                    continue
                if column not in cleaned.columns:
                    _mark_skipped(summary, column, "missing_column")
                    continue
                if pd.api.types.is_numeric_dtype(cleaned[column]):
                    _mark_skipped(summary, column, "numeric_column")
                    continue
                mode = cleaned[column].mode(dropna=True)
                if not mode.empty:
                    filled_count = int(cleaned[column].isna().sum())
                    cleaned[column] = cleaned[column].fillna(mode.iloc[0])
                    summary["applied_columns"].append(
                        {
                            "column": column,
                            "fill_value": mode.iloc[0],
                            "filled_count": filled_count,
                        }
                    )
                    continue
                _mark_skipped(summary, column, "mode_unavailable")
            summary["status"] = "applied" if summary["applied_columns"] else "skipped"
            summaries.append(summary)
            continue

        if action_name == "clip_outliers_iqr":
            multiplier = float(params.get("multiplier", 1.5))
            summary["multiplier"] = multiplier
            for column in params.get("columns", []):
                if column == target_col:
                    _mark_skipped(summary, column, "target_column_protected")
                    continue
                if column not in cleaned.columns:
                    _mark_skipped(summary, column, "missing_column")
                    continue
                if not pd.api.types.is_numeric_dtype(cleaned[column]):
                    _mark_skipped(summary, column, "non_numeric_column")
                    continue
                series = cleaned[column]
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                if pd.isna(iqr) or iqr == 0:
                    _mark_skipped(summary, column, "iqr_unavailable")
                    continue
                lower = q1 - multiplier * iqr
                upper = q3 + multiplier * iqr
                clipped_count = int(((series < lower) | (series > upper)).sum())
                cleaned[column] = series.clip(lower=lower, upper=upper)
                summary["applied_columns"].append(
                    {
                        "column": column,
                        "lower_bound": float(lower),
                        "upper_bound": float(upper),
                        "clipped_count": clipped_count,
                    }
                )
            summary["status"] = "applied" if summary["applied_columns"] else "skipped"
            summaries.append(summary)
            continue

        requested_columns = list(params.get("columns", []))
        if requested_columns:
            for column in requested_columns:
                _mark_skipped(summary, column, "unsupported_action")
        else:
            _mark_skipped(summary, "", "unsupported_action")
        summary["status"] = "skipped"
        summaries.append(summary)

    return cleaned, summaries
