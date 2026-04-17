"""Full agentic pipeline workflow with conversation recording."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multi_agent_ds.core import load_settings
from multi_agent_ds.orchestration.graph import build_graph
from multi_agent_ds.tools.conversation_recorder import (
    ConversationRecorder,
    NodeBoundary,
    conversation_recording,
)
from multi_agent_ds.tools.html_report import write_conversation_html

logger = logging.getLogger(__name__)

# Names emitted by LangGraph that do not correspond to user-defined graph nodes.
_GRAPH_INTERNAL_NAMES: frozenset[str] = frozenset({"LangGraph", "__start__", "__end__"})

# Keys on a PipelineState-shaped dict we treat as proof the event output is a
# real pipeline state (vs. an arbitrary inner chain output).
_PIPELINE_STATE_KEYS: frozenset[str] = frozenset(
    {
        "agent_decisions",
        "data_path",
        "settings",
        "modeling_verdict",
        "business_review",
    }
)


def _is_graph_node_name(name: Any) -> bool:
    """True if ``name`` looks like a real graph node (not LangGraph internals)."""
    if not isinstance(name, str):
        return False
    if name in _GRAPH_INTERNAL_NAMES:
        return False
    if name.startswith("__"):
        return False
    return True


def _looks_like_pipeline_state(output: Any) -> bool:
    """True if ``output`` is a dict that contains any PipelineState-shaped key."""
    if not isinstance(output, dict):
        return False
    return bool(_PIPELINE_STATE_KEYS & set(output.keys()))


async def _astream_and_record(
    compiled: Any,
    initial_state: dict[str, Any],
    recorder: ConversationRecorder | None,
    t0: float,
) -> dict[str, Any]:
    """Drive the compiled graph via ``astream_events`` and capture boundaries.

    Returns the best-guess final state — the output of the last ``on_chain_end``
    event whose ``output`` looks like a PipelineState dict. Since LangGraph
    emits progressively richer state snapshots on each node end (the reducer
    accumulates), the last such snapshot is the final state.

    If ``recorder`` is None, we still drive the graph via ``astream_events`` so
    that behavior stays consistent between recorded and non-recorded runs.
    """
    final_state: dict[str, Any] = {}
    async for event in compiled.astream_events(initial_state, version="v2"):
        event_name = event.get("event") if isinstance(event, dict) else None
        node_name = event.get("name") if isinstance(event, dict) else None
        if not _is_graph_node_name(node_name):
            # Still inspect on_chain_end outputs for the final-state heuristic
            # even for wrapper names.
            pass

        ts_iso = datetime.now(timezone.utc).isoformat()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if recorder is not None and _is_graph_node_name(node_name):
            if event_name == "on_chain_start":
                recorder.record_boundary(
                    NodeBoundary(
                        kind="start", node=node_name, ts=ts_iso, elapsed_ms=elapsed_ms
                    )
                )
            elif event_name == "on_chain_end":
                recorder.record_boundary(
                    NodeBoundary(
                        kind="end", node=node_name, ts=ts_iso, elapsed_ms=elapsed_ms
                    )
                )
            elif event_name == "on_chain_error":
                recorder.record_boundary(
                    NodeBoundary(
                        kind="error", node=node_name, ts=ts_iso, elapsed_ms=elapsed_ms
                    )
                )

        # Final-state heuristic: the last on_chain_end output that looks like a
        # PipelineState wins. This works for both root-level and node-level
        # events because LangGraph's reducer produces progressively-richer
        # snapshots, so the temporally-last one is the full final state.
        if event_name == "on_chain_end":
            data = event.get("data") if isinstance(event, dict) else None
            output = data.get("output") if isinstance(data, dict) else None
            if _looks_like_pipeline_state(output):
                final_state = output

    return final_state


async def run_full_pipeline(
    data_path: str | None = None,
    settings: dict[str, Any] | None = None,
    entry_node: str = "eda_raw",
    html_output: str | Path | None = None,
    record: bool = True,
) -> dict[str, Any]:
    """Run the compiled LangGraph pipeline end-to-end and optionally record it.

    Returns a dict containing the final state, the path to the HTML report
    (when recording is enabled), and top-level run metadata (start time,
    duration, turn count, error).
    """
    settings = settings or load_settings()
    initial_state: dict[str, Any] = {
        "data_path": data_path,
        "settings": settings,
        "agent_decisions": [],
        "iteration": 0,
        "modeling_iteration": 0,
        "report_iteration": 0,
        "prep_iteration": 0,
        "local_only": False,
        "dry_run": False,
    }
    compiled = build_graph(entry_node=entry_node).compile()
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    error: str | None = None
    final_state: dict[str, Any] = {}
    recorder = None
    html_path: Path | None = None

    try:
        if record:
            with conversation_recording() as recorder:
                final_state = await _astream_and_record(
                    compiled, initial_state, recorder, t0
                )
        else:
            final_state = await _astream_and_record(compiled, initial_state, None, t0)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("Full pipeline failed mid-run")
        raise
    finally:
        duration_ms = (time.perf_counter() - t0) * 1000
        if record and recorder is not None:
            meta = {
                "title": "Agent Conversation Report",
                "started_at": started_at,
                "duration_ms": duration_ms,
                "turn_count": len(recorder.turns),
                "entry_node": entry_node,
                "data_path": data_path,
                "error": error,
            }
            try:
                html_path = write_conversation_html(
                    turns=recorder.flush(),
                    agent_decisions=final_state.get("agent_decisions", []),
                    meta=meta,
                    path=Path(html_output) if html_output else None,
                    node_boundaries=recorder.flush_boundaries(),
                )
            except Exception:
                logger.exception("Failed to write conversation HTML report")

    return {
        "final_state": final_state,
        "html_path": str(html_path) if html_path else None,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "turn_count": len(recorder.turns) if recorder else 0,
        "error": error,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the full-pipeline entry point."""
    parser = argparse.ArgumentParser(
        description="Run the full agentic pipeline end-to-end.",
    )
    parser.add_argument("--data-path", default=None)
    parser.add_argument("--entry-node", default="eda_raw")
    parser.add_argument("--html-output", default=None)
    parser.add_argument("--no-record", dest="record", action="store_false")
    parser.set_defaults(record=True)
    return parser.parse_args(argv)


def cli_main(argv: list[str] | None = None) -> int:
    """CLI entry point for the full pipeline. Returns a process exit code."""
    args = _parse_args(argv)
    result = asyncio.run(
        run_full_pipeline(
            data_path=args.data_path,
            entry_node=args.entry_node,
            html_output=args.html_output,
            record=args.record,
        )
    )
    print(f"Wrote HTML report: {result.get('html_path') or '(not recorded)'}")
    print(
        f"Turns captured: {result['turn_count']}; "
        f"duration: {result['duration_ms']:.0f} ms"
    )
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    sys.exit(cli_main())
