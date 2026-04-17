"""Top-level orchestrator agent for workflow-entry and downstream decisions."""

from __future__ import annotations

from typing import Any

from multi_agent_ds.core import load_agents_config, load_settings, load_workflows_config
from multi_agent_ds.orchestration.state import PipelineState

_GRAPH_OWNED_PHASES = {
    "raw_eda",
    "prep_plan",
    "prep_feedback",
    "prep_execute",
    "processed_eda",
    "processed_approval",
    "modeling",
    "baseline",
    "tune",
    "train_tuned",
    "adjust_lr",
    "importance_review",
    "feature_selection",
    "final_recommendation",
}


def _append_decision(state: PipelineState, phase: str, **payload: Any) -> list[dict[str, Any]]:
    """Append an orchestrator decision entry to the graph trace."""
    return state.get("agent_decisions", []) + [{"agent": "orchestrator", "phase": phase, **payload}]


def _resolve_workflow_config(state: PipelineState) -> dict[str, Any]:
    """Resolve the workflow config from state or the repository default."""
    workflow_config = state.get("workflow_config")
    if workflow_config is not None:
        return workflow_config
    return load_workflows_config()


def _resolve_agents_config(state: PipelineState) -> dict[str, Any]:
    """Resolve the agent config from state or the repository default."""
    agents_config = state.get("agents_config")
    if agents_config is not None:
        return agents_config
    return load_agents_config()


def _default_workflow_name(settings: dict[str, Any], workflow_config: dict[str, Any]) -> str:
    """Pick the default workflow for a fresh orchestrator entry decision."""
    workflows = workflow_config.get("workflows", {})
    if not workflows:
        raise ValueError("workflow_config['workflows'] must contain at least one workflow")

    source = settings.get("data", {}).get("source")
    if source == "synthetic" and "baseline_only" in workflows:
        return "baseline_only"
    if "full_pipeline" in workflows:
        return "full_pipeline"
    return next(iter(workflows))


def _entry_node_for_workflow(workflow_name: str, workflow_config: dict[str, Any]) -> str:
    """Resolve the graph entry node for a workflow definition."""
    workflow = workflow_config.get("workflows", {}).get(workflow_name, {})
    explicit_entry_node = workflow.get("entry_node")
    if isinstance(explicit_entry_node, str) and explicit_entry_node:
        return explicit_entry_node

    steps = workflow.get("steps", [])
    if not steps:
        raise ValueError(f"Workflow '{workflow_name}' does not define any steps")

    first_step = steps[0]
    if isinstance(first_step, str):
        return first_step
    if isinstance(first_step, dict):
        entry_node = first_step.get("node") or first_step.get("agent")
        if isinstance(entry_node, str) and entry_node:
            return entry_node

    raise ValueError(f"Workflow '{workflow_name}' has an unsupported first step: {first_step!r}")


def _post_model_sequence_for_workflow(
    workflow_name: str,
    workflow_config: dict[str, Any],
) -> list[str]:
    """Return the declared post-model sequence for a workflow."""
    workflow = workflow_config.get("workflows", {}).get(workflow_name, {})
    sequence = workflow.get("post_model_sequence", [])
    return [step for step in sequence if isinstance(step, str) and step]


def _modeler_variant(state: PipelineState, agents_config: dict[str, Any]) -> str:
    """Resolve the active modeler variant from state or agent config."""
    override = state.get("modeler_variant")
    if isinstance(override, str) and override:
        return override

    ml_modeler_cfg = agents_config.get("agents", {}).get("ml_modeler", {})
    active_variant = ml_modeler_cfg.get("active_variant")
    if isinstance(active_variant, str) and active_variant:
        return active_variant

    return "sean"


def _current_iteration(state: PipelineState) -> int:
    """Return the top-level orchestrator iteration count."""
    return int(state.get("iteration", 0))


def _max_iterations(settings: dict[str, Any], agents_config: dict[str, Any]) -> int:
    """Resolve the orchestrator iteration cap."""
    orchestrator_cfg = agents_config.get("agents", {}).get("orchestrator", {})
    if orchestrator_cfg.get("max_iterations") is not None:
        return int(orchestrator_cfg["max_iterations"])

    model_cfg = settings.get("model", {})
    if model_cfg.get("max_iterations") is not None:
        return int(model_cfg["max_iterations"])

    return 5


def _min_improvement(settings: dict[str, Any]) -> float:
    """Resolve the minimum improvement threshold for loop decisions."""
    tuning_cfg = settings.get("model", {}).get("tuning", {})
    if tuning_cfg.get("min_improvement") is not None:
        return float(tuning_cfg["min_improvement"])
    return 0.01


def _evaluation_improvement_signal(evaluation_result: dict[str, Any]) -> float | None:
    """Resolve an explicit improvement signal from evaluation output when available."""
    for candidate in (
        evaluation_result.get("improvement"),
        evaluation_result.get("improvement_vs_prior"),
        evaluation_result.get("score_improvement"),
        evaluation_result.get("model_selection_summary", {})
        .get("winner", {})
        .get("score_improvement"),
    ):
        if candidate is not None:
            return float(candidate)
    return None


