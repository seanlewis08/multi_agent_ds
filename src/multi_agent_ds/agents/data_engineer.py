"""Data engineer agent for plan feedback and approved preparation execution."""

from __future__ import annotations

import json
from typing import Any

from multi_agent_ds.adapters.llm import build_adapter
from multi_agent_ds.core import load_prompts_config, load_settings
from multi_agent_ds.core.contracts import PreparationFeedbackOutput
from multi_agent_ds.orchestration.state import PipelineState
from multi_agent_ds.workflows.preparation import run_preparation_workflow


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
    return state.get("agent_decisions", []) + [{"agent": "data_engineer", "phase": phase, **payload}]


def data_engineer_node(state: PipelineState, mode: str = "feedback") -> dict[str, Any]:
    """Run the requested data-engineering stage."""
    settings = state.get("settings") or load_settings()

    if mode == "feedback":
        prompts = load_prompts_config()["data_engineer"]
        adapter = build_adapter(settings, agent="data_engineer", task="feedback")
        response = adapter.structured_output(
            messages=[
                {"role": "system", "content": prompts["system"]},
                {
                    "role": "user",
                    "content": prompts["plan_feedback"].format(
                        prep_plan_json=json.dumps(state["prep_plan"], sort_keys=True),
                        raw_eda_json=json.dumps(state["raw_eda_insights"], sort_keys=True),
                    ),
                },
            ],
            schema=_schema_for(PreparationFeedbackOutput),
        )
        feedback = _dump_model(PreparationFeedbackOutput, response["parsed"])
        return {
            "prep_feedback": feedback,
            "agent_decisions": _append_decision(
                state,
                "prep_feedback",
                summary=feedback["summary"],
                ready_for_execution=feedback["ready_for_execution"],
                action_feedback_count=len(feedback["action_feedback"]),
            ),
            "current_phase": "prep_feedback",
        }

    if mode == "execute":
        local_only = state.get("local_only", False)
        prep_result = run_preparation_workflow(
            data_path=state["data_path"],
            prep_plan=state["prep_plan"],
            settings=settings,
            local_only=local_only,
        )
        return {
            "processed_data_path": prep_result["processed_data_path"],
            "prep_result": prep_result,
            "agent_decisions": _append_decision(
                state,
                "prep_execute",
                artifact_filename=prep_result.get("artifact_filename"),
                processed_data_path=prep_result["processed_data_path"],
                target_column=prep_result.get("target_column"),
                processed_n_rows=prep_result.get("processed_n_rows", prep_result.get("n_rows")),
                processed_n_features=prep_result.get("processed_n_features", prep_result.get("n_features")),
            ),
            "current_phase": "prep_execute",
        }

    raise ValueError(f"Unsupported data_engineer mode: {mode}")
