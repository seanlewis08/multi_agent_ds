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
