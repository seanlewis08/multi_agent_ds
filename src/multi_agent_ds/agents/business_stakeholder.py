"""Business stakeholder agent."""

from __future__ import annotations

import json
from typing import Any

from multi_agent_ds.adapters.llm import build_adapter
from multi_agent_ds.core import load_prompts_config, load_settings
from multi_agent_ds.core.contracts import BusinessReviewOutput, EDAReviewOutput
from multi_agent_ds.orchestration.state import PipelineState
from multi_agent_ds.tools.reporting import (
    format_evaluation_summary,
    format_modeling_summary,
)

_EDA_MODES = {"raw_review", "processed_review"}
_REPORT_MODE = "report_review"
_SUPPORTED_MODES = _EDA_MODES | {_REPORT_MODE}


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
    return state.get("agent_decisions", []) + [
        {"agent": "business_stakeholder", "phase": phase, **payload}
    ]


def business_stakeholder_node(state: PipelineState, mode: str = "raw_review") -> dict[str, Any]:
    """Review raw/processed EDA or the final stakeholder report."""
    if mode not in _SUPPORTED_MODES:
        raise ValueError(
            f"Unsupported mode '{mode}' for business_stakeholder_node. "
            f"Expected one of: {sorted(_SUPPORTED_MODES)}."
        )

    settings = state.get("settings") or load_settings()
    prompts = load_prompts_config()["business_stakeholder"]
    adapter = build_adapter(settings, agent="business_stakeholder", task=mode)

    if mode in _EDA_MODES:
        review_stage = "raw" if mode == "raw_review" else "processed"
        eda_payload = (
            state["raw_eda_insights"]
            if review_stage == "raw"
            else state["processed_eda_insights"]
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
        review_key = (
            "raw_eda_business_review" if review_stage == "raw" else "processed_eda_business_review"
        )
        return {
            review_key: review,
            "agent_decisions": _append_decision(
                state,
                f"{review_stage}_eda_review",
                review_key=review_key,
            ),
        }

    # report_review
    if not state.get("experiment_report"):
        raise ValueError(
            "business_stakeholder_node(mode='report_review') requires "
            "state['experiment_report']. Run the report_writer first."
        )

    modeling_block = format_modeling_summary(
        state.get("modeling_verdict") or {}, state.get("modeling_results", {})
    )
    evaluation_block = format_evaluation_summary(state.get("evaluation_result"))

    response = adapter.structured_output(
        messages=[
            {"role": "system", "content": prompts["system"]},
            {
                "role": "user",
                "content": prompts["report_review"].format(
                    report_markdown=state["experiment_report"],
                    modeling_summary=modeling_block,
                    evaluation_summary=evaluation_block,
                ),
            },
        ],
        schema=_schema_for(BusinessReviewOutput),
    )
    review = _dump_model(BusinessReviewOutput, response["parsed"])
    return {
        "business_review": review,
        "should_revise_report": review["next_action"] == "revise_report",
        "should_revise_modeling": review["next_action"] == "revise_modeling",
        "agent_decisions": _append_decision(
            state,
            "report_review",
            approved=review["approved"],
            next_action=review["next_action"],
            summary=review["summary"],
        ),
        "current_phase": "report_review",
    }
