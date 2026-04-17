"""Focused tests for Sean Step 6 — report writer + business stakeholder report review."""

from __future__ import annotations

from typing import Any

import pytest

from multi_agent_ds.agents.business_stakeholder import business_stakeholder_node
from multi_agent_ds.agents.report_writer import report_writer_node
from multi_agent_ds.orchestration.router import route_after_business_review
from multi_agent_ds.tools.reporting import (
    format_data_summary,
    format_decision_trace,
    format_evaluation_summary,
    format_modeling_summary,
)


# ── Pure formatter coverage ────────────────────────────────────────────


def test_format_data_summary_handles_full_payload() -> None:
    block = format_data_summary(
        {
            "n_train": 700,
            "n_validation": 150,
            "n_test": 150,
            "n_features": 9,
            "n_numerical": 6,
            "n_categorical": 3,
            "target_rate_train": 0.183456,
            "target_rate_test": 0.179012,
            "has_ground_truth": True,
        }
    )
    assert "Train rows:** 700" in block
    assert "Features:** 9 (6 numerical, 3 categorical)" in block
    assert "train=0.1835" in block
    assert "Ground truth" in block


def test_format_data_summary_handles_missing_payload() -> None:
    assert "unavailable" in format_data_summary(None).lower()
    assert "unavailable" in format_data_summary({}).lower()


def test_format_modeling_summary_renders_verdict_and_candidates() -> None:
    block = format_modeling_summary(
        {
            "summary": "LightGBM leads on every metric.",
            "best_algorithm": "lightgbm",
            "ranked_algorithms": ["lightgbm", "logistic_regression"],
            "final_metrics": {
                "lightgbm": {"gini": 0.66, "roc_auc": 0.83},
                "logistic_regression": {"gini": 0.51, "roc_auc": 0.74},
            },
            "justification": "Lead larger than either model's CV std.",
            "next_action": "proceed_to_evaluation",
        },
        {
            "final_candidates": {
                "lightgbm": {"final_phase": "feature_selection"},
                "logistic_regression": {"final_phase": "baseline"},
            }
        },
    )
    assert "Best algorithm:** lightgbm" in block
    assert "lightgbm: gini=0.6600" in block
    assert "Ranking:** lightgbm, logistic_regression" in block
    assert "lightgbm: feature_selection" in block


def test_format_modeling_summary_handles_missing_verdict() -> None:
    assert "unavailable" in format_modeling_summary(None).lower()


def test_format_evaluation_summary_caveats_when_missing() -> None:
    text = format_evaluation_summary(None)
    assert "not available" in text.lower()
    assert "report relies solely" in text.lower()


def test_format_evaluation_summary_renders_known_keys() -> None:
    block = format_evaluation_summary(
        {
            "winner": "lightgbm",
            "primary_metric": "gini",
            "rankings": {"gini": ["lightgbm", "logistic_regression"]},
            "ground_truth_comparison": {
                "lightgbm": {"mse_vs_true_prob": 0.001234},
            },
            "shap": {"top_features": ["age", "income", "credit_score"]},
        }
    )
    assert "Evaluation winner:** lightgbm" in block
    assert "Primary metric:** gini" in block
    assert "MSE vs true probability = 0.001234" in block
    assert "Top features (SHAP):** age, income, credit_score" in block


def test_format_decision_trace_handles_empty_and_truncates() -> None:
    assert "no agent decisions" in format_decision_trace(None).lower()
    long_trace = [
        {"agent": "ml_modeler", "phase": f"phase_{i}", "summary": f"step {i}"}
        for i in range(40)
    ]
    block = format_decision_trace(long_trace, max_entries=5)
    assert block.count("ml_modeler / phase_") == 5
    # only the trailing five entries should be present
    assert "phase_35" in block
    assert "phase_30" not in block


# ── Report writer agent ────────────────────────────────────────────────


class FakeChatAdapter:
    """Stub adapter that returns a canned markdown report from .chat()."""

    last_user_content: str = ""

    def chat(self, messages: list[dict[str, Any]], tools: Any = None) -> dict[str, Any]:
        FakeChatAdapter.last_user_content = messages[-1]["content"]
        return {
            "content": "# Stakeholder Report\n\nLightGBM was selected.",
            "tool_calls": [],
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        }


def _fake_chat_build_adapter(*args: Any, **kwargs: Any) -> FakeChatAdapter:
    """Drop-in replacement for build_adapter that returns a chat-only fake."""
    return FakeChatAdapter()


def _settings() -> dict[str, Any]:
    return {"llm": {"providers": {"openai": {"model": "gpt-4o", "temperature": 0.2, "max_tokens": 1000}}}}


def _prompts() -> dict[str, Any]:
    return {
        "report_writer": {
            "system": "You are the report writer.",
            "generate": (
                "{critique_section}data={data_summary}; modeling={modeling_summary};"
                " evaluation={evaluation_summary}; trace={decision_trace}"
            ),
        },
        "business_stakeholder": {
            "system": "You are a business stakeholder.",
            "eda_review": "stage={review_stage}; eda={eda_json}",
            "report_review": (
                "report={report_markdown}; modeling={modeling_summary};"
                " evaluation={evaluation_summary}"
            ),
        },
    }


