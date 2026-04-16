from __future__ import annotations

from langgraph.graph.state import CompiledStateGraph, StateGraph

from multi_agent_ds.orchestration.graph import build_graph


def test_build_graph_returns_state_graph() -> None:
    graph = build_graph()

    assert isinstance(graph, StateGraph)
    assert "ml_reviewer" in graph.nodes
    assert "business_stakeholder" in graph.nodes


def test_build_graph_compiles() -> None:
    compiled = build_graph().compile()

    assert isinstance(compiled, CompiledStateGraph)
