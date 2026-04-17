from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from multi_agent_ds.workflows.preparation import run_preparation_workflow


def test_run_preparation_workflow_applies_plan_and_returns_processed_artifact(monkeypatch, tmp_path: Path) -> None:
    source_path = tmp_path / "raw.parquet"
    pd.DataFrame(
        {
            "claim_amount_avg": [10.0, 12.0, 1000.0],
            "distance_to_work": [1.0, None, 4.0],
            "binary_target": [0, 1, 1],
        }
    ).to_parquet(source_path)

    uploads: list[tuple[str, str]] = []

    def fake_upload_to_s3(local_path, path_key, filename, settings):
        uploads.append((path_key, filename))
        assert Path(local_path).exists()
        return f"s3://{settings['s3']['bucket']}/{settings['s3']['prefix']}/{settings['s3']['paths'][path_key]}/{filename}"

    monkeypatch.setattr("multi_agent_ds.workflows.preparation.upload_to_s3", fake_upload_to_s3)

    result = run_preparation_workflow(
        data_path=str(source_path),
        prep_plan={
            "cleaning_actions": [
                {
                    "action": "clip_outliers_iqr",
                    "params": {"columns": ["claim_amount_avg"]},
                },
                {
                    "action": "impute_numeric_median",
                    "params": {"columns": ["distance_to_work"]},
                },
            ],
            "feature_actions": [
                {
                    "action": "ratio",
                    "params": {
                        "numerator": "claim_amount_avg",
                        "denominator": "distance_to_work",
                        "output_column": "claim_per_distance",
                    },
                }
            ],
        },
        settings={
            "data": {"source": "existing", "existing": {"target_column": "binary_target"}},
            "s3": {
                "bucket": "example-bucket",
                "prefix": "multi_agent_ds",
                "paths": {"processed": "data/processed"},
            },
        },
    )

    assert result["processed_data_path"].startswith("s3://example-bucket/multi_agent_ds/data/processed/")
    assert result["source_data_path"] == str(source_path)
    assert result["target_column"] == "binary_target"
    assert result["artifact_filename"].startswith("raw_processed_")
    assert result["artifact_filename"].endswith(".parquet")
    assert result["source_n_rows"] == 3
    assert result["source_n_features"] == 2
    assert result["n_rows"] == 3
    assert result["n_features"] == 3
    assert result["processed_n_rows"] == 3
    assert result["processed_n_features"] == 3
    assert result["cleaning_summary"][0]["action"] == "clip_outliers_iqr"
    assert result["feature_summary"][0]["action"] == "ratio"
    assert result["feature_summary"][0]["created_features"][0]["feature"] == "claim_per_distance"
    assert uploads[0][0] == "processed"


def test_run_preparation_workflow_raises_when_target_column_is_missing(tmp_path: Path) -> None:
    source_path = tmp_path / "raw.parquet"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_parquet(source_path)

    with pytest.raises(KeyError, match="Target column 'binary_target' not found"):
        run_preparation_workflow(
            data_path=str(source_path),
            prep_plan={"cleaning_actions": [], "feature_actions": []},
            settings={
                "data": {"source": "existing", "existing": {"target_column": "binary_target"}},
                "s3": {
                    "bucket": "example-bucket",
                    "prefix": "multi_agent_ds",
                    "paths": {"processed": "data/processed"},
                },
            },
        )


def test_run_preparation_workflow_returns_head_previews(monkeypatch, tmp_path: Path) -> None:
    """Head previews for raw + processed frames are included in the returned dict.

    The HTML report uses these to render side-by-side before/after tables on
    the ``data_engineer_execute`` state detail.
    """
    source_path = tmp_path / "raw.parquet"
    pd.DataFrame(
        {
            "claim_amount_avg": [10.0, 12.0, 1000.0],
            "distance_to_work": [1.0, None, 4.0],
            "binary_target": [0, 1, 1],
        }
    ).to_parquet(source_path)

    def fake_upload_to_s3(local_path, path_key, filename, settings):
        assert Path(local_path).exists()
        return f"s3://{settings['s3']['bucket']}/{settings['s3']['prefix']}/{settings['s3']['paths'][path_key]}/{filename}"

    monkeypatch.setattr("multi_agent_ds.workflows.preparation.upload_to_s3", fake_upload_to_s3)

    result = run_preparation_workflow(
        data_path=str(source_path),
        prep_plan={
            "cleaning_actions": [
                {
                    "action": "impute_numeric_median",
                    "params": {"columns": ["distance_to_work"]},
                },
            ],
            "feature_actions": [
                {
                    "action": "ratio",
                    "params": {
                        "numerator": "claim_amount_avg",
                        "denominator": "distance_to_work",
                        "output_column": "claim_per_distance",
                    },
                }
            ],
        },
        settings={
            "data": {"source": "existing", "existing": {"target_column": "binary_target"}},
            "s3": {
                "bucket": "example-bucket",
                "prefix": "multi_agent_ds",
                "paths": {"processed": "data/processed"},
            },
        },
    )

    raw_preview = result["raw_head_preview"]
    processed_preview = result["processed_head_preview"]

    assert isinstance(raw_preview, dict)
    assert isinstance(processed_preview, dict)
    assert raw_preview["total_rows"] == 3
    assert raw_preview["total_columns"] == 3
    assert list(raw_preview["columns"]) == [
        "claim_amount_avg",
        "distance_to_work",
        "binary_target",
    ]
    # 3 rows of data, each a list of stringified cells (one per column).
    assert len(raw_preview["rows"]) == 3
    assert all(isinstance(cell, str) for row in raw_preview["rows"] for cell in row)
    # Processed preview reflects the engineered frame (extra ratio column).
    assert "claim_per_distance" in processed_preview["columns"]
    assert processed_preview["total_columns"] == 4


def test_run_preparation_workflow_requires_existing_target_column_config(tmp_path: Path) -> None:
    source_path = tmp_path / "raw.parquet"
    pd.DataFrame({"feature": [1, 2], "binary_target": [0, 1]}).to_parquet(source_path)

    with pytest.raises(ValueError, match="data.existing.target_column"):
        run_preparation_workflow(
            data_path=str(source_path),
            prep_plan={"cleaning_actions": [], "feature_actions": []},
            settings={
                "data": {"source": "existing", "existing": {}},
                "s3": {
                    "bucket": "example-bucket",
                    "prefix": "multi_agent_ds",
                    "paths": {"processed": "data/processed"},
                },
            },
        )
