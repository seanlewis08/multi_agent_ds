from __future__ import annotations

from multi_agent_ds.orchestration.router import route_after_eda, route_after_modeling


def test_route_after_eda_goes_to_data_engineer_when_cleaning_is_needed() -> None:
    assert route_after_eda({"eda_insights": {"needs_cleaning": True}}) == "data_engineer"


def test_route_after_eda_goes_to_ml_modeler_when_cleaning_is_not_needed() -> None:
    assert route_after_eda({"eda_insights": {"needs_cleaning": False}}) == "ml_modeler"
    assert route_after_eda({}) == "ml_modeler"


def test_route_after_modeling_loops_when_enabled_and_under_limit() -> None:
    assert route_after_modeling({"should_loop": True, "iteration": 0}) == "ml_modeler"
    assert route_after_modeling({"should_loop": True, "iteration": 4}) == "ml_modeler"


def test_route_after_modeling_goes_to_evaluation_when_not_looping_or_at_limit() -> None:
    assert route_after_modeling({"should_loop": False, "iteration": 0}) == "evaluation"
    assert route_after_modeling({"should_loop": True, "iteration": 5}) == "evaluation"
    assert route_after_modeling({}) == "evaluation"
