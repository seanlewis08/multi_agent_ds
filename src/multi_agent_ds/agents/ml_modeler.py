"""Machine learning modeler agent for pre-fit EDA review and modeling handoff."""

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
    return state.get("agent_decisions", []) + [{"agent": "ml_modeler", "phase": phase, **payload}]


def _review_payload(state: PipelineState, review_stage: str) -> dict[str, Any]:
    if review_stage == "raw":
        return state["raw_eda_insights"]
    return state["processed_eda_insights"]


def ml_modeler_node(state: PipelineState, mode: str = "eda_review") -> dict[str, Any]:
    """Run the requested ml_modeler stage."""
    settings = state.get("settings") or load_settings()

    if mode in {"raw_review", "processed_review"}:
        prompts = load_prompts_config()["sean_ml_modeler"]
        review_stage = "raw" if mode == "raw_review" else "processed"
        adapter = OpenAIAdapter(settings)
        response = adapter.structured_output(
            messages=[
                {"role": "system", "content": prompts["system"]},
                {
                    "role": "user",
                    "content": prompts["eda_review"].format(
                        eda_json=json.dumps(_review_payload(state, review_stage), sort_keys=True),
                        review_stage=review_stage,
                    ),
                },
            ],
            schema=_schema_for(EDAReviewOutput),
        )
        review = _dump_model(EDAReviewOutput, response["parsed"])
        review_key = (
            "raw_eda_ml_modeler_review" if review_stage == "raw" else "processed_eda_ml_modeler_review"
        )
        return {
            review_key: review,
            "agent_decisions": _append_decision(
                state,
                f"{review_stage}_eda_review",
                review_key=review_key,
            ),
        }

    if mode == "modeling_handoff":
        modeling_context = {
            "processed_data_path": state.get("processed_data_path"),
            "processed_eda_insights": state.get("processed_eda_insights"),
            "raw_eda_reviews": {
                "ml_modeler": state.get("raw_eda_ml_modeler_review"),
                "ml_reviewer": state.get("raw_eda_ml_review"),
                "business_stakeholder": state.get("raw_eda_business_review"),
            },
            "processed_eda_reviews": {
                "ml_modeler": state.get("processed_eda_ml_modeler_review"),
                "ml_reviewer": state.get("processed_eda_ml_review"),
                "business_stakeholder": state.get("processed_eda_business_review"),
            },
        }
        return {
            "modeling_context": modeling_context,
            "agent_decisions": _append_decision(
                state,
                "modeling_handoff",
                processed_data_path=state.get("processed_data_path"),
            ),
            "current_phase": "modeling",
        }

    raise ValueError(f"Unsupported ml_modeler mode: {mode}")