def _verdict_state(extras: dict[str, Any] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "settings": _settings(),
        "data": {
            "data_summary": {
                "n_train": 700,
                "n_test": 200,
                "n_features": 9,
                "n_numerical": 6,
                "n_categorical": 3,
                "target_rate_train": 0.18,
                "target_rate_test": 0.18,
                "has_ground_truth": True,
            }
        },
        "modeling_verdict": {
            "summary": "LightGBM leads.",
            "best_algorithm": "lightgbm",
            "ranked_algorithms": ["lightgbm", "logistic_regression"],
            "final_metrics": {
                "lightgbm": {"gini": 0.66},
                "logistic_regression": {"gini": 0.51},
            },
            "justification": "Clear lead.",
            "next_action": "proceed_to_evaluation",
        },
        "modeling_results": {
            "final_candidates": {
                "lightgbm": {"final_phase": "feature_selection"},
                "logistic_regression": {"final_phase": "baseline"},
            }
        },
        "agent_decisions": [
            {"agent": "ml_modeler", "phase": "baseline", "summary": "Both worth tuning."},
        ],
    }
    if extras:
        state.update(extras)
    return state


def test_report_writer_generate_happy_path(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.build_adapter", _fake_chat_build_adapter)
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.load_prompts_config", _prompts)

    result = report_writer_node(
        _verdict_state({"evaluation_result": {"winner": "lightgbm", "primary_metric": "gini"}})
    )

    assert result["experiment_report"].startswith("# Stakeholder Report")
    assert result["report_draft"] == result["experiment_report"]
    assert result["current_phase"] == "report_generate"
    assert result["report_iteration"] == 1
    decision = result["agent_decisions"][-1]
    assert decision["agent"] == "report_writer"
    assert decision["evaluation_available"] is True
    assert decision["characters"] == len(result["experiment_report"])
    # prompt should have rendered all the formatter blocks
    assert "lightgbm" in FakeChatAdapter.last_user_content
    assert "Train rows" in FakeChatAdapter.last_user_content


def test_report_writer_handles_missing_evaluation_result(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.build_adapter", _fake_chat_build_adapter)
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.load_prompts_config", _prompts)

    result = report_writer_node(_verdict_state())

    assert result["agent_decisions"][-1]["evaluation_available"] is False
    assert "not available" in FakeChatAdapter.last_user_content.lower()


def test_report_writer_raises_when_modeling_verdict_missing(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.build_adapter", _fake_chat_build_adapter)
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.load_prompts_config", _prompts)

    state = _verdict_state()
    state.pop("modeling_verdict")
    with pytest.raises(ValueError, match="modeling_verdict"):
        report_writer_node(state)


def test_report_writer_rejects_unknown_mode(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.build_adapter", _fake_chat_build_adapter)
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.load_prompts_config", _prompts)

    with pytest.raises(ValueError, match="Unsupported mode"):
        report_writer_node(_verdict_state(), mode="not_a_mode")


def test_report_writer_increments_iteration_on_loop_back(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.build_adapter", _fake_chat_build_adapter)
    monkeypatch.setattr("multi_agent_ds.agents.report_writer.load_prompts_config", _prompts)

    state = _verdict_state(
        {
            "current_phase": "report_generate",
            "report_iteration": 1,
            "business_review": {
                "summary": "Too jargon-heavy.",
                "approved": False,
                "next_action": "revise_report",
                "readability_assessment": "needs simpler language",
                "plausibility_assessment": "ok",
                "concerns": [
                    {"topic": "tone", "issue": "too technical", "severity": "medium"},
                ],
            },
        }
    )

    result = report_writer_node(state)
    assert result["report_iteration"] == 2
    assert "revise_report" in FakeChatAdapter.last_user_content
    assert "too technical" in FakeChatAdapter.last_user_content


# ── Business stakeholder report_review mode ────────────────────────────


class FakeBizReviewAdapter:
    """Stub adapter that returns a canned BusinessReviewOutput payload."""

    next_action: str = "accept"
    last_user_content: str = ""

    def structured_output(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        FakeBizReviewAdapter.last_user_content = messages[-1]["content"]
        return {
            "parsed": {
                "summary": "Report is acceptable." if FakeBizReviewAdapter.next_action == "accept"
                else "Report needs work.",
                "approved": FakeBizReviewAdapter.next_action == "accept",
                "next_action": FakeBizReviewAdapter.next_action,
                "readability_assessment": "Clear language.",
                "plausibility_assessment": "Conclusions are plausible.",
                "concerns": (
                    []
                    if FakeBizReviewAdapter.next_action == "accept"
                    else [{"topic": "clarity", "issue": "Add more caveats.", "severity": "medium"}]
                ),
            }
        }


def _fake_biz_build_adapter(*args: Any, **kwargs: Any) -> FakeBizReviewAdapter:
    """Drop-in replacement for build_adapter that returns the biz review fake."""
    return FakeBizReviewAdapter()


def _report_review_state() -> dict[str, Any]:
    return {
        "settings": _settings(),
        "experiment_report": "# Stakeholder Report\nLightGBM selected.",
        "modeling_verdict": {
            "summary": "LightGBM leads.",
            "best_algorithm": "lightgbm",
            "ranked_algorithms": ["lightgbm"],
            "final_metrics": {"lightgbm": {"gini": 0.66}},
            "justification": "Clear lead.",
            "next_action": "proceed_to_evaluation",
        },
        "evaluation_result": {"winner": "lightgbm"},
        "agent_decisions": [],
    }


def test_business_stakeholder_report_review_accept(monkeypatch) -> None:
    FakeBizReviewAdapter.next_action = "accept"
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.build_adapter", _fake_biz_build_adapter
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.load_prompts_config", _prompts
    )

    result = business_stakeholder_node(_report_review_state(), mode="report_review")

    assert result["business_review"]["next_action"] == "accept"
    assert result["business_review"]["approved"] is True
    assert result["should_revise_report"] is False
    assert result["should_revise_modeling"] is False
    assert result["current_phase"] == "report_review"
    assert result["agent_decisions"][-1]["next_action"] == "accept"


def test_business_stakeholder_report_review_revise_report(monkeypatch) -> None:
    FakeBizReviewAdapter.next_action = "revise_report"
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.build_adapter", _fake_biz_build_adapter
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.load_prompts_config", _prompts
    )

    result = business_stakeholder_node(_report_review_state(), mode="report_review")

    assert result["should_revise_report"] is True
    assert result["should_revise_modeling"] is False
    assert result["business_review"]["concerns"][0]["topic"] == "clarity"


def test_business_stakeholder_report_review_revise_modeling(monkeypatch) -> None:
    FakeBizReviewAdapter.next_action = "revise_modeling"
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.build_adapter", _fake_biz_build_adapter
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.load_prompts_config", _prompts
    )

    result = business_stakeholder_node(_report_review_state(), mode="report_review")

    assert result["should_revise_report"] is False
    assert result["should_revise_modeling"] is True


def test_business_stakeholder_report_review_requires_experiment_report(monkeypatch) -> None:
    FakeBizReviewAdapter.next_action = "accept"
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.build_adapter", _fake_biz_build_adapter
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.load_prompts_config", _prompts
    )

    state = _report_review_state()
    state.pop("experiment_report")
    with pytest.raises(ValueError, match="experiment_report"):
        business_stakeholder_node(state, mode="report_review")


def test_business_stakeholder_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported mode"):
        business_stakeholder_node(_report_review_state(), mode="not_a_mode")


def test_business_stakeholder_eda_review_still_works(monkeypatch) -> None:
    """Regression: extending the agent must not break the existing EDA modes."""

    class FakeEDAAdapter:
        def structured_output(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
            return {
                "parsed": {
                    "reviewer_role": "business_stakeholder",
                    "summary": "EDA looks fine.",
                    "concerns": [],
                    "recommendations": [],
                    "modeling_implications": [],
                    "business_implications": [],
                    "scientific_vs_art": [],
                }
            }

    def fake_build_adapter_eda(*_args: Any, **_kwargs: Any) -> FakeEDAAdapter:
        return FakeEDAAdapter()

    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.build_adapter", fake_build_adapter_eda
    )
    monkeypatch.setattr(
        "multi_agent_ds.agents.business_stakeholder.load_prompts_config", _prompts
    )

    result = business_stakeholder_node(
        {
            "settings": _settings(),
            "raw_eda_insights": {"needs_cleaning": False},
            "agent_decisions": [],
        },
        mode="raw_review",
    )
    assert result["raw_eda_business_review"]["summary"] == "EDA looks fine."


# ── Router ─────────────────────────────────────────────────────────────


def test_route_after_business_review_accept_goes_to_end() -> None:
    state = {"business_review": {"next_action": "accept"}}
    assert route_after_business_review(state) == "end"


def test_route_after_business_review_routes_to_report_writer_under_cap() -> None:
    state = {
        "business_review": {"next_action": "revise_report"},
        "report_iteration": 1,
    }
    # default cap from workflows.yaml is 2
    assert route_after_business_review(state) == "report_writer"


def test_route_after_business_review_force_accepts_at_report_cap() -> None:
    state = {
        "business_review": {"next_action": "revise_report"},
        "report_iteration": 5,
    }
    assert route_after_business_review(state) == "end"


def test_route_after_business_review_routes_to_modeler_under_cap() -> None:
    state = {
        "business_review": {"next_action": "revise_modeling"},
        "modeling_iteration": 1,
    }
    assert route_after_business_review(state) == "ml_modeler_baseline"


def test_route_after_business_review_force_accepts_at_modeling_cap() -> None:
    state = {
        "business_review": {"next_action": "revise_modeling"},
        "modeling_iteration": 99,
    }
    assert route_after_business_review(state) == "end"


def test_route_after_business_review_handles_missing_review() -> None:
    """Defensive default — if no review present, treat as accept."""
    assert route_after_business_review({}) == "end"
