"""Self-contained SPA HTML emitter for recorded agent conversations.

Produces one HTML document that embeds the run's entire recording as a single
JSON blob and renders three hash-routed views (Summary, State Detail,
Timeline) using vanilla JS with no external dependencies.

Inputs are plain dicts (see
``multi_agent_ds.tools.conversation_recorder.ConversationRecorder.flush``) so
this module is not coupled to the recorder dataclasses.
"""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Agent palette
# ---------------------------------------------------------------------------

_AGENT_COLORS: dict[str, str] = {
    "eda_analyst": "#3F7CAC",
    "data_engineer": "#44AA77",
    "ml_modeler": "#8854CC",
    "ml_reviewer": "#D98B3F",
    "business_stakeholder": "#C13E3E",
    "report_writer": "#2FAE8E",
    "reviewer": "#6B6B6B",
    "orchestrator": "#333333",
}
_AGENT_LABELS: dict[str, str] = {
    "eda_analyst": "EDA Analyst",
    "data_engineer": "Data Engineer",
    "ml_modeler": "ML Modeler",
    "ml_reviewer": "ML Reviewer",
    "business_stakeholder": "Business Stakeholder",
    "report_writer": "Report Writer",
    "reviewer": "Reviewer",
    "orchestrator": "Orchestrator",
}
_DEFAULT_AGENT_COLOR = "#64748b"

# Known (current_node -> next_node) transitions mapped to the router function
# that decides them. Derived from orchestration/router.py + graph.py.
_ROUTER_BY_TRANSITION: dict[tuple[str, str], str] = {
    ("eda_raw", "ml_modeler_raw_review"): "route_after_raw_eda",
    ("eda_raw", "ml_reviewer_raw_review"): "route_after_raw_eda",
    ("eda_raw", "business_stakeholder_raw_review"): "route_after_raw_eda",
    ("eda_prep_plan", "data_engineer_feedback"): "route_after_prep_plan",
    ("eda_prep_plan", "data_engineer_execute"): "route_after_prep_plan",
    ("data_engineer_feedback", "eda_prep_plan"): "route_after_data_engineer_feedback",
    ("data_engineer_execute", "eda_processed"): "route_after_data_engineer_execute",
    ("eda_processed", "ml_modeler_processed_review"): "route_after_processed_eda",
    ("eda_processed", "ml_reviewer_processed_review"): "route_after_processed_eda",
    ("eda_processed", "business_stakeholder_processed_review"): "route_after_processed_eda",
    ("eda_processed_approval", "ml_modeler_handoff"): "route_after_processed_approval",
    ("eda_processed_approval", "eda_prep_plan"): "route_after_processed_approval",
    ("ml_modeler_handoff", "ml_modeler_baseline"): "route_after_modeling_handoff",
    ("ml_reviewer_baseline_review", "ml_modeler_baseline"): "route_after_modeling_review",
    ("ml_reviewer_baseline_review", "ml_modeler_n_estimator_search"): "route_after_modeling_review",
    ("ml_reviewer_tuning_review", "ml_modeler_tune"): "route_after_modeling_review",
    ("ml_reviewer_tuning_review", "ml_modeler_train_tuned"): "route_after_modeling_review",
    ("ml_reviewer_lr_adjustment_review", "ml_modeler_adjust_lr"): "route_after_modeling_review",
    ("ml_reviewer_lr_adjustment_review", "ml_modeler_importance_review"): "route_after_modeling_review",
    ("ml_reviewer_feature_selection_review", "ml_modeler_feature_selection"): "route_after_modeling_review",
    ("ml_reviewer_feature_selection_review", "ml_modeler_final_recommendation"): "route_after_modeling_review",
    ("ml_reviewer_final_recommendation_review", "ml_modeler_final_recommendation"): "route_after_modeling_review",
    ("ml_reviewer_final_recommendation_review", "evaluation"): "route_after_modeling_review",
    ("evaluation", "reviewer"): "route_after_evaluation",
    ("evaluation", "ml_modeler_baseline"): "route_after_evaluation",
    ("reviewer", "report_writer"): "route_after_reviewer",
    ("report_writer", "business_stakeholder_report_review"): "route_after_report_generation",
    ("business_stakeholder_report_review", "report_writer"): "route_after_business_review",
    ("business_stakeholder_report_review", "ml_modeler_baseline"): "route_after_business_review",
}


def _agent_color_map() -> dict[str, str]:
    """Centralised palette accessor for external callers / tests."""
    return dict(_AGENT_COLORS)


def _agent_color(agent: str) -> str:
    """Return the palette color for an agent id or the default slate."""
    return _AGENT_COLORS.get(agent, _DEFAULT_AGENT_COLOR)


def _agent_label(agent: str) -> str:
    """Return the human-readable label for an agent id."""
    return _AGENT_LABELS.get(agent, agent)


# ---------------------------------------------------------------------------
# Data-dict assembly
# ---------------------------------------------------------------------------


def _elapsed_from_started_at(started_at: str, run_started_at_iso: str) -> float:
    """Parse an ISO8601 started_at and return elapsed ms from run start."""
    try:
        run_t0 = datetime.fromisoformat(run_started_at_iso.replace("Z", "+00:00"))
        t = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        return (t - run_t0).total_seconds() * 1000
    except (ValueError, AttributeError):
        return 0.0


def _assign_phases_to_turns(
    turns: list[dict[str, Any]],
    agent_decisions: list[dict[str, Any]],
) -> list[str]:
    """Assign a phase label to each turn by matching per-agent call order."""
    per_agent_phases: dict[str, list[str]] = {}
    for decision in agent_decisions:
        agent = decision.get("agent")
        phase = decision.get("phase") or decision.get("current_phase") or "unknown"
        if not isinstance(agent, str):
            continue
        per_agent_phases.setdefault(agent, []).append(str(phase))

    per_agent_counter: dict[str, int] = {}
    assignments: list[str] = []
    for turn in turns:
        agent = turn.get("agent", "unknown")
        index = per_agent_counter.get(agent, 0)
        phases_for_agent = per_agent_phases.get(agent, [])
        if phases_for_agent:
            phase = phases_for_agent[min(index, len(phases_for_agent) - 1)]
        else:
            phase = "unknown"
        assignments.append(phase)
        per_agent_counter[agent] = index + 1
    return assignments


