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


# --- Sub-graph builder -------------------------------------------------

from functools import partial
from langgraph.graph import StateGraph, END

from multi_agent_ds.agents.eda_analyst import eda_analyst_node
from multi_agent_ds.agents.data_engineer import data_engineer_node
from multi_agent_ds.orchestration.state import PipelineState


def build_demo_subgraph():
    """Compile a minimal StateGraph with optional prep_plan stage.

    The graph is: eda_raw -> prep_plan_stage -> data_engineer -> END.
    Node names ('eda_raw', 'data_engineer') match RECORDED_NODES so
    should_record() filters the event stream. The prep_plan_stage is
    internal — the viewer only sees eda_raw and data_engineer events
    (simpler visual presentation) but the sub-graph internally runs
    all three nodes so data_engineer gets the prep plan it needs.
    """
    g = StateGraph(PipelineState)
    g.add_node("eda_raw", partial(eda_analyst_node, mode="raw"))
    # prep_plan_stage runs internally but is not recorded (keep viewer simple)
    g.add_node("prep_plan_stage", partial(eda_analyst_node, mode="prep_plan"))
    g.add_node("data_engineer", partial(data_engineer_node, mode="execute"))
    g.set_entry_point("eda_raw")
    g.add_edge("eda_raw", "prep_plan_stage")
    g.add_edge("prep_plan_stage", "data_engineer")
    g.add_edge("data_engineer", END)
    return g.compile()


# --- Preflight guards --------------------------------------------------

