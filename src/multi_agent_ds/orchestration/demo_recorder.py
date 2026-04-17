"""Demo recorder: run eda_analyst -> data_engineer as a minimal sub-graph
and write an event log to data/interim/demo_run_latest.json for later
replay by src/multi_agent_ds/demo_viewer.html.

This module is the 'record' half of the record-once-replay-many demo.
It lives at the orchestration layer and composes existing agent nodes
without modifying the production graph (src/multi_agent_ds/orchestration/graph.py).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Node kinds we expose in the event log. Keep this a closed enum — the viewer
# relies on these exact strings.
NODE_START = "node_start"
NODE_END = "node_end"
NODE_ERROR = "node_error"

# LangGraph event kinds we care about. We filter events by kind and by node
# name so the log stays small and replay-friendly.
LG_ON_CHAIN_START = "on_chain_start"
LG_ON_CHAIN_END = "on_chain_end"
LG_ON_CHAIN_ERROR = "on_chain_error"

# Nodes we record. The prep_plan_stage is internal and not shown in the viewer
# (visually simpler — only two recorded agent columns). Other node-level events
# (if any emerge from sub-runnables) are ignored by the recorder.
RECORDED_NODES = frozenset({"eda_raw", "data_engineer"})


@dataclass(frozen=True)
class NormalizedEvent:
    """A flat, JSON-serializable shape the viewer consumes."""
    ts: str              # ISO-8601 UTC, ends in 'Z'
    elapsed_ms: int      # ms since recording started
    kind: str            # one of NODE_START / NODE_END / NODE_ERROR
    node: str            # node name from LangGraph (e.g. 'eda_raw')
    data: dict[str, Any] # payload (input or output) — small, JSON-safe

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "elapsed_ms": self.elapsed_ms,
            "kind": self.kind,
            "node": self.node,
            "data": self.data,
        }


def iso_utc(now: datetime) -> str:
    """Format a datetime as ISO-8601 with 'Z' suffix.

    Input must be tz-aware; naive datetimes will raise on `.astimezone(...)`.
    """
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def langgraph_event_kind(lg_event: str) -> str | None:
    """Translate a LangGraph event string into our closed vocabulary.

    Returns None for events we do not record.
    """
    return {
        LG_ON_CHAIN_START: NODE_START,
        LG_ON_CHAIN_END: NODE_END,
        LG_ON_CHAIN_ERROR: NODE_ERROR,
    }.get(lg_event)


def should_record(lg_event: dict[str, Any]) -> bool:
    """Return True iff this LangGraph event should appear in the log.

    Gates on both event kind (on_chain_*) and node name (eda_raw / data_engineer).
    Rejects LLM-level events (on_llm_*, on_chat_model_*) and sub-tool events.
    """
    if langgraph_event_kind(lg_event.get("event", "")) is None:
        return False
    name = lg_event.get("name", "")
    return name in RECORDED_NODES


def normalize_event(
    lg_event: dict[str, Any],
    *,
    ts: str,
    elapsed_ms: int,
) -> NormalizedEvent:
    """Convert a LangGraph v2 event dict into our NormalizedEvent shape.

    Preconditions: should_record(lg_event) is True.

    The `data` field is the LangGraph event's `data` payload, shallow-copied
    and filtered to primitives we can JSON-serialize safely. Callers must
    ensure non-JSON-safe values (e.g. DataFrames) are stripped BEFORE calling
    — see sanitize_payload in Task 2.
    """
    kind = langgraph_event_kind(lg_event["event"])
    assert kind is not None, "should_record lied about event"
    return NormalizedEvent(
        ts=ts,
        elapsed_ms=elapsed_ms,
        kind=kind,
        node=lg_event["name"],
        data=dict(lg_event.get("data", {})),
    )


# --- Artifact extraction (pure) ----------------------------------------

# Keys we copy out of PipelineState into the top-level artifacts block.
# Stay minimal — the viewer only needs these.
_EDA_ARTIFACT_KEY = "raw_eda_insights"
_DE_PREP_PLAN_KEY = "prep_plan"
_DE_PROCESSED_DF_HEAD_KEY = "processed_df_head"   # added by recorder post-run from parquet
_DE_PROCESSED_DF_STATS_KEY = "processed_df_stats" # added by recorder post-run from parquet
_INPUT_DF_HEAD_KEY = "input_df_head"              # added by recorder pre-run
_INPUT_DF_STATS_KEY = "input_df_stats"            # added by recorder pre-run


def extract_artifacts(final_state: dict[str, Any]) -> dict[str, Any]:
    """Pull the viewer-facing artifact dict out of the final PipelineState.

    Missing keys resolve to None (not an error) so the recorder can still
    produce a JSON even when the graph halted early. The viewer treats
    None as 'unavailable'.
    """
    return {
        "raw_eda_insights": final_state.get(_EDA_ARTIFACT_KEY),
        "prep_plan": final_state.get(_DE_PREP_PLAN_KEY),
        "processed_df_head": final_state.get(_DE_PROCESSED_DF_HEAD_KEY),
        "processed_df_stats": final_state.get(_DE_PROCESSED_DF_STATS_KEY),
        "input_df_head": final_state.get(_INPUT_DF_HEAD_KEY),
        "input_df_stats": final_state.get(_INPUT_DF_STATS_KEY),
    }


# --- Payload sanitization (pure) ---------------------------------------

def sanitize_payload(value: Any, *, max_depth: int = 6) -> Any:
    """Recursively strip non-JSON-serializable values from an event payload.

    Policy:
      - primitives pass through
      - dict / list / tuple recurse
      - anything else (DataFrame, numpy array, Series, objects) becomes
        its repr() truncated to 200 chars
      - depth cap prevents infinite recursion on circular refs

    This runs on every LangGraph event `data` field before we stash it.
    """
    if max_depth <= 0:
        return f"<max-depth: {type(value).__name__}>"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): sanitize_payload(v, max_depth=max_depth - 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_payload(v, max_depth=max_depth - 1) for v in value]
    # Fallback: repr-truncate anything else (DataFrame, ndarray, custom classes).
    r = repr(value)
    return r if len(r) <= 200 else r[:197] + "..."


# --- Atomic write (impure, but narrow and well-tested) -----------------


def atomic_write_json(payload: dict[str, Any], target: Path) -> None:
    """Write `payload` as JSON to `target` atomically.

    Writes to `target.with_suffix(target.suffix + '.tmp')` first, then
    os.replace() to the target path. This guarantees that readers never
    see a half-written file: either the old JSON (previous demo run) or
    the new JSON — never a truncated blend.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False, default=str), encoding="utf-8")
    os.replace(tmp, target)
