from __future__ import annotations

from typing import Any

from multi_agent_ds.agents.business_stakeholder import business_stakeholder_node
from multi_agent_ds.agents.data_engineer import data_engineer_node
from multi_agent_ds.agents.ml_modeler import ml_modeler_node
from multi_agent_ds.agents.ml_reviewer import ml_reviewer_node


class FakeReviewAdapter:
    def __init__(self, settings: dict[str, Any]):
        self.settings = settings

    def structured_output(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        if "ready_for_execution" in schema["properties"]:
            return {
                "parsed": {
                    "summary": "The plan is feasible.",
                    "ready_for_execution": True,
                    "action_feedback": [
                        {
                            "action": "clip_outliers_iqr",
                            "feasible": True,
                            "reason": "The feature is numeric.",
                        }
                    ],
                    "execution_notes": ["Run the approved plan once."],
                }
            }

        system_prompt = messages[0]["content"].lower()
        if "modeler agent" in system_prompt:
            reviewer_role = "ml_modeler"
        elif "business stakeholder" in system_prompt:
            reviewer_role = "business_stakeholder"
        else:
            reviewer_role = "ml_reviewer"

        return {
            "parsed": {
                "reviewer_role": reviewer_role,
                "summary": "The EDA review is acceptable.",
                "concerns": [],
                "recommendations": ["Proceed carefully."],
                "modeling_implications": ["Use robust validation."],
                "business_implications": [],
                "scientific_vs_art": [],
            }
        }


def _settings() -> dict[str, Any]:
    return {"llm": {"providers": {"openai": {"model": "gpt-4o", "temperature": 0.2, "max_tokens": 1000}}}}


def _prompts() -> dict[str, Any]:
    return {
        "data_engineer": {
            "system": "system prompt",
            "plan_feedback": "plan={prep_plan_json}; raw={raw_eda_json}",
        },
        "sean_ml_modeler": {
            "system": "You are an ML modeler agent.",
            "eda_review": "stage={review_stage}; eda={eda_json}",
        },
        "ml_reviewer": {
            "system": "You are an ML reviewer.",
            "eda_review": "stage={review_stage}; eda={eda_json}",
        },
        "business_stakeholder": {
            "system": "You are a business stakeholder.",
            "eda_review": "stage={review_stage}; eda={eda_json}",
        },
    }


def test_data_engineer_feedback_returns_structured_output(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.data_engineer.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.data_engineer.load_prompts_config", _prompts)

    result = data_engineer_node(
        {
            "settings": _settings(),
            "prep_plan": {"cleaning_actions": [{"action": "clip_outliers_iqr"}]},
            "raw_eda_insights": {"needs_cleaning": True},
            "agent_decisions": [],
        },
        mode="feedback",
    )

    assert result["prep_feedback"]["ready_for_execution"] is True
    assert result["current_phase"] == "prep_feedback"


def test_ml_modeler_raw_review_returns_review_payload(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_modeler.load_prompts_config", _prompts)

    result = ml_modeler_node(
        {"settings": _settings(), "raw_eda_insights": {"needs_cleaning": True}, "agent_decisions": []},
        mode="raw_review",
    )

    assert result["raw_eda_ml_modeler_review"]["recommendations"] == ["Proceed carefully."]


def test_ml_reviewer_and_business_stakeholder_processed_reviews_return_payloads(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.business_stakeholder.OpenAIAdapter", FakeReviewAdapter)
    monkeypatch.setattr("multi_agent_ds.agents.ml_reviewer.load_prompts_config", _prompts)
    monkeypatch.setattr("multi_agent_ds.agents.business_stakeholder.load_prompts_config", _prompts)

    state = {"settings": _settings(), "processed_eda_insights": {"needs_cleaning": False}, "agent_decisions": []}
    ml_review = ml_reviewer_node(state, mode="processed_review")
    biz_review = business_stakeholder_node(state, mode="processed_review")

    assert ml_review["processed_eda_ml_review"]["summary"] == "The EDA review is acceptable."
    assert biz_review["processed_eda_business_review"]["summary"] == "The EDA review is acceptable."
