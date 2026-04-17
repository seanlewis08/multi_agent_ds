"""Routing helpers for the runtime pipeline graph."""

from __future__ import annotations

from multi_agent_ds.core import load_workflows_config
from multi_agent_ds.orchestration.state import PipelineState

_MODELING_REVIEW_NEXT_NODE = {
    "baseline": "ml_modeler_n_estimator_search",
    "tune": "ml_modeler_train_tuned",
    "adjust_lr": "ml_modeler_importance_review",
    "feature_selection": "ml_modeler_final_recommendation",
    "final_recommendation": "evaluation",
}


def _prep_iteration_limit() -> int:
    workflow_cfg = load_workflows_config()
    return int(workflow_cfg.get("workflows", {}).get("eda_preparation", {}).get("max_iterations", 3))


def _modeling_iteration_limit() -> int:
    workflow_cfg = load_workflows_config()
    return int(workflow_cfg.get("workflows", {}).get("modeling", {}).get("max_iterations", 3))


def _report_iteration_limit() -> int:
    workflow_cfg = load_workflows_config()
    return int(workflow_cfg.get("workflows", {}).get("report", {}).get("max_iterations", 3))


def route_after_raw_eda(_state: PipelineState) -> tuple[str, str, str]:
    """Fan raw EDA out to all three reviewers."""
    return (
        "ml_modeler_raw_review",
        "ml_reviewer_raw_review",
        "business_stakeholder_raw_review",
    )


def route_after_prep_plan(state: PipelineState) -> str:
    """Route after an analyst prep-plan turn.

    The analyst ends the consensus loop by accepting the engineer's latest
    executable plan (``accepts_engineer_plan=True``). That only makes sense
    once the engineer has produced at least one plan — so acceptance requires
    both the flag AND a populated ``prep_feedback``. Otherwise the loop
    continues with another engineer turn.
    """
    prep_plan = state.get("prep_plan") or {}
    feedback = state.get("prep_feedback") or {}
    if prep_plan.get("accepts_engineer_plan", False) and feedback:
        return "data_engineer_execute"
    return "data_engineer_feedback"


def route_after_data_engineer_feedback(state: PipelineState) -> str:
    """Route after an engineer feedback/plan turn.

    The engineer ends the consensus loop by signalling ``ready_for_execution``
    on a plan that has at least one concrete action. If not ready and the
    iteration budget still has room, hand back to the analyst for another
    revision turn. When the cap is hit, force-execute the engineer's latest
    plan as forward progress (the outer ``processed_approval`` loop will
    catch a broken plan).
    """
    feedback = state.get("prep_feedback") or {}
    has_actions = bool(feedback.get("cleaning_actions") or feedback.get("feature_actions"))
    if feedback.get("ready_for_execution", False) and has_actions:
        return "data_engineer_execute"
    if state.get("prep_iteration", 0) < _prep_iteration_limit():
        return "eda_prep_plan"
    return "data_engineer_execute"


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
    """Advance from handoff into the first reviewed modeling phase."""
    return "ml_modeler_baseline"


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


def route_after_evaluation(state: PipelineState) -> str:
    """Route after the evaluation node.

    When evaluation determines the pipeline should retry modeling, it must set:
    - `should_loop=True`
    - `loop_from` to the re-entry modeler node

    Otherwise the runtime continues to the reviewer stage.
    """
    if state.get("should_loop") and state.get("loop_from"):
        return str(state["loop_from"])
    return "reviewer"


def route_after_reviewer(_state: PipelineState) -> str:
    """Advance from reviewer completion into report generation."""
    return "report_writer"


def route_after_report_generation(_state: PipelineState) -> str:
    """Advance from report generation into business stakeholder report review."""
    return "business_stakeholder_report_review"


def route_after_business_review(state: PipelineState) -> str:
    """Route after the business stakeholder verdict on the experiment report.

    Reads `business_review.next_action` and routes to one of three sinks:

    - "accept" → "end" (terminal).
    - "revise_report" → "report_writer" (rewrite the narrative), capped by
      `report_iteration` against the configured report-loop limit.
    - "revise_modeling" → "ml_modeler_baseline" (reopen the modeling loop),
      bounded by the existing modeling-loop iteration cap.

    When either cap is exceeded, the router force-accepts (returns "end") so
    the pipeline cannot loop forever on a stuck verdict.
    """
    review = state.get("business_review") or {}
    next_action = review.get("next_action", "accept")

    if next_action == "revise_report":
        if state.get("report_iteration", 0) < _report_iteration_limit():
            return "report_writer"
        return "end"

    if next_action == "revise_modeling":
        if state.get("modeling_iteration", 0) < _modeling_iteration_limit():
            return "ml_modeler_baseline"
        return "end"

    return "end"
