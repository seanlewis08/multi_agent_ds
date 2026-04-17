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
    # Outer-loop rejection context carried into the next eda_prep_plan turn so
    # the analyst's retry prompt has fresh signal (concerns + recommendations
    # from the most recent processed_approval=False verdict).
    processed_approval_concerns: list[str]
    processed_approval_recommendations: list[str]
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
    # `agent_decisions` is reduced with `operator.add`. Nodes MUST return only
    # the NEW entries they are contributing (the delta), not the full list —
    # the reducer concatenates with the current channel value. Returning the
    # full existing list causes exponential duplication across fan-out and
    # serial nodes (see LANGGRAPH_DEBUGGING.md / demo recorder bloat).
    agent_decisions: Annotated[list[dict[str, Any]], operator.add]
    current_phase: str
    should_loop: bool
    loop_from: str
    should_revise_modeling: bool
    should_revise_report: bool
    iteration: int
    modeling_iteration: int
    report_iteration: int

    # Demo recorder offline-mode flag (skips S3 upload, writes parquet locally).
    # Set only by the demo recorder's --no-upload flag; default False preserves
    # production behaviour. Consumed by data_engineer_node mode="execute".
    local_only: bool
