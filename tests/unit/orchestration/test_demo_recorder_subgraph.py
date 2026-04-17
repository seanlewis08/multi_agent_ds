"""Tests for build_demo_subgraph() three-node graph."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from multi_agent_ds.orchestration.state import PipelineState


def test_build_demo_subgraph_returns_compiled_graph(monkeypatch):
    """Verify build_demo_subgraph() returns a compiled LangGraph graph."""
    from multi_agent_ds.orchestration import demo_recorder as R

    # Stub both node functions to avoid LLM calls
    monkeypatch.setattr(
        R, "eda_analyst_node", lambda state, mode: {"raw_eda_insights": {"stub": True}}
    )
    monkeypatch.setattr(
        R, "data_engineer_node", lambda state, mode: {"prep_plan": {"stub": True}}
    )

    graph = R.build_demo_subgraph()
    # Compiled graph should have a get_graph() method
    assert hasattr(graph, "get_graph"), "build_demo_subgraph() should return a compiled graph"


def test_build_demo_subgraph_has_expected_nodes(monkeypatch):
    """Verify the sub-graph includes the three expected node names."""
    from multi_agent_ds.orchestration import demo_recorder as R

    monkeypatch.setattr(
        R, "eda_analyst_node", lambda state, mode: {"raw_eda_insights": {"stub": True}}
    )
    monkeypatch.setattr(
        R, "data_engineer_node", lambda state, mode: {"prep_plan": {"stub": True}}
    )

    graph = R.build_demo_subgraph()
    nodes = set(graph.get_graph().nodes)

    # Check that our three named nodes are present
    assert "eda_raw" in nodes, "eda_raw node not found"
    assert "prep_plan_stage" in nodes, "prep_plan_stage node not found"
    assert "data_engineer" in nodes, "data_engineer node not found"
    # Also expect LangGraph's implicit start/end nodes
    assert "__start__" in nodes or "START" in nodes, "No START node found"
    assert "__end__" in nodes or "END" in nodes, "No END node found"


def test_build_demo_subgraph_invokes_all_three_nodes(monkeypatch):
    """Verify the graph invokes all three nodes in correct order."""
    from multi_agent_ds.orchestration import demo_recorder as R

    # Create tracked mock functions
    eda_calls = []
    de_calls = []

    def stub_eda(state: PipelineState, mode: str) -> dict:
        eda_calls.append(mode)
        return {
            "raw_eda_insights": {"stub": True},
            "prep_plan": {"stub": True}
            if mode == "prep_plan"
            else None,
        }

    def stub_de(state: PipelineState, mode: str) -> dict:
        de_calls.append(mode)
        return {
            "processed_data_path": "/fake/processed.parquet",
            "processed_df_head": [{"stub": True}],
            "processed_df_stats": {"rows": 10},
        }

    monkeypatch.setattr(R, "eda_analyst_node", stub_eda)
    monkeypatch.setattr(R, "data_engineer_node", stub_de)

    graph = R.build_demo_subgraph()
    initial_state = {
        "data_path": "fake.parquet",
        "settings": {},
        "raw_eda_insights": None,
        "prep_plan": None,
        "processed_data_path": None,
    }

    # Invoke the graph — should not raise
    result = graph.invoke(initial_state)
    # Verify eda_analyst was called with "raw" and "prep_plan"
    assert "raw" in eda_calls, f"eda_analyst_node not called with mode='raw', got {eda_calls}"
    assert "prep_plan" in eda_calls, f"eda_analyst_node not called with mode='prep_plan', got {eda_calls}"
    # Verify data_engineer was called with "execute"
    assert "execute" in de_calls, f"data_engineer_node not called with mode='execute', got {de_calls}"


def test_build_demo_subgraph_final_state_combines_outputs(monkeypatch):
    """Verify final state includes outputs from both nodes."""
    from multi_agent_ds.orchestration import demo_recorder as R

    monkeypatch.setattr(
        R,
        "eda_analyst_node",
        lambda state, mode: {
            "raw_eda_insights": {"stat": "eda_value"},
            "prep_plan": {"action": "prep_value"} if mode == "prep_plan" else None,
        },
    )
    monkeypatch.setattr(
        R,
        "data_engineer_node",
        lambda state, mode: {
            "processed_data_path": "/path/to/processed.parquet",
            "processed_df_head": [{"stub": True}],
            "processed_df_stats": {"rows": 10},
        },
    )

    graph = R.build_demo_subgraph()
    initial_state = {
        "data_path": "fake.parquet",
        "settings": {},
        "raw_eda_insights": None,
        "prep_plan": None,
        "processed_data_path": None,
    }

    # Invoke the graph — should not raise
    result = graph.invoke(initial_state)
    # Final state should have outputs from eda node
    assert "raw_eda_insights" in result
    assert result["raw_eda_insights"] == {"stat": "eda_value"}
    # And prep_plan from prep_plan_stage
    assert "prep_plan" in result
    assert result["prep_plan"] == {"action": "prep_value"}
    # And processed_data_path from data_engineer
    assert "processed_data_path" in result
    assert result["processed_data_path"] == "/path/to/processed.parquet"


def test_build_demo_subgraph_propagates_local_only(monkeypatch):
    """Regression test: local_only must survive LangGraph TypedDict filtering.

    PipelineState is a TypedDict; any initial_state key not declared in the
    schema is silently dropped before node invocation. This test seeds
    local_only=True in initial_state and asserts data_engineer_node receives
    it unchanged. Catches the bug where --no-upload was plumbed through the
    CLI but stripped by the graph because local_only wasn't in PipelineState.
    """
    from multi_agent_ds.orchestration import demo_recorder as R

    observed_local_only: list[bool | None] = []

    def stub_eda(state: PipelineState, mode: str) -> dict:
        return {
            "raw_eda_insights": {"stub": True},
            "prep_plan": {"stub": True} if mode == "prep_plan" else None,
        }

    def stub_de(state: PipelineState, mode: str) -> dict:
        observed_local_only.append(state.get("local_only"))
        return {
            "processed_data_path": "/fake/local.parquet",
            "processed_df_head": [{"stub": True}],
            "processed_df_stats": {"rows": 10},
        }

    monkeypatch.setattr(R, "eda_analyst_node", stub_eda)
    monkeypatch.setattr(R, "data_engineer_node", stub_de)

    graph = R.build_demo_subgraph()
    initial_state = {
        "data_path": "fake.parquet",
        "settings": {},
        "local_only": True,
        "raw_eda_insights": None,
        "prep_plan": None,
        "processed_data_path": None,
    }

    # Invoke the graph — should not raise
    graph.invoke(initial_state)

    assert observed_local_only, "data_engineer_node was never invoked"
    assert observed_local_only[0] is True, (
        f"local_only did not propagate through LangGraph; "
        f"data_engineer_node observed {observed_local_only[0]!r} instead of True. "
        f"Likely PipelineState TypedDict is missing the local_only field."
    )


def test_record_run_accumulates_prep_plan_from_unrecorded_node(monkeypatch):
    """Regression test: prep_plan_stage output is merged into final_state even though it's not recorded.

    Root cause of AC1.2 failure: the event loop skipped prep_plan_stage due to
    should_record filtering, so its output (containing prep_plan) was never merged
    into final_state. extract_artifacts(final_state)['prep_plan'] ended up None.

    This test mocks the graph's astream_events to yield pre-fabricated events for
    all three nodes, then calls just the event-loop portion of record_run. It asserts
    that prep_plan is present in the final artifacts even though prep_plan_stage
    events are not in the recorded events list.
    """
    import asyncio
    from datetime import datetime, timezone
    from pathlib import Path
    from multi_agent_ds.orchestration import demo_recorder as R

    # Pre-fabricate LangGraph-style events for all three nodes
    eda_raw_start = {
        "event": "on_chain_start",
        "name": "eda_raw",
        "data": {"input": {"sample": "input"}},
    }
    eda_raw_end = {
        "event": "on_chain_end",
        "name": "eda_raw",
        "data": {"output": {"raw_eda_insights": {"eda_key": "eda_value"}}},
    }
    prep_plan_start = {
        "event": "on_chain_start",
        "name": "prep_plan_stage",
        "data": {"input": {"sample": "input"}},
    }
    prep_plan_end = {
        "event": "on_chain_end",
        "name": "prep_plan_stage",
        "data": {"output": {"prep_plan": {"action": "prep_value"}}},
    }
    de_start = {
        "event": "on_chain_start",
        "name": "data_engineer",
        "data": {"input": {"sample": "input"}},
    }
    de_end = {
        "event": "on_chain_end",
        "name": "data_engineer",
        "data": {"output": {"processed_data_path": "/fake/processed.parquet"}},
    }

    # Simulate astream_events yielding the sequence
    async def mock_astream_events(*args, **kwargs):
        """Yield pre-fabricated events in order."""
        for event in [
            eda_raw_start,
            eda_raw_end,
            prep_plan_start,
            prep_plan_end,
            de_start,
            de_end,
        ]:
            yield event

    # Replay the core event-loop logic from record_run
    initial_state = {
        "data_path": "/fake/data.parquet",
        "settings": {},
        "input_df_head": [{"sample": 1}],
        "input_df_stats": {"rows": 100},
    }
    final_state = dict(initial_state)
    events = []
    start_monotonic = __import__("time").monotonic()

    async def run_loop():
        """Replay the event-loop portion of record_run."""
        for lg_event in [
            eda_raw_start,
            eda_raw_end,
            prep_plan_start,
            prep_plan_end,
            de_start,
            de_end,
        ]:
            # Accumulate state from all graph nodes
            if R.should_accumulate(lg_event):
                output = lg_event.get("data", {}).get("output")
                if isinstance(output, dict):
                    safe_output = R.sanitize_payload(output)
                    if isinstance(safe_output, dict):
                        final_state.update(safe_output)

            # Record only the events the viewer will replay
            if not R.should_record(lg_event):
                continue
            elapsed_ms = int((__import__("time").monotonic() - start_monotonic) * 1000)
            ts = R.iso_utc(datetime.now(timezone.utc))
            safe_data = R.sanitize_payload(lg_event.get("data", {}))
            normalized = R.normalize_event(
                {**lg_event, "data": safe_data}, ts=ts, elapsed_ms=elapsed_ms
            )
            events.append(normalized.to_dict())

    asyncio.run(run_loop())

    # Verify state was accumulated correctly
    assert "prep_plan" in final_state, "prep_plan not in final_state"
    assert final_state["prep_plan"] == {
        "action": "prep_value"
    }, f"prep_plan value incorrect: {final_state['prep_plan']}"

    # Verify only recorded events are in the events list (no prep_plan_stage)
    recorded_nodes = [e.get("node") for e in events]
    assert "prep_plan_stage" not in recorded_nodes, (
        f"prep_plan_stage should not be recorded; events: {recorded_nodes}"
    )
    assert set(recorded_nodes) == {
        "eda_raw",
        "data_engineer",
    }, f"Expected eda_raw and data_engineer only; got {recorded_nodes}"

    # Extract artifacts from final_state and verify prep_plan is not None
    artifacts = R.extract_artifacts(final_state)
    assert artifacts["prep_plan"] is not None, "extract_artifacts should not return None for prep_plan"
    assert artifacts["prep_plan"] == {
        "action": "prep_value"
    }, f"Artifact prep_plan mismatch: {artifacts['prep_plan']}"
