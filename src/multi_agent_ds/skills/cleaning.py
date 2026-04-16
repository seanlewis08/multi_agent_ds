"""Pure data-cleaning helpers used by the preparation workflow."""

from __future__ import annotations

from typing import Any

import pandas as pd


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

        if action_name == "drop_columns":
            columns = [
                column
                for column in params.get("columns", [])
                if column in cleaned.columns and column != target_col
            ]
            cleaned = cleaned.drop(columns=columns)
            summaries.append({"action": action_name, "columns": columns})
            continue

        if action_name == "impute_numeric_median":
            columns = [
                column
                for column in params.get("columns", [])
                if column in cleaned.columns
                and column != target_col
                and pd.api.types.is_numeric_dtype(cleaned[column])
            ]
            for column in columns:
                cleaned[column] = cleaned[column].fillna(cleaned[column].median())
            summaries.append({"action": action_name, "columns": columns})
            continue

        if action_name == "impute_categorical_mode":
            columns = [
                column
                for column in params.get("columns", [])
                if column in cleaned.columns and not pd.api.types.is_numeric_dtype(cleaned[column])
            ]
            for column in columns:
                mode = cleaned[column].mode(dropna=True)
                if not mode.empty:
                    cleaned[column] = cleaned[column].fillna(mode.iloc[0])
            summaries.append({"action": action_name, "columns": columns})
            continue

        if action_name == "clip_outliers_iqr":
            multiplier = float(params.get("multiplier", 1.5))
            columns = [
                column
                for column in params.get("columns", [])
                if column in cleaned.columns and pd.api.types.is_numeric_dtype(cleaned[column])
            ]
            clipped_columns: list[str] = []
            for column in columns:
                series = cleaned[column]
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                if pd.isna(iqr) or iqr == 0:
                    continue
                lower = q1 - multiplier * iqr
                upper = q3 + multiplier * iqr
                cleaned[column] = series.clip(lower=lower, upper=upper)
                clipped_columns.append(column)
            summaries.append(
                {
                    "action": action_name,
                    "columns": clipped_columns,
                    "multiplier": multiplier,
                }
            )
            continue

        summaries.append({"action": action_name, "skipped": True})

    return cleaned, summaries
