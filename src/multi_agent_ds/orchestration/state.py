"""Shared state schema for the LangGraph orchestration layer."""

from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    """State passed between orchestration graph nodes."""

    # Data references
    data_path: str
    data: dict[str, Any]
    settings: dict[str, Any]

    # Agent outputs
    eda_insights: dict[str, Any]
    prep_result: dict[str, Any]
    modeling_results: dict[str, Any]
    evaluation_result: dict[str, Any]
    experiment_report: str

    # Control flow
    agent_decisions: list[dict[str, Any]]
    current_phase: str
    should_loop: bool
    iteration: int
