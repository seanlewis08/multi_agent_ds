"""Report writer agent — synthesizes a non-technical experiment summary."""

from __future__ import annotations

from typing import Any

from multi_agent_ds.adapters.llm import build_adapter
from multi_agent_ds.core import load_prompts_config, load_settings
from multi_agent_ds.orchestration.state import PipelineState
from multi_agent_ds.tools.reporting import (
    format_data_summary,
    format_decision_trace,
    format_evaluation_summary,
    format_modeling_summary,
)

_GENERATE_MODES = {"generate"}


def _append_decision(state: PipelineState, phase: str, **payload: Any) -> list[dict[str, Any]]:
    """Return the delta for `agent_decisions` (reducer concatenates)."""
    del state  # `PipelineState.agent_decisions` uses operator.add; return delta only
    return [{"agent": "report_writer", "phase": phase, **payload}]


def _next_report_iteration(state: PipelineState) -> int:
    """Increment the report-iteration counter on a revise loop-back."""
    if state.get("current_phase") == "report_generate":
        return state.get("report_iteration", 0) + 1
    return 1


def _critique_section(state: PipelineState) -> str:
    """Format the prior business reviewer's critique for the rewrite prompt.

    Returns an empty string on first generation. On loop-back (the business
    stakeholder set should_revise_report=True), surfaces the reviewer's summary
    and concrete concerns so the writer can answer them in the next draft.
    """
    review = state.get("business_review")
    if not review or review.get("next_action") != "revise_report":
        return ""
    concerns_block = "\n".join(
        f"- {c.get('topic', '?')}: {c.get('issue', '')}"
        for c in review.get("concerns", []) or []
    ) or "- (no specific concerns enumerated)"
    return (
        "Prior business reviewer critique (you are rewriting after a "
        "revise_report verdict):\n"
        f"Summary: {review.get('summary', '(no summary)')}\n"
        f"Readability assessment: {review.get('readability_assessment', '')}\n"
        f"Plausibility assessment: {review.get('plausibility_assessment', '')}\n"
        "Concerns:\n"
        f"{concerns_block}\n\n"
    )


def report_writer_node(state: PipelineState, mode: str = "generate") -> dict[str, Any]:
    """Generate a non-technical experiment summary from final pipeline state."""
    if mode not in _GENERATE_MODES:
        raise ValueError(
            f"Unsupported mode '{mode}' for report_writer_node. "
            f"Expected one of: {sorted(_GENERATE_MODES)}."
        )

    if not state.get("modeling_verdict"):
        raise ValueError(
            "report_writer_node requires state['modeling_verdict']. Run the "
            "ml_modeler final_recommendation phase before generating the report."
        )

    settings = state.get("settings") or load_settings()
    prompts = load_prompts_config()["report_writer"]

    data_summary = (state.get("data") or {}).get("data_summary") or {}
    data_block = format_data_summary(data_summary)
    modeling_block = format_modeling_summary(
        state["modeling_verdict"], state.get("modeling_results", {})
    )
    evaluation_block = format_evaluation_summary(state.get("evaluation_result"))
    decision_block = format_decision_trace(state.get("agent_decisions", []))
    critique_block = _critique_section(state)

    adapter = build_adapter(settings, agent="report_writer", task=mode)
    response = adapter.chat(
        messages=[
            {"role": "system", "content": prompts["system"]},
            {
                "role": "user",
                "content": prompts["generate"].format(
                    critique_section=critique_block,
                    data_summary=data_block,
                    modeling_summary=modeling_block,
                    evaluation_summary=evaluation_block,
                    decision_trace=decision_block,
                ),
            },
        ],
    )
    report_md = (response.get("content") or "").strip()

    return {
        "experiment_report": report_md,
        "report_draft": report_md,
        "agent_decisions": _append_decision(
            state,
            "report_generate",
            evaluation_available=state.get("evaluation_result") is not None,
            characters=len(report_md),
            iteration=_next_report_iteration(state),
        ),
        "current_phase": "report_generate",
        "report_iteration": _next_report_iteration(state),
    }
