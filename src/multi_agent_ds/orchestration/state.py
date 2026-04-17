"""Shared state schema for the LangGraph orchestration layer."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


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
    modeling_verdict: dict[str, Any]
    ml_review: dict[str, Any]
    evaluation_result: dict[str, Any]
    reviewer_summary: dict[str, Any]
    shap_results: dict[str, Any]
    shap_artifacts: dict[str, Any]
    mlflow_payload: dict[str, Any]
    report_draft: str
    experiment_report: str
    business_review: dict[str, Any]
    dry_run: bool
    branch_name: str
    staged_paths: list[str]
    commit_message: str
    pr_title: str
    pr_body: str
    base_branch: str
    commit_sha: str | None
    pr_metadata: dict[str, Any]
    pr_number: int | None
    pr_url: str | None

    # Control flow
    agent_decisions: Annotated[list[dict[str, Any]], operator.add]
    current_phase: str
    should_loop: bool
    loop_from: str
    should_revise_modeling: bool
    should_revise_report: bool
    iteration: int
    modeling_iteration: int
    report_iteration: int