def preflight(*, parquet_path: Path) -> None:
    """Raise early with a clear message if the recorder can't run.

    Checked conditions:
      - OPENAI_API_KEY must be set (EnvironmentError, mirrors
        adapters/llm/openai.py)
      - parquet_path must exist on disk (FileNotFoundError, includes
        the resolved absolute path in the message)

    Called before any graph invocation or file write so partial JSON
    is never produced.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Set it in your environment or .env "
            "before running the demo recorder. The recorder invokes LLM "
            "agents and cannot proceed without an API key."
        )
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Input parquet not found at {parquet_path.resolve()}. "
            f"Check config/settings.yaml -> data.source or pass --parquet."
        )


# --- Async driver ------------------------------------------------------

import asyncio
import time

import pandas as pd

from multi_agent_ds.core.config import load_settings


async def record_run(
    *,
    parquet_path: Path,
    output_path: Path,
    target_column: str | None = None,
) -> dict[str, Any]:
    """Record one eda_raw -> data_engineer run and write the event log.

    Returns the payload dict that was written (handy for tests and the CLI
    to report a summary).

    Flow:
      1. preflight() — fail fast on missing env / parquet
      2. load settings and raw DataFrame
      3. seed input_df_head / input_df_stats into the initial state
      4. compile the sub-graph
      5. async-iterate astream_events(version='v2'), record filtered events
      6. collect final state, extract artifacts, assemble payload
      7. atomic_write_json to output_path
    """
    preflight(parquet_path=parquet_path)

    settings = load_settings()
    target = target_column or _resolve_target(settings)

    df = pd.read_parquet(parquet_path)
    input_df_head = df.head(10).to_dict(orient="records")
    input_df_stats = _compute_input_stats(df, target=target)

    initial_state: dict[str, Any] = {
        "data_path": str(parquet_path),
        # state["data"] expects dict[str, Any] (see PipelineState); DataFrame passes via data_path
        "settings": settings,
        "input_df_head": input_df_head,
        "input_df_stats": input_df_stats,
    }

    graph = build_demo_subgraph()

    events: list[dict[str, Any]] = []
    final_state: dict[str, Any] = dict(initial_state)
    start_monotonic = time.monotonic()
    start_ts = datetime.now(timezone.utc)

    async for lg_event in graph.astream_events(input=initial_state, version="v2"):
        if not should_record(lg_event):
            continue
        elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)
        ts = iso_utc(datetime.now(timezone.utc))
        safe_data = sanitize_payload(lg_event.get("data", {}))
        normalized = normalize_event({**lg_event, "data": safe_data}, ts=ts, elapsed_ms=elapsed_ms)
        events.append(normalized.to_dict())
        # Keep a running copy of the final state by merging end-event outputs.
        if normalized.kind == NODE_END and isinstance(safe_data.get("output"), dict):
            final_state.update(safe_data["output"])

    # Read processed parquet and populate processed_df_head / processed_df_stats
    processed_path = final_state.get("processed_data_path")
    if processed_path and Path(processed_path).exists():
        pdf = pd.read_parquet(processed_path)
        final_state["processed_df_head"] = pdf.head(10).to_dict(orient="records")
        missing_pct = round(float(pdf.isna().mean().mean()) * 100.0, 3)
        final_state["processed_df_stats"] = {
            "rows": int(pdf.shape[0]),
            "cols": int(pdf.shape[1]),
            "path": processed_path,
            "missing_pct_after": missing_pct,
        }

    duration_ms = int((time.monotonic() - start_monotonic) * 1000)
    artifacts = extract_artifacts(final_state)

    payload = {
        "recorded_at": iso_utc(start_ts),
        "duration_ms": duration_ms,
        "config": _config_snapshot(settings, parquet_path=str(parquet_path)),
        "artifacts": artifacts,
        "events": events,
    }
    atomic_write_json(payload, output_path)
    return payload


def _compute_input_stats(df: pd.DataFrame, *, target: str) -> dict[str, Any]:
    """Tiny stats block consumed by the Input Preview screen."""
    numeric = df.select_dtypes(include="number").shape[1]
    categorical = df.shape[1] - numeric
    missing_pct = float(df.isna().mean().mean()) * 100.0
    positive_rate: float | None = None
    if target in df.columns and pd.api.types.is_numeric_dtype(df[target]):
        positive_rate = float(df[target].astype(float).mean())
    return {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "target": target,
        "positive_rate": positive_rate,
        "numeric": int(numeric),
        "categorical": int(categorical),
        "missing_pct": round(missing_pct, 3),
    }


def _resolve_target(settings: dict[str, Any]) -> str:
    """Resolve the target column name from settings."""
    data = settings.get("data", {})
    source_mode = data.get("source", "synthetic")
    if source_mode == "synthetic":
        return data.get("synthetic", {}).get("target", {}).get("column_name", "target")
    else:
        return data.get("existing", {}).get("target_column", "target")


def _config_snapshot(settings: dict[str, Any], *, parquet_path: str) -> dict[str, Any]:
    """Project settings into the small dict the Config screen shows."""
    data = settings.get("data", {})
    source_mode = data.get("source", "synthetic")
    syn = data.get("synthetic", {})
    existing = data.get("existing", {})
    target = (
        syn.get("target", {}).get("column_name")
        if source_mode == "synthetic"
        else existing.get("target_column")
    )
    scale = syn.get("scale") if source_mode == "synthetic" else "existing"
    model = settings.get("model", {})
    tuning = model.get("tuning", {})
    return {
        "source": str(parquet_path),
        "source_mode": source_mode,
        "target": target,
        "scale": scale,
        "max_trials": tuning.get("max_trials"),
        "cv_folds": model.get("cv_folds"),
        "timeout": tuning.get("timeout"),
        "algorithms": list(model.get("algorithms", [])),
        "primary_metric": model.get("primary_metric"),
        "tiebreaker": None,  # not configured in settings.yaml
        "ml_reviewer": "enabled",  # placeholder; adjust once real routing config is wired
        "business_stakeholder": "enabled",
        "report_writer": "enabled",
        "tracing": settings.get("llm", {}).get("tracing", "disabled"),
        # no `review` block exists in settings.yaml; omit or set None
        "review_enabled": None,
        "review_threshold": None,
    }
