"""Shared state schema for the LangGraph orchestration layer."""

from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    """State passed between orchestration graph nodes."""

    # Data references
    data_path: str
    data: dict[str, Any]
    settings: dict[str, Any]
    workflow_config: dict[str, Any]

    # Agent outputs
    eda_insights: dict[str, Any]
    raw_eda_insights: dict[str, Any]
    raw_eda_ml_modeler_review: dict[str, Any]
    raw_eda_ml_review: dict[str, Any]
    raw_eda_business_review: dict[str, Any]
    prep_plan: dict[str, Any]
    prep_feedback: dict[str, Any]
    prep_approved: bool
    prep_iteration: int
    prep_result: dict[str, Any]
    processed_data_path: str
    processed_eda_insights: dict[str, Any]
    processed_eda_ml_modeler_review: dict[str, Any]
    processed_eda_ml_review: dict[str, Any]
    processed_eda_business_review: dict[str, Any]
    processed_eda_approved: bool
    modeling_context: dict[str, Any]
    modeling_results: dict[str, Any]
    ml_review: dict[str, Any]
    evaluation_result: dict[str, Any]
    report_draft: str
    experiment_report: str
    business_review: dict[str, Any]

    # Control flow
    agent_decisions: list[dict[str, Any]]
    current_phase: str
    should_loop: bool
    iteration: int
