"""Minimal LangGraph skeleton for the shared orchestration layer."""

from __future__ import annotations

from langgraph.graph import END
from langgraph.graph.state import StateGraph

from multi_agent_ds.orchestration.router import (
    route_after_business_review,
    route_after_eda,
    route_after_ml_review,
    route_after_modeling,
)
from multi_agent_ds.orchestration.state import PipelineState


def _eda_node(state: PipelineState) -> dict:
    """Placeholder EDA node for the initial graph skeleton."""
    return state


def _data_engineer_node(state: PipelineState) -> dict:
    """Placeholder data engineering node for the initial graph skeleton."""
    return state


def _ml_modeler_node(state: PipelineState) -> dict:
    """Placeholder modeling node for the initial graph skeleton."""
    return state


def _evaluation_node(state: PipelineState) -> dict:
    """Placeholder evaluation node for the initial graph skeleton."""
    return state


def _ml_reviewer_node(state: PipelineState) -> dict:
    """Placeholder ML reviewer node for the initial graph skeleton."""
    return state


def _reviewer_node(state: PipelineState) -> dict:
    """Placeholder reviewer node for the initial graph skeleton."""
    return state


def _report_node(state: PipelineState) -> dict:
    """Placeholder report node for the initial graph skeleton."""
    return state


def _business_stakeholder_node(state: PipelineState) -> dict:
    """Placeholder business stakeholder node for the initial graph skeleton."""
    return state


def build_graph() -> StateGraph:
    """Build the shared LangGraph state graph skeleton."""
    graph = StateGraph(PipelineState)

    graph.add_node("eda", _eda_node)
    graph.add_node("data_engineer", _data_engineer_node)
    graph.add_node("ml_modeler", _ml_modeler_node)
    graph.add_node("ml_reviewer", _ml_reviewer_node)
    graph.add_node("evaluation", _evaluation_node)
    graph.add_node("reviewer", _reviewer_node)
    graph.add_node("report", _report_node)
    graph.add_node("business_stakeholder", _business_stakeholder_node)

    graph.set_entry_point("eda")
    graph.add_conditional_edges(
        "eda",
        route_after_eda,
        {
            "data_engineer": "data_engineer",
            "ml_modeler": "ml_modeler",
        },
    )
    graph.add_conditional_edges(
        "ml_modeler",
        route_after_modeling,
        {
            "ml_modeler": "ml_modeler",
            "ml_reviewer": "ml_reviewer",
        },
    )
    graph.add_conditional_edges(
        "ml_reviewer",
        route_after_ml_review,
        {
            "ml_modeler": "ml_modeler",
            "evaluation": "evaluation",
        },
    )
    graph.add_conditional_edges(
        "business_stakeholder",
        route_after_business_review,
        {
            "report": "report",
            "ml_modeler": "ml_modeler",
            "end": END,
        },
    )
    graph.add_edge("data_engineer", "ml_modeler")
    graph.add_edge("evaluation", "reviewer")
    graph.add_edge("reviewer", "report")
    graph.add_edge("report", "business_stakeholder")

    return graph
