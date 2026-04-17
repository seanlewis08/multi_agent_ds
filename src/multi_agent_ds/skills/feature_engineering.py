"""Pure feature-engineering helpers used by the preparation workflow."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from multi_agent_ds.tools.skill_recorder import record_skill_call


def _new_summary(action_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Build a consistent summary payload for one feature action."""
    summary = {
        "action": action_name,
        "created_features": [],
        "skipped": [],
        "status": "skipped",
    }
    if "columns" in params:
        summary["requested_columns"] = list(params.get("columns", []))
    return summary


def _mark_skipped(summary: dict[str, Any], reason: str, **details: Any) -> None:
    """Record why one requested feature action could not be applied."""
    summary["skipped"].append({"reason": reason, **details})


@record_skill_call
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
        summary = _new_summary(action_name, params)

        if action_name == "log1p":
            for column in params.get("columns", []):
                if column == target_col:
                    _mark_skipped(summary, "target_column_protected", column=column)
                    continue
                if column not in engineered.columns:
                    _mark_skipped(summary, "missing_column", column=column)
                    continue
                if not pd.api.types.is_numeric_dtype(engineered[column]):
                    _mark_skipped(summary, "non_numeric_column", column=column)
                    continue
                feature_name = f"{column}_log1p"
                engineered[feature_name] = np.log1p(engineered[column].clip(lower=0))
                summary["created_features"].append(
                    {
                        "feature": feature_name,
                        "source_column": column,
                        "transform": "log1p_clip_nonnegative",
                    }
                )
            summary["status"] = "applied" if summary["created_features"] else "skipped"
            summaries.append(summary)
            continue

        if action_name == "ratio":
            numerator = params.get("numerator")
            denominator = params.get("denominator")
            output_column = params.get("output_column")
            summary["requested_columns"] = [numerator, denominator]
            summary["output_column"] = output_column
            if not output_column:
                _mark_skipped(summary, "missing_output_column")
                summaries.append(summary)
                continue
            if output_column == target_col:
                _mark_skipped(summary, "target_column_protected", column=output_column)
                summaries.append(summary)
                continue
            if numerator not in engineered.columns:
                _mark_skipped(summary, "missing_numerator", column=numerator)
                summaries.append(summary)
                continue
            if denominator not in engineered.columns:
                _mark_skipped(summary, "missing_denominator", column=denominator)
                summaries.append(summary)
                continue
            if not pd.api.types.is_numeric_dtype(engineered[numerator]):
                _mark_skipped(summary, "non_numeric_numerator", column=numerator)
                summaries.append(summary)
                continue
            if not pd.api.types.is_numeric_dtype(engineered[denominator]):
                _mark_skipped(summary, "non_numeric_denominator", column=denominator)
                summaries.append(summary)
                continue

            zero_count = int(engineered[denominator].eq(0).sum())
            denominator_values = engineered[denominator].replace({0: pd.NA})
            engineered[output_column] = engineered[numerator] / denominator_values
            summary["created_features"].append(
                {
                    "feature": output_column,
                    "numerator": numerator,
                    "denominator": denominator,
                    "zero_denominator_count": zero_count,
                }
            )
            summary["status"] = "applied"
            summaries.append(summary)
            continue

        _mark_skipped(summary, "unsupported_action")
        summaries.append(summary)

    return engineered, summaries
