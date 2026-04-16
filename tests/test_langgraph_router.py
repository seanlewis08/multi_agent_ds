from __future__ import annotations

from multi_agent_ds.orchestration.router import (
    route_after_business_review,
    route_after_eda,
    route_after_ml_review,
    route_after_modeling,
)


def test_route_after_eda_goes_to_data_engineer_when_cleaning_is_needed() -> None:
    assert route_after_eda({"eda_insights": {"needs_cleaning": True}}) == "data_engineer"


def test_route_after_eda_goes_to_ml_modeler_when_cleaning_is_not_needed() -> None:
    assert route_after_eda({"eda_insights": {"needs_cleaning": False}}) == "ml_modeler"
    assert route_after_eda({}) == "ml_modeler"


def test_route_after_modeling_loops_when_enabled_and_under_limit() -> None:
    assert route_after_modeling({"should_loop": True, "iteration": 0}) == "ml_modeler"
    assert route_after_modeling({"should_loop": True, "iteration": 4}) == "ml_modeler"


def test_route_after_modeling_goes_to_ml_review_when_not_looping_or_at_limit() -> None:
    assert route_after_modeling({"should_loop": False, "iteration": 0}) == "ml_reviewer"
    assert route_after_modeling({"should_loop": True, "iteration": 5}) == "ml_reviewer"
    assert route_after_modeling({}) == "ml_reviewer"


def test_route_after_ml_review_routes_back_to_modeling_when_requested() -> None:
    assert route_after_ml_review({"ml_review": {"next_action": "revise_modeling"}}) == "ml_modeler"


def test_route_after_ml_review_routes_to_evaluation_by_default() -> None:
    assert route_after_ml_review({"ml_review": {"next_action": "accept"}}) == "evaluation"
    assert route_after_ml_review({}) == "evaluation"


def test_route_after_business_review_routes_to_requested_revision_path() -> None:
    assert route_after_business_review({"business_review": {"next_action": "revise_report"}}) == "report"
    assert route_after_business_review({"business_review": {"next_action": "revise_modeling"}}) == "ml_modeler"


def test_route_after_business_review_routes_to_end_by_default() -> None:
    assert route_after_business_review({"business_review": {"next_action": "accept"}}) == "end"
    assert route_after_business_review({}) == "end"