def _workflow_entry_decision(
    state: PipelineState,
    settings: dict[str, Any],
    agents_config: dict[str, Any],
    workflow_config: dict[str, Any],
) -> dict[str, Any]:
    """Build the initial workflow-entry decision payload."""
    workflow_name = _default_workflow_name(settings, workflow_config)
    entry_node = _entry_node_for_workflow(workflow_name, workflow_config)
    modeler_variant = _modeler_variant(state, agents_config)
    downstream_sequence = _post_model_sequence_for_workflow(workflow_name, workflow_config)
    decision_summary = (
        f"Selected workflow '{workflow_name}' with entry node '{entry_node}' "
        f"and modeler variant '{modeler_variant}'."
    )
    return {
        "agents_config": agents_config,
        "workflow_config": workflow_config,
        "selected_workflow": workflow_name,
        "entry_node": entry_node,
        "modeler_variant": modeler_variant,
        "downstream_sequence": downstream_sequence,
        "decision_type": "workflow_entry",
        "status": "ready",
        "next_agent": entry_node,
        "loop_from": None,
        "should_loop": False,
        "stop_reason": None,
        "blocked_on": None,
        "blocked_reason": None,
        "decision_summary": decision_summary,
        "current_phase": "orchestrator",
        "agent_decisions": _append_decision(
            state,
            "workflow_entry",
            selected_workflow=workflow_name,
            entry_node=entry_node,
            modeler_variant=modeler_variant,
            downstream_sequence=downstream_sequence,
        ),
    }


