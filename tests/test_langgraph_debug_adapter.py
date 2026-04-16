from __future__ import annotations

from multi_agent_ds.adapters.agent_frameworks.langgraph import (
    collect_graph_events,
    get_debug_graph,
    render_graph_ascii,
    render_graph_mermaid,
)
from multi_agent_ds.orchestration.graph import build_graph


def test_get_debug_graph_returns_graph_object() -> None:
    compiled = build_graph().compile()

    graph = get_debug_graph(compiled, xray=True)

    assert hasattr(graph, "nodes")
    assert hasattr(graph, "edges")
    assert "eda_raw" in graph.nodes


def test_render_graph_ascii_returns_non_empty_output() -> None:
    compiled = build_graph().compile()

    ascii_output = render_graph_ascii(compiled, xray=True)

    assert isinstance(ascii_output, str)
    assert "eda_raw" in ascii_output
    assert "ml_modeler_raw_review" in ascii_output


def test_render_graph_mermaid_returns_non_empty_output() -> None:
    compiled = build_graph().compile()

    mermaid_output = render_graph_mermaid(compiled, xray=True)

    assert isinstance(mermaid_output, str)
    assert "eda_raw" in mermaid_output
    assert "business_stakeholder_processed_review" in mermaid_output


def test_collect_graph_events_collects_async_events_from_compiled_graph() -> None:
    class FakeCompiledGraph:
        async def astream_events(self, _input_state, **kwargs):
            yield {"event": "on_chain_start", "name": "eda_raw", "kwargs": kwargs}
            yield {"event": "on_chain_end", "name": "eda_prep_plan", "kwargs": kwargs}

    events = collect_graph_events(
        FakeCompiledGraph(),
        {"data_path": "data/raw/example.parquet"},
        include_names=["eda_raw", "eda_prep_plan"],
    )

    assert len(events) == 2
    assert events[0]["name"] == "eda_raw"
    assert events[0]["kwargs"]["include_names"] == ["eda_raw", "eda_prep_plan"]
