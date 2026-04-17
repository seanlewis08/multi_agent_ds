from __future__ import annotations

import pytest

from multi_agent_ds.orchestration.router import (
    route_after_data_engineer_execute,
    route_after_data_engineer_feedback,
    route_after_evaluation,
    route_after_modeling_handoff,
    route_after_modeling_review,
    route_after_prep_plan,
    route_after_processed_approval,
    route_after_processed_eda,
    route_after_report_generation,
    route_after_reviewer,
    route_after_raw_eda,
    route_after_business_review,
)


def test_raw_review_stage_fans_out_to_all_three_reviewers() -> None:
    assert route_after_raw_eda({}) == (
        "ml_modeler_raw_review",
        "ml_reviewer_raw_review",
        "business_stakeholder_raw_review",
    )


def test_route_after_prep_plan_goes_to_feedback_when_analyst_does_not_accept() -> None:
    state = {
        "prep_plan": {"accepts_engineer_plan": False},
        "prep_feedback": {
            "cleaning_actions": [{"action": "x"}],
            "feature_actions": [],
        },
    }
    assert route_after_prep_plan(state) == "data_engineer_feedback"


def test_route_after_prep_plan_executes_when_analyst_accepts_and_engineer_plan_exists() -> None:
    state = {
        "prep_plan": {"accepts_engineer_plan": True},
        "prep_feedback": {
            "summary": "engineer plan",
            "cleaning_actions": [{"action": "x"}],
            "feature_actions": [],
        },
    }
    assert route_after_prep_plan(state) == "data_engineer_execute"


def test_route_after_prep_plan_feedback_when_accept_with_no_engineer_plan_yet() -> None:
    # Iteration-1 edge case: analyst can't meaningfully accept before the
    # engineer has produced anything. Defensive: route to feedback.
    state = {"prep_plan": {"accepts_engineer_plan": True}}
    assert route_after_prep_plan(state) == "data_engineer_feedback"


def test_route_after_data_engineer_feedback_executes_when_ready() -> None:
    state = {
        "prep_feedback": {
            "ready_for_execution": True,
            "cleaning_actions": [{"action": "x"}],
            "feature_actions": [],
        },
        "prep_iteration": 1,
    }
    assert route_after_data_engineer_feedback(state) == "data_engineer_execute"


def test_route_after_data_engineer_feedback_loops_when_not_ready() -> None:
    state = {
        "prep_feedback": {
            "ready_for_execution": False,
            "cleaning_actions": [],
            "feature_actions": [],
        },
        "prep_iteration": 1,
    }
    assert route_after_data_engineer_feedback(state) == "eda_prep_plan"


def test_route_after_data_engineer_feedback_force_executes_at_cap() -> None:
    state = {
        "prep_feedback": {
            "ready_for_execution": False,
            "cleaning_actions": [{"action": "x"}],
            "feature_actions": [],
        },
        "prep_iteration": 3,
    }
    assert route_after_data_engineer_feedback(state) == "data_engineer_execute"


def test_data_engineer_execute_router_returns_to_processed_eda() -> None:
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
        ("final_recommendation", "evaluation"),
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


def test_evaluation_routes_to_reviewer_by_default() -> None:
    assert route_after_evaluation({}) == "reviewer"


def test_evaluation_loops_back_to_modeling_when_requested() -> None:
    state = {
        "should_loop": True,
        "loop_from": "ml_modeler_baseline",
    }
    assert route_after_evaluation(state) == "ml_modeler_baseline"


def test_reviewer_advances_to_report_generation() -> None:
    assert route_after_reviewer({}) == "report_writer"


def test_report_generation_advances_to_business_review() -> None:
    assert route_after_report_generation({}) == "business_stakeholder_report_review"


def test_business_review_accepts_or_loops_with_caps() -> None:
    assert route_after_business_review({"business_review": {"next_action": "accept"}}) == "end"
    assert (
        route_after_business_review(
            {
                "business_review": {"next_action": "revise_report"},
                "report_iteration": 1,
            }
        )
        == "report_writer"
    )
    assert (
        route_after_business_review(
            {
                "business_review": {"next_action": "revise_modeling"},
                "modeling_iteration": 1,
            }
        )
        == "ml_modeler_baseline"
    )
