from __future__ import annotations

import numpy as np
import pandas as pd

from multi_agent_ds.skills.feature_engineering import apply_feature_actions


def test_log1p_creates_features_and_reports_skips() -> None:
    df = pd.DataFrame(
        {
            "claim_amount_avg": [0.0, 9.0, -3.0],
            "category": ["a", "b", "c"],
            "binary_target": [0, 1, 1],
        }
    )

    engineered, summaries = apply_feature_actions(
        df=df,
        actions=[
            {
                "action": "log1p",
                "params": {"columns": ["claim_amount_avg", "category", "binary_target", "missing_col"]},
            }
        ],
        target_col="binary_target",
    )

    assert np.allclose(engineered["claim_amount_avg_log1p"].tolist(), [0.0, np.log1p(9.0), 0.0])
    assert summaries == [
        {
            "action": "log1p",
            "created_features": [
                {
                    "feature": "claim_amount_avg_log1p",
                    "source_column": "claim_amount_avg",
                    "transform": "log1p_clip_nonnegative",
                }
            ],
            "skipped": [
                {"reason": "non_numeric_column", "column": "category"},
                {"reason": "target_column_protected", "column": "binary_target"},
                {"reason": "missing_column", "column": "missing_col"},
            ],
            "status": "applied",
            "requested_columns": ["claim_amount_avg", "category", "binary_target", "missing_col"],
        }
    ]


def test_ratio_creates_feature_and_records_zero_denominator_count() -> None:
    df = pd.DataFrame(
        {
            "claim_amount_avg": [10.0, 20.0, 30.0],
            "annual_premium": [2.0, 0.0, 5.0],
            "binary_target": [0, 1, 1],
        }
    )

    engineered, summaries = apply_feature_actions(
        df=df,
        actions=[
            {
                "action": "ratio",
                "params": {
                    "numerator": "claim_amount_avg",
                    "denominator": "annual_premium",
                    "output_column": "claim_to_premium_ratio",
                },
            }
        ],
        target_col="binary_target",
    )

    assert engineered["claim_to_premium_ratio"].tolist()[0] == 5.0
    assert pd.isna(engineered["claim_to_premium_ratio"].iloc[1])
    assert engineered["claim_to_premium_ratio"].tolist()[2] == 6.0
    assert summaries == [
        {
            "action": "ratio",
            "created_features": [
                {
                    "feature": "claim_to_premium_ratio",
                    "numerator": "claim_amount_avg",
                    "denominator": "annual_premium",
                    "zero_denominator_count": 1,
                }
            ],
            "skipped": [],
            "status": "applied",
            "requested_columns": ["claim_amount_avg", "annual_premium"],
            "output_column": "claim_to_premium_ratio",
        }
    ]


def test_ratio_reports_missing_or_invalid_inputs_cleanly() -> None:
    df = pd.DataFrame(
        {
            "numerator_ok": [1.0, 2.0],
            "category": ["a", "b"],
            "binary_target": [0, 1],
        }
    )

    _, summaries = apply_feature_actions(
        df=df,
        actions=[
            {
                "action": "ratio",
                "params": {
                    "numerator": "numerator_ok",
                    "denominator": "missing_denominator",
                    "output_column": "ratio_feature",
                },
            },
            {
                "action": "ratio",
                "params": {
                    "numerator": "category",
                    "denominator": "numerator_ok",
                    "output_column": "bad_ratio",
                },
            },
            {
                "action": "ratio",
                "params": {
                    "numerator": "numerator_ok",
                    "denominator": "numerator_ok",
                    "output_column": "binary_target",
                },
            },
        ],
        target_col="binary_target",
    )

    assert summaries == [
        {
            "action": "ratio",
            "created_features": [],
            "skipped": [{"reason": "missing_denominator", "column": "missing_denominator"}],
            "status": "skipped",
            "requested_columns": ["numerator_ok", "missing_denominator"],
            "output_column": "ratio_feature",
        },
        {
            "action": "ratio",
            "created_features": [],
            "skipped": [{"reason": "non_numeric_numerator", "column": "category"}],
            "status": "skipped",
            "requested_columns": ["category", "numerator_ok"],
            "output_column": "bad_ratio",
        },
        {
            "action": "ratio",
            "created_features": [],
            "skipped": [{"reason": "target_column_protected", "column": "binary_target"}],
            "status": "skipped",
            "requested_columns": ["numerator_ok", "numerator_ok"],
            "output_column": "binary_target",
        },
    ]
