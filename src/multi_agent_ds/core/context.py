"""Shared execution context objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExperimentContext:
    """Domain payload agents read and write during orchestration."""

    dataset_info: dict[str, Any] = field(default_factory=dict)
    feature_insights: dict[str, Any] = field(default_factory=dict)
    model_comparisons: list[dict[str, Any]] = field(default_factory=list)
    agent_reasoning_trace: list[dict[str, Any]] = field(default_factory=list)
    config_snapshot: dict[str, Any] = field(default_factory=dict)
