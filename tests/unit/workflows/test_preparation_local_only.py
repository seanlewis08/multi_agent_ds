"""Tests for local_only mode in run_preparation_workflow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from multi_agent_ds.workflows.preparation import run_preparation_workflow


@pytest.fixture
def minimal_prep_plan() -> dict:
    """Minimal prep plan for testing."""
    return {
        "cleaning_actions": [],
        "feature_actions": [],
    }


@pytest.fixture
def minimal_dataframe() -> pd.DataFrame:
    """Minimal dataframe with a target column."""
    return pd.DataFrame({
        "feature_1": [1.0, 2.0, 3.0],
        "feature_2": [4.0, 5.0, 6.0],
        "target": [0, 1, 0],
    })


@pytest.fixture
def minimal_settings(tmp_path) -> dict:
    """Minimal settings with local data path."""
    return {
        "data": {
            "source": "synthetic",
            "synthetic": {
                "target": {
                    "column_name": "target",
                },
            },
            "processed_dir": str(tmp_path / "processed"),
        },
    }


def test_run_preparation_workflow_local_only_skips_upload(
    tmp_path,
    minimal_prep_plan,
    minimal_dataframe,
    minimal_settings,
    monkeypatch,
):
    """When local_only=True, upload_to_s3 is not called."""
    # Monkeypatch load_dataframe to return minimal data
    def mock_load_dataframe(data_path, settings):
        return minimal_dataframe, "test_source.parquet"

    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.load_dataframe",
        mock_load_dataframe,
    )

    # Monkeypatch cleaning and feature actions
    def mock_cleaning(df, actions, target_col):
        return df, {"cleaned": True}

    def mock_features(df, actions, target_col):
        return df, {"engineered": True}

    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.apply_cleaning_actions",
        mock_cleaning,
    )
    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.apply_feature_actions",
        mock_features,
    )

    # Mock upload_to_s3 and assert it is NOT called
    mock_upload = MagicMock()
    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.upload_to_s3",
        mock_upload,
    )

    # Call with local_only=True
    result = run_preparation_workflow(
        data_path="dummy.parquet",
        prep_plan=minimal_prep_plan,
        settings=minimal_settings,
        local_only=True,
    )

    # Assert upload_to_s3 was never called
    mock_upload.assert_not_called()

    # Assert the result contains a local path
    assert "processed_data_path" in result
    assert isinstance(result["processed_data_path"], str)
    assert Path(result["processed_data_path"]).exists()


def test_run_preparation_workflow_local_only_writes_locally(
    tmp_path,
    minimal_prep_plan,
    minimal_dataframe,
    minimal_settings,
    monkeypatch,
):
    """When local_only=True, processed parquet is written to local path."""
    def mock_load_dataframe(data_path, settings):
        return minimal_dataframe, "test_source.parquet"

    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.load_dataframe",
        mock_load_dataframe,
    )

    def mock_cleaning(df, actions, target_col):
        return df, {"cleaned": True}

    def mock_features(df, actions, target_col):
        return df, {"engineered": True}

    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.apply_cleaning_actions",
        mock_cleaning,
    )
    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.apply_feature_actions",
        mock_features,
    )

    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.upload_to_s3",
        MagicMock(),
    )

    result = run_preparation_workflow(
        data_path="dummy.parquet",
        prep_plan=minimal_prep_plan,
        settings=minimal_settings,
        local_only=True,
    )

    processed_path = Path(result["processed_data_path"])
    assert processed_path.exists(), f"Local file not found at {processed_path}"
    assert processed_path.suffix == ".parquet"

    # Verify the file is readable as a parquet
    pdf = pd.read_parquet(processed_path)
    assert len(pdf) == 3
    assert "target" in pdf.columns


def test_run_preparation_workflow_default_uses_upload(
    tmp_path,
    minimal_prep_plan,
    minimal_dataframe,
    monkeypatch,
):
    """When local_only=False (default), upload_to_s3 IS called."""
    def mock_load_dataframe(data_path, settings):
        return minimal_dataframe, "test_source.parquet"

    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.load_dataframe",
        mock_load_dataframe,
    )

    def mock_cleaning(df, actions, target_col):
        return df, {"cleaned": True}

    def mock_features(df, actions, target_col):
        return df, {"engineered": True}

    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.apply_cleaning_actions",
        mock_cleaning,
    )
    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.apply_feature_actions",
        mock_features,
    )

    # Mock upload_to_s3 and assert it IS called
    mock_upload = MagicMock()
    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.upload_to_s3",
        mock_upload,
    )

    # Mock build_s3_uri to return a valid S3 path
    monkeypatch.setattr(
        "multi_agent_ds.workflows.preparation.build_s3_uri",
        lambda settings, key, filename: f"s3://bucket/{key}/{filename}",
    )

    # Settings with S3 configuration for upload mode
    settings_with_s3 = {
        "data": {
            "source": "synthetic",
            "synthetic": {
                "target": {
                    "column_name": "target",
                },
            },
        },
        "s3": {
            "bucket": "test-bucket",
            "paths": {
                "processed": "data/processed",
            },
        },
    }

    # Call with default local_only=False
    result = run_preparation_workflow(
        data_path="dummy.parquet",
        prep_plan=minimal_prep_plan,
        settings=settings_with_s3,
    )

    # Assert upload_to_s3 was called exactly once
    assert mock_upload.call_count == 1
