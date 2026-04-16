"""Core contracts for inter-agent orchestration payloads."""

from __future__ import annotations

from typing import Any

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
