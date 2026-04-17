"""EDA analyst agent."""

from __future__ import annotations

import json
from typing import Any

from multi_agent_ds.adapters.llm import build_adapter
from multi_agent_ds.core import load_prompts_config, load_settings, load_workflows_config
from multi_agent_ds.core.contracts import EDAOutput, PreparationPlanOutput, ProcessedApprovalOutput
from multi_agent_ds.orchestration.state import PipelineState
from multi_agent_ds.workflows.discovery import run_discovery_workflow


def _schema_for(model_cls: type[Any]) -> dict[str, Any]:
    """Return a JSON schema for the given pydantic model."""
    if hasattr(model_cls, "model_json_schema"):
        return model_cls.model_json_schema()
    return model_cls.schema()


def _dump_model(model_cls: type[Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a structured agent payload."""
    validated = model_cls(**payload)
    if hasattr(validated, "model_dump"):
        return validated.model_dump()
    return validated.dict()


def _workflow_iteration_limit() -> int:
    """Read the configured prep-loop iteration limit."""
    workflow_cfg = load_workflows_config()
    return int(workflow_cfg.get("workflows", {}).get("eda_preparation", {}).get("max_iterations", 3))


def _build_eda_messages(profile_result: dict[str, Any], prompts: dict[str, Any], prompt_key: str) -> list[dict[str, str]]:
    """Construct prompt messages for raw or processed EDA interpretation."""
    profile = profile_result["profile"]
    dataset_summary = profile["dataset_summary"]
    target_analysis = profile["target_analysis"]
    user_prompt = prompts[prompt_key].format(
        n_rows=dataset_summary["n_rows"],
        n_features=dataset_summary["n_features"],
        target_rate=target_analysis["positive_rate"],
        profile_json=json.dumps(profile, sort_keys=True),
    )
    return [
        {"role": "system", "content": prompts["system"]},
        {"role": "user", "content": user_prompt},
    ]


def _build_prep_plan_messages(state: PipelineState, prompts: dict[str, Any]) -> list[dict[str, str]]:
    """Construct the prep-planning prompt from raw EDA and reviewer feedback."""
    user_prompt = prompts["prep_plan"].format(
        raw_eda_json=json.dumps(state["raw_eda_insights"], sort_keys=True),
        ml_modeler_review_json=json.dumps(state.get("raw_eda_ml_modeler_review", {}), sort_keys=True),
        ml_review_json=json.dumps(state.get("raw_eda_ml_review", {}), sort_keys=True),
        business_review_json=json.dumps(state.get("raw_eda_business_review", {}), sort_keys=True),
        prep_feedback_json=json.dumps(state.get("prep_feedback", {}), sort_keys=True),
        prep_iteration=state.get("prep_iteration", 0) + 1,
        prep_iteration_limit=_workflow_iteration_limit(),
    )
    return [
        {"role": "system", "content": prompts["system"]},
        {"role": "user", "content": user_prompt},
    ]


def _build_processed_approval_messages(state: PipelineState, prompts: dict[str, Any]) -> list[dict[str, str]]:
    """Construct the processed-data approval prompt."""
    user_prompt = prompts["processed_approval"].format(
        processed_eda_json=json.dumps(state["processed_eda_insights"], sort_keys=True),
        ml_modeler_review_json=json.dumps(
            state.get("processed_eda_ml_modeler_review", {}),
            sort_keys=True,
        ),
        ml_review_json=json.dumps(state.get("processed_eda_ml_review", {}), sort_keys=True),
        business_review_json=json.dumps(
            state.get("processed_eda_business_review", {}),
            sort_keys=True,
        ),
        prep_iteration=state.get("prep_iteration", 0),
        prep_iteration_limit=_workflow_iteration_limit(),
    )
    return [
        {"role": "system", "content": prompts["system"]},
        {"role": "user", "content": user_prompt},
    ]


def _append_decision(state: PipelineState, phase: str, **payload: Any) -> list[dict[str, Any]]:
    """Return the delta to append to `agent_decisions`.

    `PipelineState.agent_decisions` uses an `operator.add` reducer, so nodes
    return only new entries; the reducer concatenates with the current value.
    Returning the full list here caused exponential duplication across nodes.
    """
    del state  # reducer handles accumulation; signature kept for symmetry
    return [{"agent": "eda_analyst", "phase": phase, **payload}]


# Map the agent-local mode string to the routing-table task name. Modes with
# no entry in routes['eda_analyst'] fall back to the agent-level shorthand.
_ROUTING_TASK_BY_MODE: dict[str, str] = {
    "raw": "eda_review",
    "processed": "eda_review",
    "prep_plan": "prep_plan",
    "processed_approval": "processed_approval",
}


def eda_analyst_node(state: PipelineState, mode: str = "raw") -> dict[str, Any]:
    """Run the requested EDA analyst stage."""
    settings = state.get("settings") or load_settings()
    prompts = load_prompts_config()["eda_analyst"]
    adapter = build_adapter(
        settings,
        agent="eda_analyst",
        task=_ROUTING_TASK_BY_MODE.get(mode, mode),
    )

    if mode == "raw":
        data_payload = state.get("data") or {}
        if isinstance(data_payload, dict) and "profile" in data_payload:
            profile_result = data_payload
        else:
            profile_result = run_discovery_workflow(
                data_path=state.get("data_path"),
                settings=settings,
            )
        response = adapter.structured_output(
            messages=_build_eda_messages(profile_result, prompts, "raw_review"),
            schema=_schema_for(EDAOutput),
        )
        eda_insights = _dump_model(EDAOutput, response["parsed"])
        return {
            "eda_insights": eda_insights,
            "raw_eda_insights": eda_insights,
            "data": profile_result,
            "agent_decisions": _append_decision(
                state,
                "raw_eda",
                needs_cleaning=eda_insights["needs_cleaning"],
                recommendations=eda_insights["recommendations"],
            ),
            "current_phase": "raw_eda",
        }

    if mode == "prep_plan":
        response = adapter.structured_output(
            messages=_build_prep_plan_messages(state, prompts),
            schema=_schema_for(PreparationPlanOutput),
        )
        prep_plan = _dump_model(PreparationPlanOutput, response["parsed"])
        return {
            "prep_plan": prep_plan,
            "prep_approved": prep_plan["approved"],
            "prep_iteration": state.get("prep_iteration", 0) + 1,
            "agent_decisions": _append_decision(
                state,
                "prep_plan",
                approved=prep_plan["approved"],
                action_count=len(prep_plan["cleaning_actions"]) + len(prep_plan["feature_actions"]),
            ),
            "current_phase": "prep_plan",
        }

    if mode == "processed":
        profile_result = run_discovery_workflow(
            data_path=state["processed_data_path"],
            settings=settings,
        )
        response = adapter.structured_output(
            messages=_build_eda_messages(profile_result, prompts, "raw_review"),
            schema=_schema_for(EDAOutput),
        )
        eda_insights = _dump_model(EDAOutput, response["parsed"])
        return {
            "processed_eda_insights": eda_insights,
            "agent_decisions": _append_decision(
                state,
                "processed_eda",
                needs_cleaning=eda_insights["needs_cleaning"],
                recommendations=eda_insights["recommendations"],
            ),
            "current_phase": "processed_eda",
        }

    if mode == "processed_approval":
        response = adapter.structured_output(
            messages=_build_processed_approval_messages(state, prompts),
            schema=_schema_for(ProcessedApprovalOutput),
        )
        approval = _dump_model(ProcessedApprovalOutput, response["parsed"])
        return {
            "processed_eda_approved": approval["approved"],
            "agent_decisions": _append_decision(
                state,
                "processed_approval",
                approved=approval["approved"],
                next_action=approval["next_action"],
            ),
            "current_phase": "processed_approval",
            "prep_result": state.get("prep_result", {}) | {"processed_approval": approval},
        }

    raise ValueError(f"Unsupported eda_analyst mode: {mode}")
