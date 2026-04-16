"""Minimal routing helpers for the orchestration graph skeleton."""

from __future__ import annotations

from multi_agent_ds.orchestration.state import PipelineState


def route_after_eda(state: PipelineState) -> str:
    """Route from EDA to data engineering or modeling."""
    insights = state.get("eda_insights", {})
    if insights.get("needs_cleaning", False):
        return "data_engineer"
    return "ml_modeler"


def route_after_modeling(state: PipelineState) -> str:
    """Route from modeling back to modeling or forward to evaluation."""
    if state.get("should_loop", False) and state.get("iteration", 0) < 5:
        return "ml_modeler"
    return "evaluation"
