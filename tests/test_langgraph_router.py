from __future__ import annotations

import pytest

from multi_agent_ds.orchestration.router import (
    route_after_data_engineer_execute,
    route_after_data_engineer_feedback,
    route_after_modeling_handoff,
    route_after_modeling_review,
    route_after_prep_plan,
    route_after_processed_approval,
    route_after_processed_eda,
    route_after_raw_eda,
)


def test_raw_review_stage_fans_out_to_all_three_reviewers() -> None:
    assert route_after_raw_eda({}) == (
        "ml_modeler_raw_review",
        "ml_reviewer_raw_review",
        "business_stakeholder_raw_review",
    )


def test_prep_plan_routes_to_feedback_or_execution() -> None:
    assert route_after_prep_plan({"prep_approved": False}) == "data_engineer_feedback"
    assert route_after_prep_plan({"prep_approved": True}) == "data_engineer_execute"


def test_data_engineer_routes_return_to_prep_or_processed_eda() -> None:
    assert route_after_data_engineer_feedback({}) == "eda_prep_plan"
    assert route_after_data_engineer_execute({}) == "eda_processed"


def test_processed_review_stage_fans_out_to_all_three_reviewers() -> None:
    assert route_after_processed_eda({}) == (
        "ml_modeler_processed_review",
        "ml_reviewer_processed_review",
        "business_stakeholder_processed_review",
    )


def test_processed_approval_reopens_loop_or_hands_off_to_modeling() -> None:
    assert route_after_processed_approval({"processed_eda_approved": True}) == "ml_modeler_handoff"
    assert route_after_processed_approval({"processed_eda_approved": False, "prep_iteration": 1}) == "eda_prep_plan"


def test_processed_approval_ends_when_iteration_budget_is_exhausted() -> None:
    assert route_after_processed_approval({"processed_eda_approved": False, "prep_iteration": 3}) == "end"


def test_modeling_handoff_routes_into_modeling_loop() -> None:
    assert route_after_modeling_handoff({}) == "ml_modeler_baseline"


@pytest.mark.parametrize(
    "current_phase,expected_next",
    [
        ("baseline", "ml_modeler_n_estimator_search"),
        ("tune", "ml_modeler_train_tuned"),
        ("adjust_lr", "ml_modeler_importance_review"),
        ("feature_selection", "ml_modeler_final_recommendation"),
        ("final_recommendation", "end"),
    ],
)
def test_modeling_review_advances_on_accept(current_phase: str, expected_next: str) -> None:
    state = {
        "current_phase": current_phase,
        "should_revise_modeling": False,
        "modeling_iteration": 1,
    }
    assert route_after_modeling_review(state) == expected_next


@pytest.mark.parametrize(
    "current_phase",
    ["baseline", "tune", "adjust_lr", "feature_selection", "final_recommendation"],
)
def test_modeling_review_loops_back_on_revise_under_cap(current_phase: str) -> None:
    state = {
        "current_phase": current_phase,
        "should_revise_modeling": True,
        "modeling_iteration": 1,
    }
    assert route_after_modeling_review(state) == f"ml_modeler_{current_phase}"


def test_modeling_review_advances_when_iteration_cap_exhausted() -> None:
    state = {
        "current_phase": "tune",
        "should_revise_modeling": True,
        "modeling_iteration": 99,
    }
    assert route_after_modeling_review(state) == "ml_modeler_train_tuned"


def test_modeling_review_raises_on_unknown_phase() -> None:
    with pytest.raises(ValueError, match="Unknown modeling review phase"):
        route_after_modeling_review({"current_phase": "bogus", "should_revise_modeling": False})


def test_modeling_iteration_resets_across_phases() -> None:
    """Per-phase semantics: entering a new phase resets modeling_iteration to 1.

    Covered via ml_modeler._next_modeling_iteration. This router-level assertion
    proves a realistic hand-off: baseline burns its budget (iter=3, advance to
    n_estimator_search), then later tune still has its full budget because iter
    was reset on tune entry.
    """
    # baseline at cap, revise → router advances
    assert route_after_modeling_review(
        {"current_phase": "baseline", "should_revise_modeling": True, "modeling_iteration": 3}
    ) == "ml_modeler_n_estimator_search"
    # later, tune enters fresh (iter reset to 1 by modeler), revise → loops back
    assert route_after_modeling_review(
        {"current_phase": "tune", "should_revise_modeling": True, "modeling_iteration": 1}
    ) == "ml_modeler_tune"
