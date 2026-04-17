"""Tests for demo_recorder artifact extraction and payload sanitization."""
import pandas as pd

from multi_agent_ds.orchestration.demo_recorder import (
    extract_artifacts,
    sanitize_payload,
)


def test_extract_artifacts_all_keys():
    """extract_artifacts returns a dict with all six keys when present."""
    final_state = {
        "raw_eda_insights": {"x": 1},
        "prep_plan": {"y": 2},
        "processed_df_head": [{"a": 1}],
        "processed_df_stats": {"rows": 10},
        "input_df_head": [{"b": 2}],
        "input_df_stats": {"rows": 10},
    }
    result = extract_artifacts(final_state)
    assert set(result.keys()) == {
        "raw_eda_insights",
        "prep_plan",
        "processed_df_head",
        "processed_df_stats",
        "input_df_head",
        "input_df_stats",
    }
    assert result["raw_eda_insights"] == {"x": 1}
    assert result["prep_plan"] == {"y": 2}
    assert result["processed_df_head"] == [{"a": 1}]
    assert result["processed_df_stats"] == {"rows": 10}
    assert result["input_df_head"] == [{"b": 2}]
    assert result["input_df_stats"] == {"rows": 10}


def test_extract_artifacts_missing_keys_become_none():
    """extract_artifacts returns None for missing keys (no KeyError)."""
    final_state = {}
    result = extract_artifacts(final_state)
    assert set(result.keys()) == {
        "raw_eda_insights",
        "prep_plan",
        "processed_df_head",
        "processed_df_stats",
        "input_df_head",
        "input_df_stats",
    }
    assert all(v is None for v in result.values())


def test_sanitize_payload_passes_primitives():
    """sanitize_payload passes primitives through unchanged."""
    payload = {"a": 1, "b": [1, 2.0, "three"], "c": True, "d": None}
    result = sanitize_payload(payload)
    assert result == payload


def test_sanitize_payload_strips_dataframe():
    """sanitize_payload converts DataFrames to their repr-truncated string."""
    df = pd.DataFrame({"x": [1, 2]})
    result = sanitize_payload(df)
    assert isinstance(result, str)
    # The result should not be the DataFrame itself; it's a string
    # Check that it's not empty and is a reasonable truncation
    assert len(result) > 0


def test_sanitize_payload_max_depth():
    """sanitize_payload respects max_depth and uses <max-depth> marker."""
    nested = {"nested": {"deep": {"level": 7}}}
    result = sanitize_payload(nested, max_depth=2)
    # At depth 2, we hit the inner "level" key with value 7. That becomes <max-depth: int>
    assert "<max-depth:" in str(result)
