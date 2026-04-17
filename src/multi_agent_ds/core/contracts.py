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
    """EDA analyst handoff plan for data preparation.

    Part of the EDA↔Data-Engineer consensus loop. The analyst proposes (or
    revises) a cleaning + feature-engineering plan and signals whether it
    accepts the engineer's latest executable plan via ``accepts_engineer_plan``.
    """

    summary: str
    accepts_engineer_plan: bool = False
    cleaning_actions: list[PreparationAction] = Field(default_factory=list)
    feature_actions: list[PreparationAction] = Field(default_factory=list)
    handoff_notes: list[str] = Field(default_factory=list)
    revision_rationale: str = ""


class PreparationActionFeedback(BaseModel):
    """Feasibility feedback for one preparation action."""

    action: str
    feasible: bool
    reason: str
    suggested_adjustment: str | None = None


class PreparationExecutionPlan(BaseModel):
    """Data engineer's executable preparation plan.

    Produced during the consensus loop; this is the artifact that
    ``run_preparation_workflow`` runs when the loop exits (whether via analyst
    acceptance, engineer readiness, or iteration cap). Includes concrete
    ``cleaning_actions`` / ``feature_actions`` alongside feasibility feedback.
    """

    summary: str
    ready_for_execution: bool
    cleaning_actions: list[PreparationAction] = Field(default_factory=list)
    feature_actions: list[PreparationAction] = Field(default_factory=list)
    action_feedback: list[PreparationActionFeedback] = Field(default_factory=list)
    execution_notes: list[str] = Field(default_factory=list)


# Back-compat alias for one-release deprecation window. Prefer
# PreparationExecutionPlan in new code.
PreparationFeedbackOutput = PreparationExecutionPlan


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
    phase: str | None = None


class BaselineDecision(BaseModel):
    """Modeler's decision after reviewing baseline results."""

    summary: str
    algorithms_to_tune: list[str] = Field(default_factory=list)
    algorithms_to_drop: list[str] = Field(default_factory=list)
    reasoning: str


class TuningDecision(BaseModel):
    """Modeler's decision after reviewing Optuna tuning results."""

    algorithm: str
    accept_tuned_params: bool
    chosen_params: dict[str, Any] = Field(default_factory=dict)
    reasoning: str


class LearningRateDecision(BaseModel):
    """Modeler's decision after adjusting learning rate."""

    algorithm: str
    keep_adjustment: bool
    chosen_learning_rate: float
    chosen_n_estimators: int
    reasoning: str


class FeatureSelectionDecision(BaseModel):
    """Modeler's decision after reviewing permutation importance."""

    algorithm: str
    accept_subset: bool
    kept_features: list[str] = Field(default_factory=list)
    dropped_features: list[str] = Field(default_factory=list)
    reasoning: str


class ModelingVerdict(BaseModel):
    """Final cross-algorithm recommendation from the ml_modeler."""

    summary: str
    best_algorithm: str
    ranked_algorithms: list[str] = Field(default_factory=list)
    final_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    justification: str
    next_action: Literal["proceed_to_evaluation", "revise_modeling"] = "proceed_to_evaluation"


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
