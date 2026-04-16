from __future__ import annotations

from multi_agent_ds.orchestration.router import (
    route_after_data_engineer_execute,
    route_after_data_engineer_feedback,
    route_after_modeling_handoff,
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


def test_modeling_handoff_routes_to_end() -> None:
    assert route_after_modeling_handoff({}) == "end"
