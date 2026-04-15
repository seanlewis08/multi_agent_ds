from __future__ import annotations

from pathlib import Path

import pandas as pd

from multi_agent_ds.core import resolve_tracking_uri
from multi_agent_ds.skills import modeling as modeling_skill
from multi_agent_ds.workflows import modeling


def test_resolve_tracking_uri_keeps_absolute_sqlite_uri() -> None:
    uri = "sqlite:////Users/sean.lewis/DataspellProjects/multi_agent_ds/mlruns.db"
    assert resolve_tracking_uri(uri) == uri


def test_resolve_tracking_uri_resolves_relative_sqlite_uri() -> None:
    uri = resolve_tracking_uri("sqlite:///mlruns.db")
    assert uri == "sqlite:////Users/sean.lewis/DataspellProjects/multi_agent_ds/mlruns.db"


def test_safe_output_name_normalizes_run_names() -> None:
    assert modeling._safe_output_name("baseline v1 / lightgbm") == "baseline_v1_lightgbm"
    assert modeling._safe_output_name("   ", fallback="abc123") == "abc123"


def test_resolve_output_dir_uses_run_name_and_deduplicates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(modeling, "_MLFLOW_OUTPUT_DIR", tmp_path)

    first = modeling._resolve_output_dir("baseline v1 / lightgbm", "abc123")
    second = modeling._resolve_output_dir("baseline v1 / lightgbm", "abc123")

    assert first.name == "baseline_v1_lightgbm"
    assert second.name == "baseline_v1_lightgbm__2"
    assert first.is_dir()
    assert second.is_dir()


def test_export_folder_name_defaults_to_experiment_timestamp() -> None:
    generated = modeling._export_folder_name("experiment", 1_741_000_000_000)
    assert generated == "experiment_2025-03-03_110640"


def test_export_folder_name_preserves_explicit_user_name() -> None:
    generated = modeling._export_folder_name("sean_baseline", 1_741_000_000_000)
    assert generated == "sean_baseline_2025-03-03_110640"


def test_export_folder_name_replaces_old_generated_parent_name() -> None:
    generated = modeling._export_folder_name(
        "baseline_lightgbm_logistic_regression_2025-03-03_110640",
        1_741_000_000_000,
    )
    assert generated == "experiment_2025-03-03_110640"


def test_prepare_data_creates_train_validation_test_splits() -> None:
    rows = 100
    df = pd.DataFrame(
        {
            "feature_num": range(rows),
            "feature_cat": ["a", "b"] * (rows // 2),
            "target": [0, 1] * (rows // 2),
            "_true_probability": [0.1, 0.9] * (rows // 2),
        }
    )

    data = modeling_skill.prepare_data(df, test_size=0.2, validation_size=0.2)

    assert len(data["X_train"]) == 60
    assert len(data["X_validation"]) == 20
    assert len(data["X_test"]) == 20
    assert len(data["true_prob_validation"]) == 20
    assert len(data["true_prob_test"]) == 20
    assert data["data_summary"]["n_validation"] == 20


def test_fit_model_history_includes_validation_series() -> None:
    class DummyBoostModel:
        def fit(self, X_train, y_train, eval_set, eval_names, eval_metric):
            self.evals_result_ = {
                eval_names[0]: {eval_metric: [0.7, 0.5, 0.4]},
                eval_names[1]: {eval_metric: [0.8, 0.6, 0.55]},
            }
            self.best_iteration_ = 2

    X_train = pd.DataFrame({"x": [1, 2, 3, 4]})
    y_train = pd.Series([0, 1, 0, 1])
    X_validation = pd.DataFrame({"x": [5, 6]})
    y_validation = pd.Series([0, 1])

    history = modeling_skill._fit_model_and_capture_history(
        DummyBoostModel(),
        "lightgbm",
        X_train,
        y_train,
        X_validation,
        y_validation,
    )

    assert history is not None
    datasets = {item["dataset"] for item in history["series"]}
    assert datasets == {"train", "validation"}
