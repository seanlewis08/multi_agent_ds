from __future__ import annotations

from typing import Any

from multi_agent_ds.agents.eda_analyst import eda_analyst_node


class FakeAdapter:
    def __init__(self, settings: dict[str, Any]):
        self.settings = settings

    def structured_output(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

        if "needs_cleaning" in schema["properties"]:
            return {
                "parsed": {
                    "n_rows": 4,
                    "n_features": 2,
                    "target_rate": 0.5,
                    "needs_cleaning": True,
                    "feature_summaries": [{"feature": "age", "issue": "right_skew"}],
                    "correlation_flags": [],
                    "recommendations": ["Inspect skewed numeric features before modeling."],
                }
            }

        if "handoff_notes" in schema["properties"]:
            return {
                "parsed": {
                    "summary": "Impute the gaps and clip one outlier feature.",
                    "approved": False,
                    "cleaning_actions": [
                        {
                            "area": "cleaning",
                            "action": "clip_outliers_iqr",
                            "rationale": "Reduce extreme leverage points.",
                            "params": {"columns": ["claim_amount_avg"]},
                        }
                    ],
                    "feature_actions": [],
                    "handoff_notes": ["Preserve the target column."],
                }
            }

        return {
            "parsed": {
                "approved": True,
                "summary": "Processed data is ready for modeling.",
                "next_action": "accept_processed_data",
                "concerns": [],
                "recommendations": [],
            }
        }


def _settings() -> dict[str, Any]:
    """Minimal routing-shaped settings dict.

    ``build_adapter`` is monkeypatched in every test so this block is not
    normally exercised; keeping it well-formed means the harness fails
    informatively if the patch ever regresses.
    """
    return {
        "llm": {
            "default_provider": "openai",
            "model_matrix": {
                "balanced": {"cheap": "gpt-4.1-mini", "moderate": "gpt-4.1", "expensive": "gpt-4.1"},
            },
            "capability_settings": {
                "balanced": {"temperature": 0.2, "max_tokens": 1000},
            },
            "routes": {
                "default": {"capability": "balanced", "cost": "cheap"},
                "eda_analyst": {"capability": "balanced", "cost": "cheap"},
            },
        }
    }


def _fake_build_adapter(settings: dict[str, Any], *, agent: str, task: str | None) -> Any:
    return FakeAdapter(settings)


def _profile_result() -> dict[str, Any]:
    return {
        "data_path": "data/raw/sample.parquet",
        "target_column": "binary_target",
        "n_rows": 4,
        "n_features": 2,
        "profile": {
            "dataset_summary": {
                "n_rows": 4,
                "n_features": 2,
                "target_column": "binary_target",
                "excluded_metadata_columns": [],
                "numeric_features": ["age"],
                "categorical_features": ["state"],
            },
            "distributions": {"feature_counts": {"numeric": 1, "categorical": 1}},
            "target_analysis": {"positive_rate": 0.5},
            "correlations": {"high_correlation_pairs": [], "target_correlations": []},
            "feature_target_relationships": {
                "top_numerical_signals": [],
                "top_categorical_signals": [],
            },
            "outliers": {"flagged_features": []},
        },
    }


def _prompts() -> dict[str, Any]:
    return {
        "eda_analyst": {
            "system": "system prompt",
            "raw_review": "rows={n_rows}; features={n_features}; target_rate={target_rate}; {profile_json}",
            "prep_plan": (
                "raw={raw_eda_json}; modeler={ml_modeler_review_json}; "
                "review={ml_review_json}; business={business_review_json}; feedback={prep_feedback_json}"
            ),
            "processed_approval": (
                "processed={processed_eda_json}; modeler={ml_modeler_review_json}; "
                "review={ml_review_json}; business={business_review_json}"
            ),
        }
    }


def test_eda_analyst_node_profiles_raw_data(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.eda_analyst.build_adapter", _fake_build_adapter)
    monkeypatch.setattr("multi_agent_ds.agents.eda_analyst.load_prompts_config", _prompts)

    result = eda_analyst_node(
        {
            "settings": _settings(),
            "data": _profile_result(),
            "agent_decisions": [],
        },
        mode="raw",
    )

    assert result["raw_eda_insights"]["needs_cleaning"] is True
    assert result["agent_decisions"][0]["phase"] == "raw_eda"
    assert result["current_phase"] == "raw_eda"


def test_eda_analyst_node_builds_prep_plan(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.eda_analyst.build_adapter", _fake_build_adapter)
    monkeypatch.setattr("multi_agent_ds.agents.eda_analyst.load_prompts_config", _prompts)
    monkeypatch.setattr(
        "multi_agent_ds.agents.eda_analyst.load_workflows_config",
        lambda: {"workflows": {"eda_preparation": {"max_iterations": 3}}},
    )

    result = eda_analyst_node(
        {
            "settings": _settings(),
            "raw_eda_insights": {"needs_cleaning": True, "recommendations": ["clip claim_amount_avg"]},
            "raw_eda_ml_modeler_review": {"summary": "Modeling caution."},
            "raw_eda_ml_review": {"summary": "Scientific caution."},
            "raw_eda_business_review": {"summary": "Business caution."},
            "agent_decisions": [],
        },
        mode="prep_plan",
    )

    assert result["prep_plan"]["cleaning_actions"][0]["action"] == "clip_outliers_iqr"
    assert result["prep_approved"] is False
    assert result["prep_iteration"] == 1


def test_eda_analyst_node_approves_processed_data(monkeypatch) -> None:
    monkeypatch.setattr("multi_agent_ds.agents.eda_analyst.build_adapter", _fake_build_adapter)
    monkeypatch.setattr("multi_agent_ds.agents.eda_analyst.load_prompts_config", _prompts)
    monkeypatch.setattr(
        "multi_agent_ds.agents.eda_analyst.load_workflows_config",
        lambda: {"workflows": {"eda_preparation": {"max_iterations": 3}}},
    )

    result = eda_analyst_node(
        {
            "settings": _settings(),
            "processed_eda_insights": {"needs_cleaning": False, "recommendations": []},
            "processed_eda_ml_modeler_review": {"summary": "Looks ready."},
            "processed_eda_ml_review": {"summary": "Looks ready."},
            "processed_eda_business_review": {"summary": "Looks ready."},
            "prep_result": {},
            "agent_decisions": [],
        },
        mode="processed_approval",
    )

    assert result["processed_eda_approved"] is True
    assert result["prep_result"]["processed_approval"]["next_action"] == "accept_processed_data"
