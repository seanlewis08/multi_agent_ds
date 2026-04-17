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
from multi_agent_ds.tools.conversation_recorder import conversation_recording
from multi_agent_ds.tools.html_report import write_conversation_html

logger = logging.getLogger(__name__)


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
                final_state = await compiled.ainvoke(initial_state)
        else:
            final_state = await compiled.ainvoke(initial_state)
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
