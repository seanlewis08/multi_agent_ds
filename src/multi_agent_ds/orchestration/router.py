"""Routing helpers for the expanded pre-modeling EDA workflow."""

from __future__ import annotations

from multi_agent_ds.core import load_workflows_config
from multi_agent_ds.orchestration.state import PipelineState


def _prep_iteration_limit() -> int:
    workflow_cfg = load_workflows_config()
    return int(workflow_cfg.get("workflows", {}).get("eda_preparation", {}).get("max_iterations", 3))


def route_after_raw_eda(_state: PipelineState) -> str:
    """Send freshly produced raw EDA to the first downstream reviewer."""
    return "ml_modeler_raw_review"


def route_after_ml_modeler_raw_review(_state: PipelineState) -> str:
    """Continue the raw-review sequence after the modeler review."""
    return "ml_reviewer_raw_review"


def route_after_ml_reviewer_raw_review(_state: PipelineState) -> str:
    """Continue the raw-review sequence after the ML reviewer."""
    return "business_stakeholder_raw_review"


def route_after_business_raw_review(_state: PipelineState) -> str:
    """Fan reviews back in to the EDA analyst for prep planning."""
    return "eda_prep_plan"


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


def route_after_processed_eda(_state: PipelineState) -> str:
    """Send processed-data EDA through the same reviewer sequence."""
    return "ml_modeler_processed_review"


def route_after_ml_modeler_processed_review(_state: PipelineState) -> str:
    """Continue the processed-review sequence after the modeler review."""
    return "ml_reviewer_processed_review"


def route_after_ml_reviewer_processed_review(_state: PipelineState) -> str:
    """Continue the processed-review sequence after the ML reviewer review."""
    return "business_stakeholder_processed_review"


def route_after_business_processed_review(_state: PipelineState) -> str:
    """Return processed reviews to the EDA analyst for final approval."""
    return "eda_processed_approval"


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
