"""Tests for --no-upload CLI flag in demo_recorder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from multi_agent_ds.orchestration import demo_recorder


def test_main_no_upload_flag(tmp_path, monkeypatch):
    """CLI --no-upload flag should be parsed and passed to record_run."""
    import asyncio

    # Create a minimal fake parquet
    import pandas as pd
    df = pd.DataFrame({
        "feature_1": [1.0, 2.0],
        "target": [0, 1],
    })
    parquet_path = tmp_path / "input.parquet"
    df.to_parquet(parquet_path)

    output_path = tmp_path / "output.json"

    # Mock record_run to capture kwargs
    mock_record_run = AsyncMock(return_value={
        "events": [],
        "artifacts": {},
        "duration_ms": 100,
    })
    monkeypatch.setattr(demo_recorder, "record_run", mock_record_run)

    # Call main with --no-upload flag
    argv = [
        "--parquet", str(parquet_path),
        "--output", str(output_path),
        "--no-upload",
    ]
    exit_code = demo_recorder.main(argv)

    # Verify exit code is 0
    assert exit_code == 0

    # Verify record_run was called with local_only=True
    assert mock_record_run.call_count == 1
    call_kwargs = mock_record_run.call_args[1]
    assert call_kwargs.get("local_only") is True


def test_main_without_no_upload_flag(tmp_path, monkeypatch):
    """CLI without --no-upload flag should default to local_only=False."""
    import asyncio

    # Create a minimal fake parquet
    import pandas as pd
    df = pd.DataFrame({
        "feature_1": [1.0, 2.0],
        "target": [0, 1],
    })
    parquet_path = tmp_path / "input.parquet"
    df.to_parquet(parquet_path)

    output_path = tmp_path / "output.json"

    # Mock record_run to capture kwargs
    mock_record_run = AsyncMock(return_value={
        "events": [],
        "artifacts": {},
        "duration_ms": 100,
    })
    monkeypatch.setattr(demo_recorder, "record_run", mock_record_run)

    # Call main WITHOUT --no-upload flag
    argv = [
        "--parquet", str(parquet_path),
        "--output", str(output_path),
    ]
    exit_code = demo_recorder.main(argv)

    # Verify exit code is 0
    assert exit_code == 0

    # Verify record_run was called with local_only=False (default)
    assert mock_record_run.call_count == 1
    call_kwargs = mock_record_run.call_args[1]
    assert call_kwargs.get("local_only") is False


def test_main_resolves_parquet_from_settings(tmp_path, monkeypatch):
    """CLI without --parquet should resolve from settings via resolve_data_path."""
    import pandas as pd

    # Create a minimal fake parquet
    df = pd.DataFrame({
        "feature_1": [1.0, 2.0],
        "target": [0, 1],
    })
    synthetic_parquet = tmp_path / "synthetic.parquet"
    df.to_parquet(synthetic_parquet)

    output_path = tmp_path / "output.json"

    # Mock resolve_data_path to return our test parquet
    monkeypatch.setattr(
        demo_recorder,
        "resolve_data_path",
        lambda data_path, settings: str(synthetic_parquet),
    )

    # Mock record_run to capture kwargs
    mock_record_run = AsyncMock(return_value={
        "events": [],
        "artifacts": {},
        "duration_ms": 100,
    })
    monkeypatch.setattr(demo_recorder, "record_run", mock_record_run)

    # Call main WITHOUT --parquet flag (should resolve via settings)
    argv = ["--output", str(output_path)]
    exit_code = demo_recorder.main(argv)

    # Verify exit code is 0
    assert exit_code == 0

    # Verify record_run was called with the resolved parquet path
    assert mock_record_run.call_count == 1
    call_kwargs = mock_record_run.call_args[1]
    assert call_kwargs["parquet_path"] == Path(synthetic_parquet)
