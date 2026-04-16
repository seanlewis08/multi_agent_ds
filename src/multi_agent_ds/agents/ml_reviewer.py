"""Machine learning reviewer agent."""

from __future__ import annotations

import json
from typing import Any

from multi_agent_ds.adapters.llm import OpenAIAdapter
from multi_agent_ds.core import load_prompts_config, load_settings
from multi_agent_ds.core.contracts import EDAReviewOutput, MLReviewOutput
from multi_agent_ds.orchestration.state import PipelineState

_EDA_MODES = {"raw_review", "processed_review"}
_MODELING_REVIEW_MODES = {
    "baseline_review": "baseline",
    "tuning_review": "tune",
    "lr_adjustment_review": "adjust_lr",
    "feature_selection_review": "feature_selection",
    "final_recommendation_review": "final_recommendation",
}
_BASELINE_STRIP_KEYS = ("model", "y_pred", "y_prob")
_TUNING_STRIP_KEYS = ("trial_history",)


def _schema_for(model_cls: type[Any]) -> dict[str, Any]:
    if hasattr(model_cls, "model_json_schema"):
        return model_cls.model_json_schema()
    return model_cls.schema()


def _dump_model(model_cls: type[Any], payload: dict[str, Any]) -> dict[str, Any]:
    validated = model_cls(**payload)
    if hasattr(validated, "model_dump"):
        return validated.model_dump()
    return validated.dict()


def _append_decision(state: PipelineState, phase: str, **payload: Any) -> list[dict[str, Any]]:
    return state.get("agent_decisions", []) + [{"agent": "ml_reviewer", "phase": phase, **payload}]


def _strip_nested(bundle: dict[str, Any], drop_keys: tuple[str, ...]) -> dict[str, Any]:
    """Drop non-serializable / verbose keys from per-algo result dicts."""
    return {
        algo: {k: v for k, v in result.items() if k not in drop_keys}
        for algo, result in bundle.items()
    }


def _modeling_payload(state: PipelineState, phase: str) -> dict[str, Any]:
    """Build the {decision + underlying_skill_output} payload the reviewer inspects."""
    results = state["modeling_results"]
    if phase == "baseline":
        return {
            "decision": results["baseline_decision"],
            "baseline_results": _strip_nested(results["baseline"], _BASELINE_STRIP_KEYS),
        }
    if phase == "tune":
        return {
            "decisions": results["tuning_decisions"],
            "tuning_results": _strip_nested(results["tuning"], _TUNING_STRIP_KEYS),
        }
    if phase == "adjust_lr":
        return {
            "decisions": results["adjust_lr_decisions"],
            "adjust_lr_results": _strip_nested(results["adjust_lr"], _BASELINE_STRIP_KEYS),
        }
    if phase == "feature_selection":
        return {
            "decisions": results["feature_selection_decisions"],
            "feature_selection_results": _strip_nested(
                results["feature_selection"], _BASELINE_STRIP_KEYS
            ),
            "importances": results.get("importances", {}),
        }
    if phase == "final_recommendation":
        return {
            "verdict": state["modeling_verdict"],
            "final_candidates": results.get("final_candidates", {}),
        }
    raise ValueError(f"Unknown modeling phase for reviewer: {phase}")


def ml_reviewer_node(state: PipelineState, mode: str = "raw_review") -> dict[str, Any]:
    """Review raw/processed EDA or a modeler decision from a mathematical perspective."""
    if mode not in _EDA_MODES and mode not in _MODELING_REVIEW_MODES:
        allowed = sorted(_EDA_MODES | _MODELING_REVIEW_MODES.keys())
        raise ValueError(f"Unsupported mode: {mode}. Expected one of: {allowed}")

    settings = state.get("settings") or load_settings()
    prompts = load_prompts_config()["ml_reviewer"]
    adapter = OpenAIAdapter(settings)

    if mode in _EDA_MODES:
        review_stage = "raw" if mode == "raw_review" else "processed"
        eda_payload = (
            state["raw_eda_insights"] if review_stage == "raw" else state["processed_eda_insights"]
        )
        response = adapter.structured_output(
            messages=[
                {"role": "system", "content": prompts["system"]},
                {
                    "role": "user",
                    "content": prompts["eda_review"].format(
                        eda_json=json.dumps(eda_payload, sort_keys=True),
                        review_stage=review_stage,
                    ),
                },
            ],
            schema=_schema_for(EDAReviewOutput),
        )
        review = _dump_model(EDAReviewOutput, response["parsed"])
        review_key = "raw_eda_ml_review" if review_stage == "raw" else "processed_eda_ml_review"
        return {
            review_key: review,
            "agent_decisions": _append_decision(
                state,
                f"{review_stage}_eda_review",
                review_key=review_key,
            ),
        }

    phase = _MODELING_REVIEW_MODES[mode]
    payload = _modeling_payload(state, phase)
    response = adapter.structured_output(
        messages=[
            {"role": "system", "content": prompts["system"]},
            {
                "role": "user",
                "content": prompts[mode].format(
                    phase=phase,
                    payload_json=json.dumps(payload, sort_keys=True, default=str),
                ),
            },
        ],
        schema=_schema_for(MLReviewOutput),
    )
    review = _dump_model(MLReviewOutput, response["parsed"])
    review["phase"] = review.get("phase") or phase
    prior_reviews = state.get("ml_review", {})
    return {
        "ml_review": prior_reviews | {phase: review},
        "should_revise_modeling": review["next_action"] == "revise_modeling",
        "agent_decisions": _append_decision(
            state,
            mode,
            review_phase=phase,
            approved=review["approved"],
            next_action=review["next_action"],
            summary=review["summary"],
        ),
    }