def _extract_summary(response: dict[str, Any]) -> str:
    """Pull a short human one-liner out of a structured or chat response."""
    if not isinstance(response, dict):
        return ""
    parsed = response.get("parsed")
    if isinstance(parsed, dict):
        for key in ("summary", "rationale", "explanation", "narrative", "verdict"):
            val = parsed.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()[:240]
        # Fallback: first string-valued field that's non-empty and short-ish.
        for val in parsed.values():
            if isinstance(val, str) and val.strip():
                return val.strip()[:240]
    content = response.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()[:240]
    return ""


def _pair_boundaries_into_states(
    node_boundaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair ``start`` and ``end`` (or ``error``) boundaries into state records.

    The boundaries list is the interleaved sequence emitted by LangGraph's
    ``astream_events`` (one pair per node visit — a node can be visited
    multiple times in loop-heavy graphs). We walk the list in order and for
    every ``start`` boundary we find the next matching ``end``/``error`` for
    the same node name.
    """
    states: list[dict[str, Any]] = []
    open_stack: list[tuple[int, dict[str, Any]]] = []  # (index_in_states, boundary)

    for boundary in node_boundaries:
        kind = boundary.get("kind")
        node = boundary.get("node")
        ts = boundary.get("ts")
        elapsed_ms = float(boundary.get("elapsed_ms") or 0.0)

        if kind == "start":
            state = {
                "node": node,
                "status": "running",
                "started_at_ms": elapsed_ms,
                "started_at": ts,
                "ended_at_ms": None,
                "ended_at": None,
                "elapsed_ms": None,
            }
            states.append(state)
            open_stack.append((len(states) - 1, boundary))
        elif kind in {"end", "error"}:
            # Match against the most-recently-opened state with the same node.
            match_idx: int | None = None
            for idx in range(len(open_stack) - 1, -1, -1):
                _state_idx, open_boundary = open_stack[idx]
                if open_boundary.get("node") == node:
                    match_idx = idx
                    break
            if match_idx is not None:
                state_idx, _ = open_stack.pop(match_idx)
                states[state_idx]["ended_at_ms"] = elapsed_ms
                states[state_idx]["ended_at"] = ts
                states[state_idx]["elapsed_ms"] = (
                    elapsed_ms - states[state_idx]["started_at_ms"]
                )
                states[state_idx]["status"] = (
                    "errored" if kind == "error" else "completed"
                )

    return states


def _build_data_dict(
    turns: list[dict[str, Any]],
    node_boundaries: list[dict[str, Any]],
    agent_decisions: list[dict[str, Any]],
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the embedded DATA blob consumed by the SPA."""
    turn_phases = _assign_phases_to_turns(turns, agent_decisions)
    run_started_at = str(meta.get("started_at", "") or "")

    # Annotate turns with derived fields.
    annotated_turns: list[dict[str, Any]] = []
    for idx, (turn, phase) in enumerate(zip(turns, turn_phases)):
        started_at_ms = _elapsed_from_started_at(
            str(turn.get("started_at", "") or ""), run_started_at
        )
        annotated = {
            "turn_index": int(turn.get("turn_index", idx)),
            "node": turn.get("node"),
            "agent": turn.get("agent", "unknown"),
            "task": turn.get("task"),
            "model": turn.get("model", "unknown"),
            "capability": turn.get("capability", "unknown"),
            "cost_tier": turn.get("cost_tier", "unknown"),
            "kind": turn.get("kind", "chat"),
            "started_at": turn.get("started_at"),
            "started_at_ms": started_at_ms,
            "elapsed_ms": float(turn.get("elapsed_ms") or 0.0),
            "messages_sent": turn.get("messages_sent") or [],
            "response": turn.get("response") or {},
            "usage": turn.get("usage"),
            "phase": phase,
        }
        annotated_turns.append(annotated)

    # Assemble states from boundaries.
    states = _pair_boundaries_into_states(node_boundaries or [])

    # For each state, compute turn_indices, agent, phase, summary.
    for state in states:
        node = state["node"]
        matching_turn_indices: list[int] = []
        agents_seen: list[str] = []
        phases_seen: list[str] = []
        for annotated in annotated_turns:
            if annotated.get("node") == node:
                matching_turn_indices.append(annotated["turn_index"])
                agents_seen.append(annotated["agent"])
                phases_seen.append(annotated["phase"])
        state["turn_indices"] = matching_turn_indices
        state["agent"] = agents_seen[0] if agents_seen else _agent_for_node(node)
        state["phase"] = phases_seen[0] if phases_seen else ""
        # Summary: pull the first useful one-liner from the first turn's response.
        summary = ""
        if matching_turn_indices:
            first_turn = annotated_turns[matching_turn_indices[0]]
            summary = _extract_summary(first_turn.get("response") or {})
        state["summary"] = summary

    # Fallback: if we have no boundaries, synthesize states from turns so the
    # Summary view is still meaningful. Group consecutive turns by (node,
    # agent, phase); if node is None use agent as the grouping key.
    if not states and annotated_turns:
        synthesized: list[dict[str, Any]] = []
        for annotated in annotated_turns:
            group_key = annotated.get("node") or annotated.get("agent")
            last = synthesized[-1] if synthesized else None
            if (
                last is not None
                and last.get("_group_key") == group_key
                and last.get("phase") == annotated.get("phase")
            ):
                last["turn_indices"].append(annotated["turn_index"])
                last["ended_at_ms"] = (
                    annotated["started_at_ms"] + annotated["elapsed_ms"]
                )
                last["elapsed_ms"] = last["ended_at_ms"] - last["started_at_ms"]
            else:
                synthesized.append(
                    {
                        "_group_key": group_key,
                        "node": annotated.get("node")
                        or f"{annotated.get('agent', 'unknown')}_turn_{annotated['turn_index']}",
                        "agent": annotated.get("agent", "unknown"),
                        "phase": annotated.get("phase", ""),
                        "status": "completed",
                        "started_at_ms": annotated["started_at_ms"],
                        "started_at": annotated.get("started_at"),
                        "ended_at_ms": annotated["started_at_ms"]
                        + annotated["elapsed_ms"],
                        "ended_at": annotated.get("started_at"),
                        "elapsed_ms": annotated["elapsed_ms"],
                        "turn_indices": [annotated["turn_index"]],
                        "summary": _extract_summary(annotated.get("response") or {}),
                    }
                )
        # Strip the internal key before emitting.
        for synth in synthesized:
            synth.pop("_group_key", None)
        states = synthesized

    # Compute next_node + routed_via for each state based on temporal order.
    for idx, state in enumerate(states):
        next_node = None
        if idx + 1 < len(states):
            next_node = states[idx + 1]["node"]
        state["next_node"] = next_node
        if next_node is not None:
            state["routed_via"] = _ROUTER_BY_TRANSITION.get(
                (state["node"], next_node)
            )
        else:
            state["routed_via"] = None

    # Agents list — only those that appear in turns or states.
    agent_ids: list[str] = []
    for annotated in annotated_turns:
        aid = annotated["agent"]
        if aid not in agent_ids:
            agent_ids.append(aid)
    for state in states:
        aid = state.get("agent")
        if isinstance(aid, str) and aid and aid not in agent_ids:
            agent_ids.append(aid)
    agents = [
        {"id": aid, "label": _agent_label(aid), "color": _agent_color(aid)}
        for aid in agent_ids
    ]

    tokens_in, tokens_out = _sum_tokens(turns)

    full_meta = {
        "title": str(meta.get("title", "Agent Conversation Report")),
        "started_at": run_started_at,
        "duration_ms": float(meta.get("duration_ms") or 0.0),
        "turn_count": int(meta.get("turn_count", len(turns))),
        "total_tokens_in": tokens_in,
        "total_tokens_out": tokens_out,
        "total_tokens": tokens_in + tokens_out,
        "error": meta.get("error"),
        "entry_node": meta.get("entry_node"),
        "data_path": meta.get("data_path"),
        "html_output_path": meta.get("html_output_path"),
    }

    return {
        "meta": full_meta,
        "agents": agents,
        "states": states,
        "turns": annotated_turns,
    }


def _agent_for_node(node: str | None) -> str:
    """Best-guess agent id from a graph node name."""
    if not isinstance(node, str):
        return "unknown"
    if node.startswith("eda_"):
        return "eda_analyst"
    if node.startswith("data_engineer"):
        return "data_engineer"
    if node.startswith("ml_modeler"):
        return "ml_modeler"
    if node.startswith("ml_reviewer"):
        return "ml_reviewer"
    if node.startswith("business_stakeholder"):
        return "business_stakeholder"
    if node == "report_writer":
        return "report_writer"
    if node == "reviewer":
        return "reviewer"
    if node == "evaluation":
        return "orchestrator"
    return "unknown"


def _sum_tokens(turns: list[dict[str, Any]]) -> tuple[int, int]:
    """Sum input and output tokens across all turns."""
    total_in = 0
    total_out = 0
    for turn in turns:
        usage = turn.get("usage") or {}
        total_in += int(usage.get("input_tokens") or 0)
        total_out += int(usage.get("output_tokens") or 0)
    return total_in, total_out


# ---------------------------------------------------------------------------
# HTML / JS / CSS
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --agent-eda_analyst: #3F7CAC;
  --agent-data_engineer: #44AA77;
  --agent-ml_modeler: #8854CC;
  --agent-ml_reviewer: #D98B3F;
  --agent-business_stakeholder: #C13E3E;
  --agent-report_writer: #2FAE8E;
  --agent-reviewer: #6B6B6B;
  --agent-orchestrator: #333333;
  --agent-unknown: #64748b;
  --bg: #FBF6EE;
  --fg: #222;
  --muted: #888;
  --border: #DDD;
  --card-bg: #FFF;
  --accent: #FF5A00;
  color-scheme: light;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.45;
}
header.topbar {
  background: #111;
  color: #FFF;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
  position: sticky;
  top: 0;
  z-index: 10;
}
header.topbar .title { font-weight: 700; font-size: 16px; }
header.topbar nav { display: flex; gap: 12px; }
header.topbar nav a {
  color: #DDD;
  text-decoration: none;
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 4px;
}
header.topbar nav a:hover { background: #222; color: #FFF; }
header.topbar nav a.active { background: var(--accent); color: #FFF; }
header.topbar .meta { margin-left: auto; font-size: 12px; color: #CCC; display: flex; gap: 14px; }
header.topbar .meta span { white-space: nowrap; }
main {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}
.error-banner {
  background: #7f1d1d;
  color: #fee2e2;
  padding: 10px 14px;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
}
h2.view-title {
  margin: 0 0 16px;
  font-size: 20px;
}
.muted { color: var(--muted); font-size: 12px; }
.badge {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  background: #EEE;
  color: #333;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.badge.agent { color: #FFF; }
.badge.status-completed { background: #DDEEDD; color: #2E7D32; }
.badge.status-running { background: #FFF4D4; color: #A06100; }
.badge.status-errored { background: #FADBD8; color: #922B21; }

/* ---- Flow strip ---- */
.flow-strip {
  display: flex;
  gap: 0;
  overflow-x: auto;
  padding: 10px 0 14px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--border);
}
.flow-strip .flow-node {
  flex: 0 0 auto;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 4px solid var(--agent-unknown);
  border-radius: 6px;
  padding: 6px 10px;
  margin-right: 8px;
  font-size: 12px;
  min-width: 150px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.flow-strip .flow-node:hover { box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
.flow-strip .flow-node .flow-node-name { font-weight: 600; }
.flow-strip .flow-node .flow-node-sub { color: var(--muted); font-size: 11px; }
.flow-strip .flow-arrow {
  align-self: center;
  color: var(--muted);
  font-size: 14px;
  margin: 0 4px;
  flex: 0 0 auto;
}

/* ---- Summary card grid ---- */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}
.state-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 5px solid var(--agent-unknown);
  border-radius: 8px;
  padding: 14px 16px;
  cursor: pointer;
  transition: box-shadow 0.1s ease;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.state-card:hover { box-shadow: 0 3px 10px rgba(0,0,0,0.08); }
.state-card .card-header {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
}
.state-card .card-node { font-weight: 700; font-size: 14px; }
.state-card .card-summary {
  font-size: 13px;
  color: #333;
  max-height: 3.6em;
  overflow: hidden;
  text-overflow: ellipsis;
}
.state-card .card-footer {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; color: var(--muted); margin-top: auto;
}
.state-card .card-footer .card-next { color: var(--accent); }

/* ---- State detail ---- */
.breadcrumb {
  margin-bottom: 14px;
  font-size: 13px;
}
.breadcrumb a {
  color: var(--accent);
  text-decoration: none;
  margin-right: 10px;
}
.breadcrumb a:hover { text-decoration: underline; }
.state-header {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 5px solid var(--agent-unknown);
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 18px;
}
.state-header h2 { margin: 0 0 6px; font-size: 20px; }
.state-header .state-meta {
  display: flex; flex-wrap: wrap; gap: 16px;
  font-size: 13px; color: #444; margin-top: 8px;
}
.state-header .state-meta .routed { color: var(--accent); }
article.turn-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 4px solid var(--agent-unknown);
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 14px;
}
.turn-header {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-bottom: 10px;
}
.turn-header .turn-index { font-size: 12px; color: var(--muted); }
.turn-header .turn-timing { margin-left: auto; font-size: 12px; color: var(--muted); }
details.message {
  background: #F6F1E7;
  border-radius: 6px;
  padding: 8px 12px;
  margin: 8px 0;
}
details.message summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.msg-user, .msg-assistant, .msg-tool {
  background: #FFF9EE;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  margin: 8px 0;
}
.msg-user h5, .msg-assistant h5, .msg-tool h5, .msg-system h5 {
  margin: 0 0 6px;
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.response-block {
  background: #F4FFF8;
  border: 1px solid #CCE5D5;
  border-radius: 6px;
  padding: 10px 14px;
  margin-top: 12px;
}
.response-block h4 {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
pre {
  background: #F8F5EE;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 8px 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 360px;
  overflow-y: auto;
  margin: 0;
}
.prose {
  white-space: pre-wrap;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  font-size: 13px;
  color: #222;
}
dl.kv-list { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; margin: 0; }
dl.kv-list dt { font-weight: 600; color: #555; font-size: 13px; }
dl.kv-list dd { margin: 0; font-size: 13px; }
dl.kv-list dd ul { margin: 4px 0; padding-left: 18px; }
table.kv-table { border-collapse: collapse; width: 100%; font-size: 12px; margin: 6px 0; }
table.kv-table th, table.kv-table td {
  border: 1px solid var(--border); padding: 4px 8px; text-align: left;
}
table.kv-table th { background: #F0EADC; }

/* ---- Timeline ---- */
.timeline-controls {
  display: flex; gap: 14px; align-items: center; margin-bottom: 14px;
  padding: 10px 14px; background: var(--card-bg);
  border: 1px solid var(--border); border-radius: 8px;
}
.timeline-controls button {
  background: var(--accent); color: #FFF; border: none;
  padding: 6px 14px; border-radius: 4px; cursor: pointer; font-weight: 600;
}
.timeline-controls button.ghost {
  background: transparent; color: #333; border: 1px solid var(--border);
}
.timeline-controls .elapsed-display {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}
.timeline-controls input[type="range"] { flex: 1; }
.timeline-lanes {
  position: relative;
  display: flex;
  gap: 8px;
  min-height: 600px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}
.lane {
  flex: 1;
  min-width: 140px;
  position: relative;
  border-right: 1px solid var(--border);
}
.lane:last-child { border-right: none; }
.lane-header {
  position: sticky; top: 0;
  background: var(--card-bg);
  padding: 6px 8px;
  font-size: 12px;
  font-weight: 600;
  border-bottom: 2px solid var(--agent-unknown);
  text-align: center;
}
.lane-body {
  position: relative;
  height: 100%;
  min-height: 600px;
}
.item {
  position: absolute;
  left: 6px;
  right: 6px;
  background: var(--agent-unknown);
  color: #FFF;
  border-radius: 4px;
  padding: 4px 6px;
  font-size: 11px;
  cursor: pointer;
  opacity: 0.15;
  transition: opacity 0.15s ease;
  overflow: hidden;
}
.item.active { opacity: 1; }
.item .item-title { font-weight: 600; font-size: 11px; }
.item .item-sub { font-size: 10px; opacity: 0.9; }
.playhead {
  position: absolute;
  left: 0; right: 0;
  height: 2px;
  background: var(--accent);
  z-index: 5;
  pointer-events: none;
}
.node-band {
  position: absolute;
  left: 0; right: 0;
  background: rgba(0,0,0,0.03);
  border-top: 1px dashed var(--border);
  border-bottom: 1px dashed var(--border);
  pointer-events: none;
  z-index: 1;
}
.node-band .node-band-label {
  position: absolute;
  left: 4px; top: 2px;
  font-size: 10px;
  color: var(--muted);
  background: rgba(255,255,255,0.7);
  padding: 0 3px;
  border-radius: 2px;
}
"""

_JS = r"""
// --- utilities ---
function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    if (k === 'style' && typeof attrs[k] === 'object') {
      Object.assign(node.style, attrs[k]);
    } else if (k === 'className') {
      node.className = attrs[k];
    } else if (k.startsWith('on') && typeof attrs[k] === 'function') {
      node.addEventListener(k.substring(2).toLowerCase(), attrs[k]);
    } else if (attrs[k] !== undefined && attrs[k] !== null) {
      node.setAttribute(k, attrs[k]);
    }
  }
  if (children !== undefined && children !== null) appendChildren(node, children);
  return node;
}
function appendChildren(parent, children) {
  if (Array.isArray(children)) {
    children.forEach(c => appendChildren(parent, c));
  } else if (children === null || children === undefined) {
    // skip
  } else if (typeof children === 'string' || typeof children === 'number') {
    parent.appendChild(document.createTextNode(String(children)));
  } else {
    parent.appendChild(children);
  }
}
function fmtMs(ms) {
  if (ms == null) return '\u2014';
  if (ms < 1000) return Math.round(ms) + ' ms';
  return (ms / 1000).toFixed(2) + ' s';
}
function agentVar(agent) { return 'var(--agent-' + (agent || 'unknown') + ')'; }
function findState(node) { return DATA.states.find(s => s.node === node); }
function findAgent(id) { return DATA.agents.find(a => a.id === id); }

// --- router ---
function currentRoute() {
  const hash = (location.hash || '').replace(/^#/, '');
  if (!hash || hash === 'summary') return { view: 'summary' };
  if (hash.startsWith('state/')) {
    return { view: 'state', node: decodeURIComponent(hash.substring('state/'.length)) };
  }
  if (hash === 'timeline') return { view: 'timeline' };
  return { view: 'summary' };
}
function navigate(hash) { location.hash = hash; }

function rerender() {
  const app = document.getElementById('app');
  app.innerHTML = '';
  // Playback driver is owned by the timeline view; cancel on route change.
  if (window.__timelineTimer) { clearInterval(window.__timelineTimer); window.__timelineTimer = null; }
  updateNavActive();
  const route = currentRoute();
  if (route.view === 'state' && route.node) {
    renderStateDetail(app, route.node);
  } else if (route.view === 'timeline') {
    renderTimeline(app);
  } else {
    renderSummary(app);
  }
}
function updateNavActive() {
  const route = currentRoute();
  document.querySelectorAll('header.topbar nav a').forEach(a => {
    const target = (a.getAttribute('href') || '').replace(/^#/, '');
    a.classList.toggle('active', target === route.view);
  });
}
window.addEventListener('hashchange', rerender);

// --- view 1: summary ---
function renderSummary(app) {
  app.appendChild(el('h2', { className: 'view-title' }, 'Summary'));
  if (DATA.meta.error) {
    app.appendChild(el('div', { className: 'error-banner' }, 'Run error: ' + DATA.meta.error));
  }
  if (!DATA.states.length) {
    app.appendChild(el('div', { className: 'muted' }, 'No states recorded for this run.'));
    return;
  }
  // Flow strip
  const strip = el('div', { className: 'flow-strip' });
  DATA.states.forEach((state, idx) => {
    const agentId = state.agent || 'unknown';
    const box = el('div', {
      className: 'flow-node',
      style: { borderLeftColor: agentVar(agentId) },
      onclick: () => navigate('#state/' + encodeURIComponent(state.node)),
    }, [
      el('div', { className: 'flow-node-name' }, state.node),
      el('div', { className: 'flow-node-sub' }, (state.agent || '') + ' \u00b7 ' + fmtMs(state.elapsed_ms)),
    ]);
    strip.appendChild(box);
    if (idx < DATA.states.length - 1) {
      strip.appendChild(el('span', { className: 'flow-arrow' }, '\u2192'));
    }
  });
  app.appendChild(strip);
  // Card grid
  const grid = el('div', { className: 'card-grid' });
  DATA.states.forEach(state => {
    const agentId = state.agent || 'unknown';
    const agent = findAgent(agentId);
    const agentColor = agentVar(agentId);
    const card = el('article', {
      className: 'state-card',
      style: { borderLeftColor: agentColor },
      onclick: () => navigate('#state/' + encodeURIComponent(state.node)),
    }, [
      el('div', { className: 'card-header' }, [
        el('span', { className: 'badge agent', style: { background: agentColor } }, agent ? agent.label : agentId),
        el('span', { className: 'badge status-' + (state.status || 'running') }, state.status || 'running'),
        (state.phase ? el('span', { className: 'badge' }, state.phase) : null),
      ]),
      el('div', { className: 'card-node' }, state.node),
      (state.summary ? el('div', { className: 'card-summary' }, state.summary) : null),
      el('div', { className: 'card-footer' }, [
        el('span', null, fmtMs(state.elapsed_ms) + ' \u00b7 ' + (state.turn_indices ? state.turn_indices.length : 0) + ' turn(s)'),
        (state.next_node
          ? el('span', { className: 'card-next' }, '\u2192 ' + state.next_node)
          : null),
      ]),
    ]);
    grid.appendChild(card);
  });
  app.appendChild(grid);
}

// --- view 2: state detail ---
function renderStateDetail(app, nodeName) {
  const state = findState(nodeName);
  app.appendChild(el('div', { className: 'breadcrumb' }, [
    el('a', { href: '#summary' }, '\u2190 Summary'),
    el('a', { href: '#timeline' }, 'Timeline'),
    el('span', null, ' / ' + nodeName),
  ]));
  if (!state) {
    app.appendChild(el('div', { className: 'muted' }, 'Unknown state: ' + nodeName));
    return;
  }
  const agentId = state.agent || 'unknown';
  const agent = findAgent(agentId);
  const agentColor = agentVar(agentId);
  // Header
  const prevState = DATA.states.find(s => s.next_node === nodeName);
  const header = el('div', {
    className: 'state-header',
    style: { borderLeftColor: agentColor },
  }, [
    el('h2', null, state.node),
    el('div', null, [
      el('span', { className: 'badge agent', style: { background: agentColor } }, agent ? agent.label : agentId),
      ' ',
      el('span', { className: 'badge status-' + (state.status || 'running') }, state.status || 'running'),
      (state.phase ? [' ', el('span', { className: 'badge' }, state.phase)] : null),
    ]),
    el('div', { className: 'state-meta' }, [
      el('span', null, 'Duration: ' + fmtMs(state.elapsed_ms)),
      el('span', null, 'Turns: ' + (state.turn_indices ? state.turn_indices.length : 0)),
      (prevState
        ? el('span', null, 'From: ' + prevState.node)
        : null),
      (state.next_node
        ? el('span', { className: 'routed' },
            'Routes to: ' + state.next_node + (state.routed_via ? ' (' + state.routed_via + ')' : ''))
        : null),
    ]),
  ]);
  app.appendChild(header);
  // Turn cards
  const turns = (state.turn_indices || []).map(i => DATA.turns[i]).filter(Boolean);
  if (!turns.length) {
    app.appendChild(el('div', { className: 'muted' }, 'No adapter turns recorded for this state.'));
    return;
  }
  turns.forEach(turn => app.appendChild(renderTurnCard(turn)));
}

function renderTurnCard(turn) {
  const agentId = turn.agent || 'unknown';
  const agent = findAgent(agentId);
  const agentColor = agentVar(agentId);
  const usage = turn.usage || {};
  const tokenStr = usage.input_tokens != null
    ? (usage.input_tokens + ' in / ' + usage.output_tokens + ' out')
    : 'no usage reported';
  const card = el('article', {
    className: 'turn-card',
    style: { borderLeftColor: agentColor },
  }, [
    el('div', { className: 'turn-header' }, [
      el('span', { className: 'turn-index' }, '#' + turn.turn_index),
      el('span', { className: 'badge agent', style: { background: agentColor } },
         agent ? agent.label : agentId),
      (turn.task ? el('span', { className: 'badge' }, turn.task) : null),
      el('span', { className: 'badge' }, turn.model),
      el('span', { className: 'badge' }, turn.capability + '/' + turn.cost_tier),
      el('span', { className: 'turn-timing' },
         fmtMs(turn.elapsed_ms) + ' \u00b7 ' + tokenStr),
    ]),
    renderMessagesBlock(turn.messages_sent || []),
    renderResponseBlock(turn),
  ]);
  return card;
}

function renderMessagesBlock(messages) {
  const frag = document.createDocumentFragment();
  messages.forEach(msg => {
    const role = msg.role || 'user';
    const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content, null, 2);
    if (role === 'system') {
      frag.appendChild(el('details', { className: 'message msg-system' }, [
        el('summary', null, 'System prompt'),
        el('pre', null, content),
      ]));
    } else if (role === 'user') {
      frag.appendChild(renderUserMessage(content));
    } else {
      frag.appendChild(el('div', { className: 'msg-' + role }, [
        el('h5', null, role),
        el('pre', null, content),
      ]));
    }
  });
  return frag;
}

function renderUserMessage(content) {
  // If content contains a big JSON blob annotated by a well-known keyword,
  // extract and pretty-print it in a collapsible details block. The surrounding
  // prose stays visible.
  const markers = ['profile_json=', 'payload_json=', 'state_json='];
  let marker = null;
  let idx = -1;
  for (const m of markers) {
    const i = content.indexOf(m);
    if (i !== -1 && (idx === -1 || i < idx)) { marker = m; idx = i; }
  }
  const wrap = el('div', { className: 'msg-user' }, [el('h5', null, 'User prompt')]);
  if (marker == null) {
    wrap.appendChild(el('pre', null, content));
    return wrap;
  }
  const jsonStart = content.indexOf('{', idx);
  if (jsonStart === -1) {
    wrap.appendChild(el('pre', null, content));
    return wrap;
  }
  // Walk braces to find the matching close.
  const end = matchBrace(content, jsonStart);
  if (end === -1) {
    wrap.appendChild(el('pre', null, content));
    return wrap;
  }
  const before = content.substring(0, jsonStart);
  const jsonText = content.substring(jsonStart, end + 1);
  const after = content.substring(end + 1);
  let pretty = jsonText;
  try { pretty = JSON.stringify(JSON.parse(jsonText), null, 2); } catch (e) {}
  wrap.appendChild(el('pre', null, before));
  wrap.appendChild(el('details', { className: 'message' }, [
    el('summary', null, marker.replace('=', '') + ' (embedded JSON)'),
    el('pre', null, pretty),
  ]));
  if (after.trim()) wrap.appendChild(el('pre', null, after));
  return wrap;
}

function matchBrace(s, start) {
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < s.length; i++) {
    const c = s[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (c === '\\') { esc = true; continue; }
      if (c === '"') { inStr = false; }
      continue;
    }
    if (c === '"') { inStr = true; continue; }
    if (c === '{') depth++;
    else if (c === '}') {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

// --- schema-aware response renderers ---
function renderResponseBlock(turn) {
  const wrap = el('div', { className: 'response-block' }, [
    el('h4', null, 'Response (' + turn.kind + ')'),
  ]);
  const resp = turn.response || {};
  if (turn.kind === 'structured') {
    const parsed = resp.parsed || resp;
    wrap.appendChild(renderStructured(parsed));
  } else {
    const content = resp.content != null ? String(resp.content) : JSON.stringify(resp, null, 2);
    wrap.appendChild(el('div', { className: 'prose' }, content));
  }
  return wrap;
}

function renderStructured(parsed) {
  if (!parsed || typeof parsed !== 'object') {
    return el('pre', null, JSON.stringify(parsed, null, 2));
  }
  const keys = Object.keys(parsed);
  const keySet = new Set(keys);
  // Schema detection by signature key set.
  if (keySet.has('algorithms_to_tune')) return renderBaselineDecision(parsed);
  if (keySet.has('tuning_plan') || keySet.has('tuning_configs')) return renderTuningDecision(parsed);
  if (keySet.has('lr_adjustment') || keySet.has('learning_rate_adjustment')) return renderLearningRateDecision(parsed);
  if (keySet.has('selected_features') || keySet.has('features_to_drop')) return renderFeatureSelectionDecision(parsed);
  if (keySet.has('approved') && keySet.has('cleaning_actions')) return renderPreparationPlan(parsed);
  if (keySet.has('next_action') && (keySet.has('verdict') || keySet.has('rationale'))) return renderBusinessReview(parsed);
  if (keySet.has('should_revise_modeling')) return renderMLReview(parsed);
  if (keySet.has('dataset_profile') || keySet.has('key_findings')) return renderEDAOutput(parsed);
  if (keySet.has('eda_approved') || keySet.has('eda_review')) return renderEDAReview(parsed);
  if (keySet.has('recommended_model') || keySet.has('final_model')) return renderModelingVerdict(parsed);
  return renderGenericKV(parsed);
}

function renderGenericKV(obj) {
  const dl = el('dl', { className: 'kv-list' });
  Object.keys(obj).forEach(key => {
    dl.appendChild(el('dt', null, key));
    dl.appendChild(renderValueDD(obj[key]));
  });
  return dl;
}
function renderValueDD(val) {
  const dd = el('dd');
  if (val === null || val === undefined) {
    dd.appendChild(el('span', { className: 'muted' }, '—'));
  } else if (typeof val === 'string') {
    dd.appendChild(document.createTextNode(val));
  } else if (typeof val === 'number' || typeof val === 'boolean') {
    dd.appendChild(document.createTextNode(String(val)));
  } else if (Array.isArray(val)) {
    if (val.length === 0) dd.appendChild(el('span', { className: 'muted' }, '(empty)'));
    else if (val.every(v => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')) {
      const ul = el('ul');
      val.forEach(v => ul.appendChild(el('li', null, String(v))));
      dd.appendChild(ul);
    } else {
      dd.appendChild(el('pre', null, JSON.stringify(val, null, 2)));
    }
  } else if (typeof val === 'object') {
    dd.appendChild(el('pre', null, JSON.stringify(val, null, 2)));
  }
  return dd;
}

// Schema-specific formatters. Each delegates to renderGenericKV for anything
// beyond the fields we know about, ensuring no field is silently dropped.
function renderEDAOutput(p) { return renderGenericKV(p); }
function renderPreparationPlan(p) { return renderGenericKV(p); }
function renderBaselineDecision(p) { return renderGenericKV(p); }
function renderTuningDecision(p) { return renderGenericKV(p); }
function renderLearningRateDecision(p) { return renderGenericKV(p); }
function renderFeatureSelectionDecision(p) { return renderGenericKV(p); }
function renderModelingVerdict(p) { return renderGenericKV(p); }
function renderEDAReview(p) { return renderGenericKV(p); }
function renderMLReview(p) { return renderGenericKV(p); }
function renderBusinessReview(p) { return renderGenericKV(p); }

// --- view 3: timeline ---
function renderTimeline(app) {
  app.appendChild(el('h2', { className: 'view-title' }, 'Timeline'));
  if (!DATA.turns.length) {
    app.appendChild(el('div', { className: 'muted' }, 'No turns recorded.'));
    return;
  }
  const totalMs = Math.max(
    DATA.meta.duration_ms || 0,
    ...DATA.turns.map(t => t.started_at_ms + t.elapsed_ms),
    ...DATA.states.map(s => s.ended_at_ms || 0),
  );
  const state = { cursor: 0, playing: false, speed: 1 };
  const pxPerMs = 400 / Math.max(totalMs, 1000); // fit at least 400px of lane height per 1s
  const laneHeight = Math.max(600, totalMs * pxPerMs + 40);
  // --- Controls ---
  const playBtn = el('button', null, 'Play');
  const speedSel = el('select', { className: 'ghost' });
  ['1', '2', '4', '8'].forEach(v => speedSel.appendChild(el('option', { value: v }, v + 'x')));
  const elapsedDisplay = el('span', { className: 'elapsed-display' }, '0 / ' + fmtMs(totalMs));
  const scrubber = el('input', { type: 'range', min: '0', max: String(totalMs), value: '0', step: '10' });
  const resetBtn = el('button', { className: 'ghost' }, 'Reset');
  const controls = el('div', { className: 'timeline-controls' }, [
    playBtn, speedSel, resetBtn, elapsedDisplay, scrubber,
  ]);
  app.appendChild(controls);
  // --- Lanes ---
  const lanes = el('div', { className: 'timeline-lanes', style: { height: (laneHeight + 40) + 'px' } });
  const agents = DATA.agents.length ? DATA.agents : [{ id: 'unknown', label: 'unknown', color: '#64748b' }];
  const laneRefs = {};
  agents.forEach(a => {
    const lane = el('div', { className: 'lane' }, [
      el('div', { className: 'lane-header', style: { borderBottomColor: a.color, color: a.color } }, a.label),
    ]);
    const body = el('div', { className: 'lane-body', style: { height: laneHeight + 'px' } });
    lane.appendChild(body);
    lanes.appendChild(lane);
    laneRefs[a.id] = body;
  });
  // Node bands span all lanes — render them in an absolutely-positioned overlay.
  const bandLayer = el('div', {
    style: {
      position: 'absolute',
      left: '0', right: '0', top: '32px', bottom: '0',
      pointerEvents: 'none',
    },
  });
  DATA.states.forEach(s => {
    if (s.ended_at_ms == null) return;
    const top = s.started_at_ms * pxPerMs;
    const height = Math.max(12, (s.ended_at_ms - s.started_at_ms) * pxPerMs);
    const band = el('div', {
      className: 'node-band',
      style: { top: top + 'px', height: height + 'px' },
    }, [el('span', { className: 'node-band-label' }, s.node)]);
    bandLayer.appendChild(band);
  });
  lanes.appendChild(bandLayer);
  // Turn chips
  const chips = [];
  DATA.turns.forEach(turn => {
    const laneBody = laneRefs[turn.agent] || laneRefs[Object.keys(laneRefs)[0]];
    if (!laneBody) return;
    const agentColor = agentVar(turn.agent);
    const top = turn.started_at_ms * pxPerMs;
    const height = Math.max(24, turn.elapsed_ms * pxPerMs);
    const chip = el('div', {
      className: 'item',
      style: { top: top + 'px', height: height + 'px', background: agentColor },
      onclick: () => {
        if (turn.node) navigate('#state/' + encodeURIComponent(turn.node));
      },
    }, [
      el('div', { className: 'item-title' }, '#' + turn.turn_index + ' ' + (turn.task || turn.kind)),
      el('div', { className: 'item-sub' }, (turn.node || '') + ' \u00b7 ' + fmtMs(turn.elapsed_ms)),
    ]);
    laneBody.appendChild(chip);
    chips.push({ chip: chip, start: turn.started_at_ms });
  });
  // Playhead line
  const playhead = el('div', { className: 'playhead', style: { top: '32px' } });
  lanes.appendChild(playhead);
  app.appendChild(lanes);

  // --- Playback driver ---
  function setCursor(ms) {
    state.cursor = Math.max(0, Math.min(totalMs, ms));
    const y = 32 + state.cursor * pxPerMs;
    playhead.style.top = y + 'px';
    elapsedDisplay.textContent = fmtMs(state.cursor) + ' / ' + fmtMs(totalMs);
    scrubber.value = String(Math.round(state.cursor));
    chips.forEach(({ chip, start }) => {
      chip.classList.toggle('active', start <= state.cursor);
    });
  }
  setCursor(0);
  playBtn.addEventListener('click', () => {
    state.playing = !state.playing;
    playBtn.textContent = state.playing ? 'Pause' : 'Play';
  });
  resetBtn.addEventListener('click', () => { setCursor(0); });
  speedSel.addEventListener('change', () => {
    state.speed = parseFloat(speedSel.value) || 1;
  });
  scrubber.addEventListener('input', () => {
    setCursor(parseFloat(scrubber.value) || 0);
  });
  window.__timelineTimer = setInterval(() => {
    if (!state.playing) return;
    const next = state.cursor + 40 * state.speed;
    if (next >= totalMs) { setCursor(totalMs); state.playing = false; playBtn.textContent = 'Play'; return; }
    setCursor(next);
  }, 40);
}

// --- boot ---
document.addEventListener('DOMContentLoaded', rerender);
"""


def _escape(value: Any) -> str:
    """HTML-escape any value after string coercion."""
    return html.escape(str(value), quote=True)


def _embed_json_safely(data: dict[str, Any]) -> str:
    """Serialize ``data`` to a string that is safe to embed in a <script> tag.

    Escapes ``</`` and the unicode line separators that would otherwise break
    JS parsers. Pattern adapted from ``demo_viewer_loader.inject_demo_log``.
    """
    raw = json.dumps(data, default=str, ensure_ascii=False)
    # Neutralize ``</script>`` and similar close-tag escapes.
    raw = raw.replace("</", "<\\/")
    # JS-hostile line separators.
    raw = raw.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return raw


def _format_duration(duration_ms: Any) -> str:
    """Human-readable duration string for the topbar."""
    try:
        ms = float(duration_ms)
    except (TypeError, ValueError):
        return "—"
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"


def render_conversation_html(
    turns: list[dict[str, Any]],
    agent_decisions: list[dict[str, Any]],
    meta: dict[str, Any],
    node_boundaries: list[dict[str, Any]] | None = None,
) -> str:
    """Render a full self-contained HTML document for a recorded run.

    The ``node_boundaries`` parameter is optional for back-compat with callers
    that pre-date the boundary-capture work; when omitted, state cards are
    synthesized from the turns themselves.
    """
    data = _build_data_dict(turns, node_boundaries or [], agent_decisions, meta)
    data_json = _embed_json_safely(data)

    title = _escape(data["meta"]["title"])
    duration_str = _format_duration(data["meta"]["duration_ms"])
    turn_count = int(data["meta"]["turn_count"])
    total_tokens = int(data["meta"]["total_tokens"])
    error = data["meta"].get("error")
    error_banner = ""
    if error:
        error_banner = f'<div class="error-banner">Run error: {_escape(error)}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>{_CSS}</style>
</head>
<body>
  <header class="topbar">
    <div class="title">{title}</div>
    <nav>
      <a href="#summary">Summary</a>
      <a href="#timeline">Timeline</a>
    </nav>
    <div class="meta">
      <span>{_escape(duration_str)}</span>
      <span>{turn_count} turns</span>
      <span>{total_tokens} tokens</span>
    </div>
  </header>
  <main id="app">{error_banner}</main>
  <script>
    const DATA = {data_json};
    {_JS}
  </script>
</body>
</html>
"""


def _default_report_path() -> Path:
    """Compute the default timestamped HTML report path under ``reports/``."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return Path("reports") / f"conversation_{stamp}.html"


def write_conversation_html(
    turns: list[dict[str, Any]],
    agent_decisions: list[dict[str, Any]],
    meta: dict[str, Any],
    path: Path | None = None,
    node_boundaries: list[dict[str, Any]] | None = None,
) -> Path:
    """Render and write the conversation HTML to disk.

    Writes the primary file at ``path`` (or ``reports/conversation_<ts>.html``)
    and a mirrored ``conversation_latest.html`` in the same directory. Returns
    the primary path.
    """
    primary_path = Path(path) if path is not None else _default_report_path()
    primary_path.parent.mkdir(parents=True, exist_ok=True)

    meta_with_path = dict(meta)
    meta_with_path.setdefault("html_output_path", str(primary_path))
    document = render_conversation_html(
        turns, agent_decisions, meta_with_path, node_boundaries=node_boundaries
    )
    primary_path.write_text(document, encoding="utf-8")

    latest_path = primary_path.parent / "conversation_latest.html"
    try:
        shutil.copy2(primary_path, latest_path)
    except OSError:
        latest_path.write_text(document, encoding="utf-8")

    return primary_path
