from __future__ import annotations

import numpy as np
import pandas as pd

from multi_agent_ds.skills.cleaning import apply_cleaning_actions


def test_drop_columns_protects_target_and_reports_missing_columns() -> None:
    df = pd.DataFrame(
        {
            "drop_me": [1, 2],
            "keep_me": [3, 4],
            "binary_target": [0, 1],
        }
    )

    cleaned, summaries = apply_cleaning_actions(
        df=df,
        actions=[
            {
                "action": "drop_columns",
                "params": {"columns": ["drop_me", "binary_target", "missing_col"]},
            }
        ],
        target_col="binary_target",
    )

    assert cleaned.columns.tolist() == ["keep_me", "binary_target"]
    assert summaries == [
        {
            "action": "drop_columns",
            "requested_columns": ["drop_me", "binary_target", "missing_col"],
            "applied_columns": ["drop_me"],
            "skipped_columns": [
                {"column": "binary_target", "reason": "target_column_protected"},
                {"column": "missing_col", "reason": "missing_column"},
            ],
            "status": "applied",
        }
    ]


def test_impute_numeric_median_skips_non_numeric_target_and_missing_medians() -> None:
    df = pd.DataFrame(
        {
            "num_ok": [1.0, None, 5.0],
            "num_all_missing": [np.nan, np.nan, np.nan],
            "category": ["a", None, "b"],
            "binary_target": [0, 1, 1],
        }
    )

    cleaned, summaries = apply_cleaning_actions(
        df=df,
        actions=[
            {
                "action": "impute_numeric_median",
                "params": {
                    "columns": [
                        "num_ok",
                        "num_all_missing",
                        "category",
                        "binary_target",
                        "missing_col",
                    ]
                },
            }
        ],
        target_col="binary_target",
    )

    assert cleaned["num_ok"].tolist() == [1.0, 3.0, 5.0]
    assert cleaned["num_all_missing"].isna().all()
    assert summaries == [
        {
            "action": "impute_numeric_median",
            "requested_columns": [
                "num_ok",
                "num_all_missing",
                "category",
                "binary_target",
                "missing_col",
            ],
            "applied_columns": [{"column": "num_ok", "fill_value": 3.0, "filled_count": 1}],
            "skipped_columns": [
                {"column": "num_all_missing", "reason": "median_unavailable"},
                {"column": "category", "reason": "non_numeric_column"},
                {"column": "binary_target", "reason": "target_column_protected"},
                {"column": "missing_col", "reason": "missing_column"},
            ],
            "status": "applied",
        }
    ]


def test_impute_categorical_mode_skips_numeric_target_and_missing_modes() -> None:
    df = pd.DataFrame(
        {
            "segment": ["a", None, "a"],
            "all_missing_category": [None, None, None],
            "numeric_col": [1.0, None, 3.0],
            "binary_target": [0, 1, 1],
        }
    )

    cleaned, summaries = apply_cleaning_actions(
        df=df,
        actions=[
            {
                "action": "impute_categorical_mode",
                "params": {
                    "columns": [
                        "segment",
                        "all_missing_category",
                        "numeric_col",
                        "binary_target",
                        "missing_col",
                    ]
                },
            }
        ],
        target_col="binary_target",
    )

    assert cleaned["segment"].tolist() == ["a", "a", "a"]
    assert cleaned["all_missing_category"].isna().all()
    assert summaries == [
        {
            "action": "impute_categorical_mode",
            "requested_columns": [
                "segment",
                "all_missing_category",
                "numeric_col",
                "binary_target",
                "missing_col",
            ],
            "applied_columns": [{"column": "segment", "fill_value": "a", "filled_count": 1}],
            "skipped_columns": [
                {"column": "all_missing_category", "reason": "mode_unavailable"},
                {"column": "numeric_col", "reason": "numeric_column"},
                {"column": "binary_target", "reason": "target_column_protected"},
                {"column": "missing_col", "reason": "missing_column"},
            ],
            "status": "applied",
        }
    ]


def test_clip_outliers_iqr_reports_applied_and_skipped_columns() -> None:
    df = pd.DataFrame(
        {
            "claim_amount_avg": [10.0, 12.0, 14.0, 1000.0],
            "flat_numeric": [5.0, 5.0, 5.0, 5.0],
            "category": ["a", "b", "c", "d"],
            "binary_target": [0, 0, 1, 1],
        }
    )

    cleaned, summaries = apply_cleaning_actions(
        df=df,
        actions=[
            {
                "action": "clip_outliers_iqr",
                "params": {
                    "columns": [
                        "claim_amount_avg",
                        "flat_numeric",
                        "category",
                        "binary_target",
                        "missing_col",
                    ],
                    "multiplier": 1.5,
                },
            }
        ],
        target_col="binary_target",
    )

    assert cleaned["claim_amount_avg"].iloc[-1] < 1000.0
    assert cleaned["flat_numeric"].tolist() == [5.0, 5.0, 5.0, 5.0]
    assert summaries == [
        {
            "action": "clip_outliers_iqr",
            "requested_columns": [
                "claim_amount_avg",
                "flat_numeric",
                "category",
                "binary_target",
                "missing_col",
            ],
            "applied_columns": [
                    {
                        "column": "claim_amount_avg",
                        "lower_bound": -362.0,
                        "upper_bound": 634.0,
                        "clipped_count": 1,
                    }
                ],
            "skipped_columns": [
                {"column": "flat_numeric", "reason": "iqr_unavailable"},
                {"column": "category", "reason": "non_numeric_column"},
                {"column": "binary_target", "reason": "target_column_protected"},
                {"column": "missing_col", "reason": "missing_column"},
            ],
            "multiplier": 1.5,
            "status": "applied",
        }
    ]
