"""Pure feature-engineering helpers used by the preparation workflow."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def apply_feature_actions(
    df: pd.DataFrame,
    actions: list[dict[str, Any]] | None,
    target_col: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Apply a compact set of feature-engineering actions to a dataframe."""
    if not actions:
        return df.copy(), []

    engineered = df.copy()
    summaries: list[dict[str, Any]] = []

    for action in actions:
        action_name = action.get("action")
        params = action.get("params", {})

        if action_name == "log1p":
            columns = [
                column
                for column in params.get("columns", [])
                if column in engineered.columns and column != target_col
            ]
            created: list[str] = []
            for column in columns:
                feature_name = f"{column}_log1p"
                engineered[feature_name] = np.log1p(engineered[column].clip(lower=0))
                created.append(feature_name)
            summaries.append({"action": action_name, "created_features": created})
            continue

        if action_name == "ratio":
            numerator = params.get("numerator")
            denominator = params.get("denominator")
            output_column = params.get("output_column")
            if (
                numerator in engineered.columns
                and denominator in engineered.columns
                and output_column
                and output_column != target_col
            ):
                denominator_values = engineered[denominator].replace({0: pd.NA})
                engineered[output_column] = engineered[numerator] / denominator_values
                summaries.append({"action": action_name, "created_features": [output_column]})
            else:
                summaries.append({"action": action_name, "skipped": True})
            continue

        summaries.append({"action": action_name, "skipped": True})

    return engineered, summaries
