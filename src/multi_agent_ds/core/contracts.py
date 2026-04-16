"""Core contracts for inter-agent orchestration payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EDAOutput(BaseModel):
    """What the EDA agent produces for downstream steps."""

    n_rows: int
    n_features: int
    target_rate: float
    needs_cleaning: bool
    feature_summaries: list[dict[str, Any]] = Field(default_factory=list)
    correlation_flags: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class EDAReviewConcern(BaseModel):
    """One concern raised during pre-modeling EDA review."""

    topic: str
    issue: str
    severity: Literal["low", "medium", "high"]


class EDAReviewOutput(BaseModel):
    """Review of EDA insights from a downstream specialist perspective."""

    reviewer_role: Literal["ml_modeler", "ml_reviewer", "business_stakeholder"]
    summary: str
    concerns: list[EDAReviewConcern] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    modeling_implications: list[str] = Field(default_factory=list)
    business_implications: list[str] = Field(default_factory=list)
    scientific_vs_art: list[dict[str, str]] = Field(default_factory=list)


class PreparationAction(BaseModel):
    """One requested preparation action for the data engineer."""

    area: Literal["cleaning", "feature_engineering"]
    action: str
    rationale: str
    params: dict[str, Any] = Field(default_factory=dict)


class PreparationPlanOutput(BaseModel):
    """EDA analyst handoff plan for data preparation."""

    summary: str
    approved: bool
    cleaning_actions: list[PreparationAction] = Field(default_factory=list)
    feature_actions: list[PreparationAction] = Field(default_factory=list)
    handoff_notes: list[str] = Field(default_factory=list)


class PreparationActionFeedback(BaseModel):
    """Feasibility feedback for one preparation action."""

    action: str
    feasible: bool
    reason: str
    suggested_adjustment: str | None = None


class PreparationFeedbackOutput(BaseModel):
    """Data engineer feasibility feedback on a proposed prep plan."""

    summary: str
    ready_for_execution: bool
    action_feedback: list[PreparationActionFeedback] = Field(default_factory=list)
    execution_notes: list[str] = Field(default_factory=list)


class ProcessedApprovalOutput(BaseModel):
    """Final approval decision for the processed dataset before modeling."""

    approved: bool
    summary: str
    next_action: Literal["accept_processed_data", "revise_preparation"] = "accept_processed_data"
    concerns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ModelingOutput(BaseModel):
    """What the modeling agent produces for downstream steps."""

    algorithm: str
    phase: str
    scores: dict[str, float] = Field(default_factory=dict)
    params_used: dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    next_action: str


class ModelingDecisionReview(BaseModel):
    """Review of one modeling decision."""

    decision: str
    classification: Literal["scientific", "art", "mixed"]
    mathematical_basis: str
    reasoning_quality: Literal["strong", "adequate", "weak"]
    revision_questions: list[str] = Field(default_factory=list)


class MLReviewOutput(BaseModel):
    """What the ML reviewer produces after inspecting modeling decisions."""

    summary: str
    approved: bool
    next_action: Literal["accept", "revise_modeling"] = "accept"
    decisions: list[ModelingDecisionReview] = Field(default_factory=list)


class BusinessConcern(BaseModel):
    """One business-facing concern about results or report clarity."""

    topic: str
    issue: str
    severity: Literal["low", "medium", "high"]


class BusinessReviewOutput(BaseModel):
    """What the business stakeholder agent produces after reviewing the report."""

    summary: str
    approved: bool
    next_action: Literal["accept", "revise_report", "revise_modeling"] = "accept"
    readability_assessment: str
    plausibility_assessment: str
    concerns: list[BusinessConcern] = Field(default_factory=list)
