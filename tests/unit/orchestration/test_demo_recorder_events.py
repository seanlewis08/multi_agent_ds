"""Tests for demo_recorder event normalization helpers."""
from datetime import datetime, timezone

from multi_agent_ds.orchestration.demo_recorder import (
    iso_utc,
    langgraph_event_kind,
    normalize_event,
    should_record,
)


def test_iso_utc_format():
    """iso_utc formats a datetime as ISO-8601 with 'Z' suffix and millisecond precision."""
    now = datetime(2026, 4, 16, 14, 3, 22, 456789, tzinfo=timezone.utc)
    result = iso_utc(now)
    assert result == "2026-04-16T14:03:22.456Z"


def test_langgraph_event_kind_mappings():
    """langgraph_event_kind translates LangGraph event strings or returns None."""
    assert langgraph_event_kind("on_chain_start") == "node_start"
    assert langgraph_event_kind("on_chain_end") == "node_end"
    assert langgraph_event_kind("on_chain_error") == "node_error"
    # Unmapped events return None
    assert langgraph_event_kind("on_chat_model_start") is None
    assert langgraph_event_kind("on_llm_start") is None
    assert langgraph_event_kind("garbage") is None


def test_should_record_filters_by_event_and_node():
    """should_record returns True only for chain events on recorded nodes."""
    # Should record: on_chain_start for eda_raw
    assert should_record({"event": "on_chain_start", "name": "eda_raw"}) is True
    # Should record: on_chain_end for data_engineer
    assert should_record({"event": "on_chain_end", "name": "data_engineer"}) is True
    # Should not record: chain event but wrong node
    assert should_record({"event": "on_chain_start", "name": "orchestrator"}) is False
    # Should not record: correct node but wrong event kind
    assert should_record({"event": "on_llm_start", "name": "eda_raw"}) is False


def test_normalize_event_shape():
    """normalize_event converts a LangGraph event dict to NormalizedEvent with correct shape."""
    lg_event = {
        "event": "on_chain_start",
        "name": "eda_raw",
        "data": {"input": {"key": "value"}},
    }
    result = normalize_event(lg_event, ts="2026-04-16T14:03:22.456Z", elapsed_ms=42)
    result_dict = result.to_dict()

    # Check all five keys are present
    assert set(result_dict.keys()) == {"ts", "elapsed_ms", "kind", "node", "data"}
    assert result_dict["ts"] == "2026-04-16T14:03:22.456Z"
    assert result_dict["elapsed_ms"] == 42
    assert result_dict["kind"] == "node_start"
    assert result_dict["node"] == "eda_raw"
    assert result_dict["data"] == {"input": {"key": "value"}}
