"""Machine learning reviewer agent."""

from __future__ import annotations

import json
from typing import Any

from multi_agent_ds.adapters.llm import OpenAIAdapter
from multi_agent_ds.core import load_prompts_config, load_settings
from multi_agent_ds.core.contracts import EDAReviewOutput
from multi_agent_ds.orchestration.state import PipelineState


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


def ml_reviewer_node(state: PipelineState, mode: str = "raw_review") -> dict[str, Any]:
    """Review raw or processed EDA from a mathematical perspective."""
    if mode not in {"raw_review", "processed_review"}:
        raise ValueError(f"Unsupported mode: {mode}. Expected one of: raw_review, processed_review")

    settings = state.get("settings") or load_settings()
    prompts = load_prompts_config()["ml_reviewer"]
    review_stage = "raw" if mode == "raw_review" else "processed"
    eda_payload = state["raw_eda_insights"] if review_stage == "raw" else state["processed_eda_insights"]

    adapter = OpenAIAdapter(settings)
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