def _blocked_decision(
    state: PipelineState,
    *,
    next_agent: str | None,
    blocked_on: str,
    blocked_reason: str,
    modeler_variant: str | None = None,
    downstream_sequence: list[str] | None = None,
    iteration: int | None = None,
    max_iterations: int | None = None,
    should_loop: bool = False,
    loop_from: str | None = None,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    """Build a blocked or pending downstream decision."""
    return {
        "decision_type": "downstream_route",
        "status": "blocked",
        "selected_workflow": None,
        "entry_node": None,
        "modeler_variant": modeler_variant,
        "downstream_sequence": downstream_sequence or [],
        "iteration": iteration,
        "max_iterations": max_iterations,
        "next_agent": next_agent,
        "loop_from": loop_from,
        "should_loop": should_loop,
        "stop_reason": stop_reason,
        "blocked_on": blocked_on,
        "blocked_reason": blocked_reason,
        "decision_summary": blocked_reason,
        "current_phase": "orchestrator",
        "agent_decisions": _append_decision(
            state,
            "downstream_route",
            next_agent=next_agent,
            blocked_on=blocked_on,
            modeler_variant=modeler_variant,
            downstream_sequence=downstream_sequence or [],
            iteration=iteration,
            max_iterations=max_iterations,
            should_loop=should_loop,
            loop_from=loop_from,
            stop_reason=stop_reason,
        ),
    }


def _ready_decision(
    state: PipelineState,
    *,
    next_agent: str | None,
    modeler_variant: str | None = None,
    downstream_sequence: list[str] | None = None,
    iteration: int | None = None,
    max_iterations: int | None = None,
    should_loop: bool = False,
    loop_from: str | None = None,
    stop_reason: str | None = None,
    decision_summary: str,
) -> dict[str, Any]:
    """Build a ready downstream decision."""
    return {
        "decision_type": "downstream_route",
        "status": "ready",
        "selected_workflow": None,
        "entry_node": None,
        "modeler_variant": modeler_variant,
        "downstream_sequence": downstream_sequence or [],
        "iteration": iteration,
        "max_iterations": max_iterations,
        "next_agent": next_agent,
        "loop_from": loop_from,
        "should_loop": should_loop,
        "stop_reason": stop_reason,
        "blocked_on": None,
        "blocked_reason": None,
        "decision_summary": decision_summary,
        "current_phase": "orchestrator",
        "agent_decisions": _append_decision(
            state,
            "downstream_route",
            next_agent=next_agent,
            modeler_variant=modeler_variant,
            downstream_sequence=downstream_sequence or [],
            iteration=iteration,
            max_iterations=max_iterations,
            should_loop=should_loop,
            loop_from=loop_from,
            stop_reason=stop_reason,
        ),
    }


def _downstream_decision(
    state: PipelineState,
    settings: dict[str, Any],
    agents_config: dict[str, Any],
    workflow_config: dict[str, Any],
) -> dict[str, Any]:
    """Build a post-modeling / post-evaluation / report-loop decision."""
    selected_workflow = state.get("selected_workflow")
    if not isinstance(selected_workflow, str) or not selected_workflow:
        selected_workflow = _default_workflow_name(settings, workflow_config)

    modeler_variant = _modeler_variant(state, agents_config)
    downstream_sequence = _post_model_sequence_for_workflow(selected_workflow, workflow_config)
    iteration = _current_iteration(state)
    max_iterations = _max_iterations(settings, agents_config)

    if state.get("business_review"):
        if state.get("should_revise_report"):
            return _blocked_decision(
                state,
                next_agent="report_writer",
                modeler_variant=modeler_variant,
                downstream_sequence=downstream_sequence,
                iteration=iteration,
                max_iterations=max_iterations,
                should_loop=True,
                loop_from="report_writer",
                blocked_on="report_review_graph_wiring",
                blocked_reason=(
                    "Business report review requested a rewrite, but the report-review loop "
                    "is not yet wired into orchestration.graph."
                ),
            )
        if state.get("should_revise_modeling"):
            return _blocked_decision(
                state,
                next_agent="ml_modeler_baseline",
                modeler_variant=modeler_variant,
                downstream_sequence=downstream_sequence,
                iteration=iteration,
                max_iterations=max_iterations,
                should_loop=True,
                loop_from="ml_modeler_baseline",
                blocked_on="report_review_graph_wiring",
                blocked_reason=(
                    "Business report review requested a modeling revision, but the report-review "
                    "loop is not yet wired into orchestration.graph."
                ),
            )
        return _ready_decision(
            state,
            next_agent=None,
            modeler_variant=modeler_variant,
            downstream_sequence=downstream_sequence,
            iteration=iteration,
            max_iterations=max_iterations,
            stop_reason="business_review_accepted",
            decision_summary="Business review accepted the report. No further runtime action is required.",
        )

    if state.get("experiment_report"):
        return _blocked_decision(
            state,
            next_agent="business_stakeholder_report_review",
            modeler_variant=modeler_variant,
            downstream_sequence=downstream_sequence,
            iteration=iteration,
            max_iterations=max_iterations,
            blocked_on="report_review_graph_wiring",
            blocked_reason=(
                "The report is generated, but business_stakeholder report_review is not yet "
                "wired into orchestration.graph."
            ),
        )

    if state.get("evaluation_result"):
        evaluation_result = state["evaluation_result"]
        improvement = _evaluation_improvement_signal(evaluation_result)
        threshold = _min_improvement(settings)

        if improvement is not None and improvement < threshold and iteration < max_iterations:
            return _blocked_decision(
                state,
                next_agent="ml_modeler_baseline",
                modeler_variant=modeler_variant,
                downstream_sequence=downstream_sequence,
                iteration=iteration,
                max_iterations=max_iterations,
                should_loop=True,
                loop_from="ml_modeler_baseline",
                blocked_on="post_evaluation_loop_wiring",
                blocked_reason=(
                    f"Evaluation improvement {improvement:.6f} is below the configured "
                    f"threshold {threshold:.6f}, so the orchestrator would reopen the "
                    "modeling loop if post-evaluation loop wiring existed."
                ),
            )

        stop_reason = None
        if iteration >= max_iterations:
            stop_reason = "max_iterations_reached"
        elif improvement is None:
            stop_reason = "prior_context_missing"
        elif improvement >= threshold:
            stop_reason = "improvement_threshold_met"

        return _blocked_decision(
            state,
            next_agent="reviewer",
            modeler_variant=modeler_variant,
            downstream_sequence=downstream_sequence,
            iteration=iteration,
            max_iterations=max_iterations,
            blocked_on="reviewer_graph_wiring",
            blocked_reason=(
                "Evaluation output is available, but the reviewer agent is not yet wired into "
                "orchestration.graph."
            ),
            stop_reason=stop_reason,
        )

    if state.get("modeling_verdict"):
        return _blocked_decision(
            state,
            next_agent="evaluation",
            modeler_variant=modeler_variant,
            downstream_sequence=downstream_sequence,
            iteration=iteration,
            max_iterations=max_iterations,
            blocked_on="evaluation_graph_wiring",
            blocked_reason=(
                "A modeling verdict is available, but the evaluation workflow is not yet wired "
                "into orchestration.graph."
            ),
        )

    current_phase = state.get("current_phase")
    if current_phase in _GRAPH_OWNED_PHASES:
        return _ready_decision(
            state,
            next_agent=None,
            modeler_variant=modeler_variant,
            downstream_sequence=downstream_sequence,
            iteration=iteration,
            max_iterations=max_iterations,
            decision_summary=(
                f"Current phase '{current_phase}' is already owned by the existing graph/router flow."
            ),
        )

    return _ready_decision(
        state,
        next_agent=None,
        modeler_variant=modeler_variant,
        downstream_sequence=downstream_sequence,
        iteration=iteration,
        max_iterations=max_iterations,
        decision_summary="No downstream decision was required from the current state snapshot.",
    )


def orchestrator_node(state: PipelineState) -> dict[str, Any]:
    """Return a machine-readable workflow-entry or downstream-routing decision."""
    settings = state.get("settings") or load_settings()
    agents_config = _resolve_agents_config(state)
    workflow_config = _resolve_workflow_config(state)

    if not state.get("current_phase"):
        return _workflow_entry_decision(state, settings, agents_config, workflow_config)

    return _downstream_decision(state, settings, agents_config, workflow_config)
