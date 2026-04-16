from __future__ import annotations

from pathlib import Path

import pandas as pd

from multi_agent_ds.workflows.discovery import run_discovery_workflow


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age": [22, 25, 47, 51],
            "state": ["OH", "OH", "CA", "TX"],
            "binary_target": [0, 0, 1, 1],
        }
    )


def test_run_discovery_workflow_profiles_local_parquet(tmp_path: Path) -> None:
    data_path = tmp_path / "sample.parquet"
    _sample_df().to_parquet(data_path)

    result = run_discovery_workflow(
        data_path=str(data_path),
        settings={"data": {"source": "existing", "existing": {"target_column": "binary_target"}}},
    )

    assert result["data_path"] == str(data_path)
    assert result["target_column"] == "binary_target"
    assert result["n_rows"] == 4
    assert result["n_features"] == 2
    assert sorted(result["profile"].keys()) == [
        "correlations",
        "dataset_summary",
        "distributions",
        "feature_target_relationships",
        "outliers",
        "target_analysis",
    ]


def test_run_discovery_workflow_raises_when_existing_target_column_is_wrong(tmp_path: Path) -> None:
    data_path = tmp_path / "sample.parquet"
    _sample_df().to_parquet(data_path)

    try:
        run_discovery_workflow(
            data_path=str(data_path),
            settings={"data": {"source": "existing", "existing": {"target_column": "wrong_name"}}},
        )
    except KeyError as exc:
        assert "wrong_name" in str(exc)
    else:
        raise AssertionError("Expected KeyError when configured target column is missing.")


def test_run_discovery_workflow_raises_when_existing_target_column_is_missing_from_settings(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "sample.parquet"
    _sample_df().to_parquet(data_path)

    try:
        run_discovery_workflow(
            data_path=str(data_path),
            settings={"data": {"source": "existing", "existing": {}}},
        )
    except ValueError as exc:
        assert "data.existing.target_column" in str(exc)
    else:
        raise AssertionError("Expected ValueError when existing target column is not configured.")


def test_run_discovery_workflow_downloads_explicit_s3_uri(monkeypatch) -> None:
    sample_df = _sample_df()

    def fake_get_s3_client(_settings):
        class FakeClient:
            def download_file(self, bucket, key, destination):
                assert bucket == "example-bucket"
                assert key == "data/raw/sample.parquet"
                sample_df.to_parquet(destination)

        return FakeClient()

    monkeypatch.setattr("multi_agent_ds.workflows.discovery.get_s3_client", fake_get_s3_client)

    result = run_discovery_workflow(
        data_path="s3://example-bucket/data/raw/sample.parquet",
        settings={"data": {"source": "existing", "existing": {"target_column": "binary_target"}}},
    )

    assert result["data_path"] == "s3://example-bucket/data/raw/sample.parquet"
    assert result["n_rows"] == 4
