"""Tests for preflight() guard function."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_preflight_raises_environment_error_when_api_key_missing(monkeypatch, tmp_path):
    """Verify preflight() raises EnvironmentError if OPENAI_API_KEY is unset."""
    from multi_agent_ds.orchestration import demo_recorder as R

    # Ensure OPENAI_API_KEY is not set
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Create a fake parquet file so the only failure is the missing API key
    parquet_path = tmp_path / "input.parquet"
    parquet_path.write_text("fake")

    # Should raise EnvironmentError
    with pytest.raises(EnvironmentError) as exc_info:
        R.preflight(parquet_path=parquet_path)

    # Message should mention OPENAI_API_KEY
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_preflight_raises_file_not_found_when_parquet_missing(monkeypatch):
    """Verify preflight() raises FileNotFoundError if parquet_path doesn't exist."""
    from multi_agent_ds.orchestration import demo_recorder as R

    # Ensure OPENAI_API_KEY is set
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

    # Use a path that doesn't exist
    missing_parquet = Path("/tmp/does-not-exist-test-file-xyz.parquet")

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError) as exc_info:
        R.preflight(parquet_path=missing_parquet)

    # Message should include the resolved path
    error_msg = str(exc_info.value)
    assert "parquet" in error_msg.lower() or "parquet" in error_msg


def test_preflight_returns_none_when_both_present(monkeypatch, tmp_path):
    """Verify preflight() returns None (no exception) when both conditions are met."""
    from multi_agent_ds.orchestration import demo_recorder as R

    # Set API key
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

    # Create real parquet file
    parquet_path = tmp_path / "input.parquet"
    parquet_path.write_text("fake parquet content")

    # Should not raise any exception
    result = R.preflight(parquet_path=parquet_path)
    assert result is None, "preflight() should return None on success"
