from __future__ import annotations

import numpy as np

from multi_agent_ds.skills import modeling
from multi_agent_ds.tools.artifacts import generate_run_artifacts


class _DummyHistoryModel:
    evals_result_ = {
        "train": {
            "binary_logloss": [0.62, 0.51, 0.44],
        }
    }
    best_iteration_ = 3


def test_extract_training_history_normalizes_lightgbm_evals_result() -> None:
    history = modeling._extract_training_history(_DummyHistoryModel(), "lightgbm")

    assert history is not None
    assert history["algorithm"] == "lightgbm"
    assert history["n_iterations"] == 3
    assert history["best_iteration"] == 3
    assert history["series"] == [
        {
            "dataset": "train",
            "metric": "binary_logloss",
            "values": [0.62, 0.51, 0.44],
        }
    ]


def test_generate_run_artifacts_includes_learning_curve_when_history_present() -> None:
    history = {
        "algorithm": "lightgbm",
        "history_source": "evals_result_",
        "n_iterations": 3,
        "best_iteration": 3,
        "series": [
            {
                "dataset": "train",
                "metric": "binary_logloss",
                "values": [0.62, 0.51, 0.44],
            }
        ],
    }

    artifacts = generate_run_artifacts(
        model=_DummyHistoryModel(),
        y_test=np.array([0, 1, 0, 1]),
        y_pred=np.array([0, 1, 0, 1]),
        y_prob=np.array([0.1, 0.8, 0.2, 0.9]),
        feature_names=["feature_a"],
        algo_name="lightgbm",
        training_history=history,
    )

    assert "learning_curve.json" in artifacts
    assert "learning_curve.png" in artifacts
    assert artifacts["learning_curve.json"]["best_iteration"] == 3
    assert artifacts["learning_curve.json"]["series"][0]["metric"] == "binary_logloss"
