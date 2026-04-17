"""Tests for _build_demo_graph() — the full 13-node pre-modeling workflow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from multi_agent_ds.orchestration.state import PipelineState


def test_build_demo_graph_returns_compiled_graph(monkeypatch):
    """Verify _build_demo_graph() returns a compiled LangGraph graph."""
    from multi_agent_ds.orchestration import demo_recorder as R

    # Patch build_graph to return a mock compiled graph
    mock_graph = MagicMock()
    mock_graph.compile.return_value = MagicMock(get_graph=MagicMock())
    monkeypatch.setattr(R, "build_graph", lambda: mock_graph)

    graph = R._build_demo_graph()
    # Compiled graph should have a get_graph() method
    assert hasattr(graph, "get_graph"), "_build_demo_graph() should return a compiled graph"


def test_build_demo_graph_delegates_to_build_graph(monkeypatch):
    """Verify _build_demo_graph() delegates to build_graph() from graph.py."""
    from multi_agent_ds.orchestration import demo_recorder as R

    # Track whether build_graph was called
    calls = []

    def mock_build_graph():
        calls.append(True)
        mock_compiled = MagicMock()
        mock_compiled.get_graph = MagicMock(return_value=MagicMock(nodes=set()))
        return mock_compiled

    monkeypatch.setattr(R, "build_graph", mock_build_graph)

    graph = R._build_demo_graph()

    assert len(calls) == 1, "_build_demo_graph() should call build_graph() once"


def test_recorded_nodes_contains_13_pre_modeling_nodes():
    """Verify RECORDED_NODES has exactly the 13 pre-modeling nodes."""
    from multi_agent_ds.orchestration import demo_recorder as R

    expected_nodes = frozenset({
        "eda_raw",
        "ml_modeler_raw_review",
        "ml_reviewer_raw_review",
        "business_stakeholder_raw_review",
        "eda_prep_plan",
        "data_engineer_feedback",
        "data_engineer_execute",
        "eda_processed",
        "ml_modeler_processed_review",
        "ml_reviewer_processed_review",
        "business_stakeholder_processed_review",
        "eda_processed_approval",
        "ml_modeler_handoff",
    })

    assert R.RECORDED_NODES == expected_nodes, (
        f"RECORDED_NODES mismatch. Expected {expected_nodes}, got {R.RECORDED_NODES}"
    )
    assert len(R.RECORDED_NODES) == 13, (
        f"RECORDED_NODES should have 13 nodes, got {len(R.RECORDED_NODES)}"
    )


def test_accumulate_nodes_equals_recorded_nodes():
    """Verify ACCUMULATE_NODES == RECORDED_NODES for the 13-node workflow."""
    from multi_agent_ds.orchestration import demo_recorder as R

    assert R.ACCUMULATE_NODES == R.RECORDED_NODES, (
        f"ACCUMULATE_NODES ({R.ACCUMULATE_NODES}) should equal "
        f"RECORDED_NODES ({R.RECORDED_NODES}) for 13-node workflow"
    )


def test_recorded_nodes_subset_of_accumulate_nodes_invariant():
    """Verify the invariant: RECORDED_NODES ⊆ ACCUMULATE_NODES."""
    from multi_agent_ds.orchestration import demo_recorder as R

    assert R.RECORDED_NODES.issubset(R.ACCUMULATE_NODES), (
        f"RECORDED_NODES {R.RECORDED_NODES - R.ACCUMULATE_NODES} are not in ACCUMULATE_NODES; "
        "invariant violated."
    )


def test_record_run_accumulates_all_13_pre_modeling_nodes(monkeypatch, tmp_path):
    """Integration test: record_run() accumulates all 13 pre-modeling nodes
    and stops at ml_modeler_handoff (no post-modeling nodes recorded).

    Regression coverage: With the 13-node workflow, RECORDED_NODES ==
    ACCUMULATE_NODES, so all pre-modeling nodes are both recorded and
    accumulated. Post-modeling nodes (e.g., ml_modeler_baseline) should
    be ignored by the recorder because they are not in RECORDED_NODES.
    """
    import asyncio
    import json
    from multi_agent_ds.orchestration import demo_recorder as R

    # Build a fake graph that yields events from the 13 pre-modeling nodes
    # plus a post-modeling node (which should be ignored).
    class FakeGraph:
        async def astream_events(self, input, version):
            for event in [
                {"event": "on_chain_start", "name": "eda_raw",
                 "data": {"input": {}}},
                {"event": "on_chain_end", "name": "eda_raw",
                 "data": {"output": {"raw_eda_insights": {"key": "value"}}}},
                {"event": "on_chain_start", "name": "ml_modeler_raw_review",
                 "data": {"input": {}}},
                {"event": "on_chain_end", "name": "ml_modeler_raw_review",
                 "data": {"output": {"raw_eda_ml_modeler_review": {"key": "value"}}}},
                {"event": "on_chain_end", "name": "ml_modeler_handoff",
                 "data": {"output": {"modeling_context": {"key": "value"}}}},
                # Post-modeling nodes should be ignored (not in RECORDED_NODES)
                {"event": "on_chain_start", "name": "ml_modeler_baseline",
                 "data": {"input": {}}},
                {"event": "on_chain_end", "name": "ml_modeler_baseline",
                 "data": {"output": {"modeling_results": {"key": "value"}}}},
            ]:
                yield event

    # Patch _build_demo_graph so record_run uses FakeGraph.
    monkeypatch.setattr(R, "_build_demo_graph", lambda: FakeGraph())

    # Patch preflight to no-op.
    monkeypatch.setattr(R, "preflight", lambda *a, **kw: None)

    # Patch load_dotenv to no-op.
    monkeypatch.setattr(R, "load_dotenv", lambda *a, **kw: None)

    # Patch pandas.read_parquet.
    import pandas as pd
    fake_df = pd.DataFrame({"feature_1": [1, 2, 3], "target": [0, 1, 0]})
    monkeypatch.setattr(R.pd, "read_parquet", lambda *a, **kw: fake_df)

    # Patch load_settings.
    monkeypatch.setattr(R, "load_settings", lambda: {"data": {"source": "synthetic"}, "target": "target"})

    # Invoke record_run().
    parquet_path = tmp_path / "fake.parquet"
    parquet_path.write_text("")
    output_path = tmp_path / "demo_run.json"

    asyncio.run(R.record_run(
        parquet_path=parquet_path,
        output_path=output_path,
        local_only=True,
    ))

    # Load and verify the JSON.
    payload = json.loads(output_path.read_text())

    # Verify only pre-modeling nodes are recorded
    recorded_nodes = [e["node"] for e in payload["events"]]
    assert "ml_modeler_baseline" not in recorded_nodes, (
        f"Post-modeling node ml_modeler_baseline leaked into recorded events: {recorded_nodes}"
    )

    # Verify ml_modeler_handoff is the last recorded node
    assert "ml_modeler_handoff" in recorded_nodes, (
        f"ml_modeler_handoff should be recorded: {recorded_nodes}"
    )
    assert recorded_nodes[-1] == "ml_modeler_handoff", (
        f"ml_modeler_handoff should be the last recorded node, but got {recorded_nodes[-1]} at end"
    )
