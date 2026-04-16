from __future__ import annotations

from pathlib import Path

import pandas as pd

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
            "feature_actions": [],
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
    assert result["n_rows"] == 3
    assert uploads[0][0] == "processed"
