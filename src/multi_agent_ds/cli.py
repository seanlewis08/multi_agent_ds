"""Unified CLI dispatcher for multi-agent-ds workflows.

Exposes ``full``, ``discovery``, ``preparation``, ``modeling``, and
``evaluation`` subcommands. Each subcommand delegates to the matching
workflow function with minimal glue.

The ``full`` subcommand additionally runs a cost-safe preflight that asks
for confirmation before spending real tokens on expensive routes or large
synthetic datasets. Pass ``--yes`` to bypass the prompt in automation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from multi_agent_ds.adapters.llm.routing import resolve_model_config
from multi_agent_ds.core import load_settings

logger = logging.getLogger(__name__)

_COST_TIER_WARNING_TIERS = {"expensive"}
_SCALE_WARNING = {"medium", "large"}


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands."""
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--scale",
        default=None,
        choices=["small", "medium", "large"],
        help="Override settings.data.synthetic.scale.",
    )
    shared.add_argument(
        "--cost-override",
        default=None,
        choices=["cheap", "moderate", "expensive"],
        help="Override settings.llm.cost_override (downshifts every route's cost).",
    )
    shared.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompts.",
    )

    parser = argparse.ArgumentParser(
        prog="multi-agent-ds",
        description="Unified CLI for multi-agent-ds workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    full = subparsers.add_parser("full", parents=[shared], help="Run the full agentic pipeline.")
    full.add_argument("--data-path", default=None)
    full.add_argument("--entry-node", default="eda_raw")
    full.add_argument("--html-output", default=None)
    full.add_argument("--no-record", dest="record", action="store_false")
    full.set_defaults(record=True)

    discovery = subparsers.add_parser(
        "discovery", parents=[shared], help="Run discovery profiling only."
    )
    discovery.add_argument("--data-path", default=None)
    discovery.add_argument("--target-col", default=None)

    preparation = subparsers.add_parser(
        "preparation", parents=[shared], help="Execute an approved preparation plan."
    )
    preparation.add_argument("--data-path", required=True)
    preparation.add_argument(
        "--prep-plan",
        required=True,
        help="Path to a JSON file containing the preparation plan.",
    )
    preparation.add_argument(
        "--local-only",
        action="store_true",
        help="Write processed parquet locally and skip S3 upload.",
    )

    modeling = subparsers.add_parser(
        "modeling", parents=[shared], help="Run the baseline modeling workflow."
    )
    modeling.add_argument(
        "--data-path",
        default="data/raw/synthetic_dataset.parquet",
    )
    modeling.add_argument("--algorithms", nargs="+", default=None)
    modeling.add_argument("--run-name", default=None)

    evaluation = subparsers.add_parser(
        "evaluation",
        parents=[shared],
        help="Run post-training evaluation from a persisted state JSON file.",
    )
    evaluation.add_argument(
        "--state",
        required=True,
        help="Path to a JSON file containing 'results' and 'data' keys.",
    )

    return parser


def _apply_shared_overrides(settings: dict[str, Any], args: argparse.Namespace) -> None:
    """Write CLI overrides back into the settings dict in place."""
    scale = getattr(args, "scale", None)
    if scale:
        data_cfg = settings.setdefault("data", {})
        synthetic_cfg = data_cfg.setdefault("synthetic", {})
        synthetic_cfg["scale"] = scale

    cost_override = getattr(args, "cost_override", None)
    if cost_override:
        llm_cfg = settings.setdefault("llm", {})
        llm_cfg["cost_override"] = cost_override


def _collect_route_cost_tiers(settings: dict[str, Any]) -> set[str]:
    """Resolve every route in settings and collect the distinct cost tiers."""
    llm_cfg = settings.get("llm") or {}
    routes = llm_cfg.get("routes") or {}
    cost_tiers: set[str] = set()
    for agent, block in routes.items():
        if agent == "default":
            tasks: list[str | None] = [None]
        elif isinstance(block, dict) and "capability" in block and "cost" in block:
            tasks = [None]
        elif isinstance(block, dict):
            tasks = list(block.keys())
        else:
            tasks = [None]
        for task in tasks:
            try:
                config = resolve_model_config(settings, agent=agent, task=task)
            except ValueError:
                continue
            cost_tiers.add(config.cost_tier)
    return cost_tiers


def _resolve_active_scale_rows(settings: dict[str, Any]) -> tuple[str, int | None]:
    """Return the configured scale label and its configured n_rows (if any)."""
    synthetic_cfg = (settings.get("data") or {}).get("synthetic") or {}
    scale = str(synthetic_cfg.get("scale", "small"))
    scales = synthetic_cfg.get("scales") or {}
    scale_block = scales.get(scale) or {}
    n_rows = scale_block.get("n_rows")
    return scale, int(n_rows) if isinstance(n_rows, int) else None


def _cost_preflight(settings: dict[str, Any], assume_yes: bool) -> bool:
    """Prompt the user before a potentially expensive ``full`` run.

    Returns True to continue, False to abort.
    """
    scale, n_rows = _resolve_active_scale_rows(settings)
    cost_tiers = _collect_route_cost_tiers(settings)
    uses_expensive = bool(cost_tiers & _COST_TIER_WARNING_TIERS)
    is_large_scale = scale in _SCALE_WARNING

    if not (uses_expensive or is_large_scale):
        return True
    if assume_yes:
        return True

    sys.stderr.write("\n")
    sys.stderr.write("=" * 72 + "\n")
    sys.stderr.write("multi-agent-ds: cost preflight warning\n")
    sys.stderr.write("=" * 72 + "\n")
    sys.stderr.write(f"  scale: {scale}\n")
    if n_rows is not None:
        sys.stderr.write(f"  n_rows: {n_rows:,}\n")
    sys.stderr.write(f"  resolved cost tiers: {sorted(cost_tiers) or ['(none resolved)']}\n")
    sys.stderr.write(
        "  This run may spend a meaningful amount of real tokens on paid models.\n"
    )
    sys.stderr.write("  Re-run with --yes to skip this prompt.\n")
    sys.stderr.write("=" * 72 + "\n")
    sys.stderr.flush()

    answer = input("Continue? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _run_full(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    """Dispatch the ``full`` subcommand."""
    if not _cost_preflight(settings, assume_yes=bool(args.yes)):
        sys.stderr.write("Aborted by user.\n")
        return 2

    # Lazy-import so CLI startup stays cheap.
    from multi_agent_ds.workflows.full_pipeline import run_full_pipeline

    result = asyncio.run(
        run_full_pipeline(
            data_path=args.data_path,
            settings=settings,
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


def _run_discovery(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    """Dispatch the ``discovery`` subcommand."""
    from multi_agent_ds.workflows.discovery import run_discovery_workflow

    payload = run_discovery_workflow(
        data_path=args.data_path,
        settings=settings,
        target_col=args.target_col,
    )
    print(
        f"Profiled {payload['n_rows']} rows x {payload['n_features']} features "
        f"from {payload['data_path']} (target={payload['target_column']})."
    )
    return 0


def _run_preparation(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    """Dispatch the ``preparation`` subcommand."""
    from multi_agent_ds.workflows.preparation import run_preparation_workflow

    prep_plan_path = Path(args.prep_plan)
    prep_plan = json.loads(prep_plan_path.read_text(encoding="utf-8"))
    payload = run_preparation_workflow(
        data_path=args.data_path,
        prep_plan=prep_plan,
        settings=settings,
        local_only=bool(args.local_only),
    )
    print(f"Wrote processed parquet: {payload['processed_data_path']}")
    return 0


def _run_modeling(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    """Dispatch the ``modeling`` subcommand."""
    from multi_agent_ds.workflows.modeling import run_modeling_workflow

    results = run_modeling_workflow(
        data_path=args.data_path,
        settings=settings,
        algorithms=args.algorithms,
        run_name=args.run_name,
    )
    print(f"Trained {len(results)} algorithm(s): {', '.join(results.keys())}")
    return 0


def _run_evaluation(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    """Dispatch the ``evaluation`` subcommand."""
    from multi_agent_ds.workflows.evaluation import run_evaluation_workflow

    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    results = state.get("results") or {}
    data = state.get("data") or {}
    if not results:
        sys.stderr.write(
            "evaluation: state file is missing a non-empty 'results' key.\n"
            "See run_evaluation_workflow for the expected shape.\n"
        )
        return 2
    payload = run_evaluation_workflow(results, data, settings)
    winner = payload["evaluation_result"]["winner"]
    metric = payload["evaluation_result"]["primary_metric"]
    print(f"Winner: {winner} on {metric}.")
    return 0


_DISPATCH = {
    "full": _run_full,
    "discovery": _run_discovery,
    "preparation": _run_preparation,
    "modeling": _run_modeling,
    "evaluation": _run_evaluation,
}


def _main(argv: list[str] | None = None) -> int:
    """Parse ``argv`` and dispatch to the matching subcommand."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()
    _apply_shared_overrides(settings, args)

    handler = _DISPATCH.get(args.command)
    if handler is None:
        parser.error(f"Unknown command: {args.command}")
    return handler(args, settings)


def main() -> None:
    """Console-scripts entry point."""
    sys.exit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
