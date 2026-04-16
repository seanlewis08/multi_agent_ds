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
    """Route from modeling back to modeling or forward to ML review."""
    if state.get("should_loop", False) and state.get("iteration", 0) < 5:
        return "ml_modeler"
    return "ml_reviewer"


def route_after_ml_review(state: PipelineState) -> str:
    """Route from ML review to evaluation or back to modeling."""
    review = state.get("ml_review", {})
    if review.get("next_action") == "revise_modeling":
        return "ml_modeler"
    return "evaluation"


def route_after_business_review(state: PipelineState) -> str:
    """Route from business review to end, report revision, or modeling revision."""
    review = state.get("business_review", {})
    next_action = review.get("next_action", "accept")
    if next_action == "revise_report":
        return "report"
    if next_action == "revise_modeling":
        return "ml_modeler"
    return "end"
