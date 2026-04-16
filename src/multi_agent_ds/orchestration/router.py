"""Routing helpers for the expanded pre-modeling EDA workflow."""

from __future__ import annotations

from multi_agent_ds.core import load_workflows_config
from multi_agent_ds.orchestration.state import PipelineState

_MODELING_REVIEW_NEXT_NODE = {
    "baseline": "ml_modeler_n_estimator_search",
    "tune": "ml_modeler_train_tuned",
    "adjust_lr": "ml_modeler_importance_review",
    "feature_selection": "ml_modeler_final_recommendation",
    "final_recommendation": "end",
}


def _prep_iteration_limit() -> int:
    workflow_cfg = load_workflows_config()
    return int(workflow_cfg.get("workflows", {}).get("eda_preparation", {}).get("max_iterations", 3))


def _modeling_iteration_limit() -> int:
    workflow_cfg = load_workflows_config()
    return int(workflow_cfg.get("workflows", {}).get("modeling", {}).get("max_iterations", 3))


def route_after_raw_eda(_state: PipelineState) -> tuple[str, str, str]:
    """Fan raw EDA out to all three reviewers."""
    return (
        "ml_modeler_raw_review",
        "ml_reviewer_raw_review",
        "business_stakeholder_raw_review",
    )


def route_after_prep_plan(state: PipelineState) -> str:
    """Either execute an approved plan or keep iterating with the data engineer."""
    if state.get("prep_approved", False):
        return "data_engineer_execute"
    return "data_engineer_feedback"


def route_after_data_engineer_feedback(_state: PipelineState) -> str:
    """Return feasibility feedback to the EDA analyst for the next plan iteration."""
    return "eda_prep_plan"


def route_after_data_engineer_execute(_state: PipelineState) -> str:
    """Profile the processed dataset after the approved prep plan runs."""
    return "eda_processed"


def route_after_processed_eda(_state: PipelineState) -> tuple[str, str, str]:
    """Fan processed EDA out to all three reviewers."""
    return (
        "ml_modeler_processed_review",
        "ml_reviewer_processed_review",
        "business_stakeholder_processed_review",
    )


def route_after_processed_approval(state: PipelineState) -> str:
    """Either hand the approved data to modeling or reopen the prep loop."""
    if state.get("processed_eda_approved", False):
        return "ml_modeler_handoff"
    if state.get("prep_iteration", 0) < _prep_iteration_limit():
        return "eda_prep_plan"
    return "end"


def route_after_modeling_handoff(_state: PipelineState) -> str:
    """Stop after the final modeling handoff package is assembled."""
    return "end"


def route_after_modeling_review(state: PipelineState) -> str:
    """Route after a reviewer verdict on a modeling phase.

    Loops back to the reviewed modeler mode when the reviewer flagged
    `should_revise_modeling` AND the modeling-loop iteration counter is still
    under the configured cap. Otherwise advances to the next modeling phase.
    `current_phase` is set by the modeler to the phase name (e.g. "baseline",
    "tune") and stays set through the reviewer run.
    """
    current = state.get("current_phase")
    if current not in _MODELING_REVIEW_NEXT_NODE:
        raise ValueError(f"Unknown modeling review phase: {current!r}")

    revise = state.get("should_revise_modeling", False)
    iteration = state.get("modeling_iteration", 0)
    if revise and iteration < _modeling_iteration_limit():
        return f"ml_modeler_{current}"
    return _MODELING_REVIEW_NEXT_NODE[current]
