"""End-to-end workflow compositions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["run_full_pipeline"]

if TYPE_CHECKING:
    from multi_agent_ds.workflows.full_pipeline import run_full_pipeline  # noqa: F401


def __getattr__(name: str) -> Any:
    """Lazy-import ``run_full_pipeline`` to avoid circular imports.

    ``full_pipeline`` imports ``orchestration.graph`` which imports the agent
    modules, and several agents import from ``workflows`` — eager-importing
    here would deadlock module initialization. Lazy-loading preserves the
    public ``from multi_agent_ds.workflows import run_full_pipeline`` ergonomic
    without triggering the cycle.
    """
    if name == "run_full_pipeline":
        from multi_agent_ds.workflows.full_pipeline import run_full_pipeline

        return run_full_pipeline
    raise AttributeError(f"module 'multi_agent_ds.workflows' has no attribute {name!r}")
