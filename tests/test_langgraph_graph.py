from __future__ import annotations

import pytest
from langgraph.graph.state import CompiledStateGraph, StateGraph

from multi_agent_ds.orchestration.graph import build_graph


def test_build_graph_returns_state_graph() -> None:
    graph = build_graph()

    assert isinstance(graph, StateGraph)
    assert "eda_raw" in graph.nodes
    assert "data_engineer_execute" in graph.nodes
    assert "ml_modeler_handoff" in graph.nodes


def test_build_graph_compiles() -> None:
    compiled = build_graph().compile()

    assert isinstance(compiled, CompiledStateGraph)


@pytest.mark.parametrize(
    "node_name",
    [
        "ml_modeler_baseline",
        "ml_reviewer_baseline_review",
        "ml_modeler_n_estimator_search",
        "ml_modeler_tune",
        "ml_reviewer_tuning_review",
        "ml_modeler_train_tuned",
        "ml_modeler_adjust_lr",
        "ml_reviewer_lr_adjustment_review",
        "ml_modeler_importance_review",
        "ml_modeler_feature_selection",
        "ml_reviewer_feature_selection_review",
        "ml_modeler_final_recommendation",
        "ml_reviewer_final_recommendation_review",
    ],
)
def test_modeling_loop_nodes_are_registered(node_name: str) -> None:
    graph = build_graph()
    assert node_name in graph.nodes


def test_modeling_loop_graph_compiles_end_to_end() -> None:
    """The full graph (pre-modeling EDA loop + modeling loop) must compile."""
    compiled = build_graph().compile()
    assert isinstance(compiled, CompiledStateGraph)
