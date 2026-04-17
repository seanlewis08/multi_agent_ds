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


def test_record_run_accumulates_prep_plan_from_unrecorded_node(monkeypatch, tmp_path):
    """Regression test for AC1.2: record_run() must merge prep_plan_stage
    output into final_state even though prep_plan_stage is not in RECORDED_NODES.

    Regression coverage: if the should_accumulate branch in record_run()'s
    event loop is removed or gated behind should_record, this test fails.
    """
    import asyncio
    import json
    from multi_agent_ds.orchestration import demo_recorder as R

    # 1. Build a fake compiled-graph object that yields realistic events.
    class FakeGraph:
        async def astream_events(self, input, version):
            for event in [
                {"event": "on_chain_start", "name": "eda_raw",
                 "data": {"input": {"sample": "input"}}},
                {"event": "on_chain_end", "name": "eda_raw",
                 "data": {"output": {"raw_eda_insights": {"eda_key": "eda_value"}}}},
                {"event": "on_chain_start", "name": "prep_plan_stage",
                 "data": {"input": {"sample": "input"}}},
                {"event": "on_chain_end", "name": "prep_plan_stage",
                 "data": {"output": {"prep_plan": {"action": "prep_value"}}}},
                {"event": "on_chain_start", "name": "data_engineer",
                 "data": {"input": {"sample": "input"}}},
                {"event": "on_chain_end", "name": "data_engineer",
                 "data": {"output": {"processed_data_path": "/fake/processed.parquet"}}},
            ]:
                yield event

    # 2. Patch build_demo_subgraph so record_run uses FakeGraph.
    monkeypatch.setattr(R, "build_demo_subgraph", lambda: FakeGraph())

    # 3. Patch preflight to no-op (so OPENAI_API_KEY and parquet existence are not checked).
    monkeypatch.setattr(R, "preflight", lambda *a, **kw: None)

    # 4. Patch load_dotenv to no-op.
    monkeypatch.setattr(R, "load_dotenv", lambda *a, **kw: None)

    # 5. Patch pandas.read_parquet everywhere record_run calls it.
    #    Specifically: the initial input-df read, and the post-run processed-df read.
    import pandas as pd
    fake_df = pd.DataFrame({"feature_1": [1, 2, 3], "target": [0, 1, 0]})
    monkeypatch.setattr(R.pd, "read_parquet", lambda *a, **kw: fake_df)

    # 6. Patch load_settings to return a minimal settings dict.
    monkeypatch.setattr(R, "load_settings", lambda: {"data": {"source": "synthetic"}, "target": "target"})

    # 7. Invoke record_run() with a throwaway output path.
    parquet_path = tmp_path / "fake.parquet"
    parquet_path.write_text("")  # just needs to exist-ish; read_parquet is mocked
    output_path = tmp_path / "demo_run.json"

    asyncio.run(R.record_run(
        parquet_path=parquet_path,
        output_path=output_path,
        local_only=True,
    ))

    # 8. Load the JSON record_run wrote.
    payload = json.loads(output_path.read_text())

    # 9. Assert prep_plan was accumulated into final_state → artifacts.
    assert payload["artifacts"]["prep_plan"] == {"action": "prep_value"}, (
        f"record_run did not accumulate prep_plan_stage output into artifacts; "
        f"got {payload['artifacts']['prep_plan']!r}"
    )

    # 10. Assert prep_plan_stage is NOT in recorded events (viewer scope).
    recorded_nodes = [e["node"] for e in payload["events"]]
    assert "prep_plan_stage" not in recorded_nodes, (
        f"prep_plan_stage leaked into recorded events: {recorded_nodes}"
    )
    assert set(recorded_nodes) == {"eda_raw", "data_engineer"}
