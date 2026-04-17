"""Demo recorder: run eda_analyst -> data_engineer as a minimal sub-graph
and write an event log to data/interim/demo_run_latest.json for later
replay by src/multi_agent_ds/demo_viewer.html.

This module is the 'record' half of the record-once-replay-many demo.
It lives at the orchestration layer and composes existing agent nodes
without modifying the production graph (src/multi_agent_ds/orchestration/graph.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
