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
    "router": "#6B6B6B",
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
    "router": "Router",
}
_DEFAULT_AGENT_COLOR = "#64748b"

# --- Node -> agent inference ---------------------------------------------------
#
# Graph node names follow a stable prefix convention (e.g. ``data_engineer_*``)
# with a handful of special-cases (the ``eda_*`` family maps to ``eda_analyst``
# rather than an ``eda`` agent). We match the longest prefix first so
# ``business_stakeholder`` wins over a shorter prefix like ``business``, and
# ``ml_reviewer`` wins over ``ml``.

_AGENT_PREFIXES_LONGEST_FIRST: tuple[str, ...] = (
    "business_stakeholder",
    "ml_modeler",
    "ml_reviewer",
    "data_engineer",
    "report_writer",
    "eda",  # matches eda_raw, eda_prep_plan, eda_processed, eda_processed_approval
    "evaluation",
    "reviewer",
)

_NODE_TO_AGENT_OVERRIDE: dict[str, str] = {
    # Anything that doesn't follow the prefix rule gets an explicit entry here.
    "eda_raw": "eda_analyst",
    "eda_prep_plan": "eda_analyst",
    "eda_processed": "eda_analyst",
    "eda_processed_approval": "eda_analyst",
}

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

    Defensively filters out conditional-edge router callables (``route_after_*``)
    even when they appear in legacy / backfilled boundary payloads. The
    upstream recorder filter in ``workflows/full_pipeline.py`` is the primary
    guard; this is belt-and-suspenders so re-rendering an older JSON payload
    doesn't produce spurious router-named states.
    """
    states: list[dict[str, Any]] = []
    open_stack: list[tuple[int, dict[str, Any]]] = []  # (index_in_states, boundary)

    for boundary in node_boundaries:
        kind = boundary.get("kind")
        node = boundary.get("node")
        # Defensive: reject conditional-edge router callables. See docstring.
        if isinstance(node, str) and node.startswith("route_after_"):
            continue
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


def _group_states_into_rows(states: list[dict[str, Any]]) -> list[list[str]]:
    """Group states into time-row buckets for the swimlane Summary view.

    Two states share a row when they start near-simultaneously (within the
    anchor row's time window + a small tolerance). This surfaces LangGraph
    fan-outs — e.g. the three EDA reviewers that fire in parallel after
    ``eda_raw`` — as a horizontally-aligned row.

    Returns a list of rows, each row being a list of node names ordered by
    their natural start time (column reordering happens at render time).
    """
    if not states:
        return []
    sorted_states = sorted(states, key=lambda s: s.get("started_at_ms") or 0.0)
    rows: list[list[dict[str, Any]]] = [[sorted_states[0]]]
    tolerance_ms = 50.0
    for state in sorted_states[1:]:
        anchor = rows[-1][0]
        anchor_start = anchor.get("started_at_ms") or 0.0
        state_start = state.get("started_at_ms") or 0.0
        # Fan-out siblings start near-simultaneously (within tolerance) with
        # the anchor that opened the row. States that begin meaningfully later
        # — even if they overlap a long-running anchor's window — belong in a
        # later row so the grid reads top-to-bottom in execution order.
        if abs(state_start - anchor_start) <= tolerance_ms:
            rows[-1].append(state)
        else:
            rows.append([state])
    return [[s["node"] for s in row] for row in rows]


def _agent_column_order(
    states: list[dict[str, Any]],
    available_agents: list[str],
) -> list[str]:
    """Return agent IDs ordered by first appearance in execution timeline.

    Agents that exist in ``available_agents`` but did not appear in states
    are appended afterwards so the Summary grid has a column for every known
    agent.
    """
    seen: list[str] = []
    for state in sorted(states, key=lambda s: s.get("started_at_ms") or 0.0):
        agent = state.get("agent")
        if isinstance(agent, str) and agent and agent not in seen:
            seen.append(agent)
    for aid in available_agents:
        if aid not in seen:
            seen.append(aid)
    return seen


def _build_data_dict(
    turns: list[dict[str, Any]],
    node_boundaries: list[dict[str, Any]],
    agent_decisions: list[dict[str, Any]],
    meta: dict[str, Any],
    skill_calls: list[dict[str, Any]] | None = None,
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
        # Defensive: if the recorder left ``agent`` blank, try to infer it from
        # the node name before falling back to the legacy "unknown" sentinel.
        raw_agent = turn.get("agent")
        if not isinstance(raw_agent, str) or not raw_agent or raw_agent == "unknown":
            inferred = _infer_agent_from_node(turn.get("node"))
            agent_id = inferred if inferred is not None else (raw_agent or "unknown")
        else:
            agent_id = raw_agent
        annotated = {
            "turn_index": int(turn.get("turn_index", idx)),
            "node": turn.get("node"),
            "agent": agent_id,
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
            turn_node = annotated.get("node")
            # Require BOTH sides to carry a node before accepting a match. For
            # legacy / backfilled payloads where turns lack a ``node`` field,
            # ``turn_node`` is None and would otherwise spuriously match every
            # state (None == None) — causing the state's agent to latch onto
            # whichever turn happens to appear first globally. Falling through
            # to ``_agent_for_node(node)`` produces the correct inferred agent
            # for those legacy payloads.
            if turn_node is None or turn_node != node:
                continue
            matching_turn_indices.append(annotated["turn_index"])
            agents_seen.append(annotated["agent"])
            phases_seen.append(annotated["phase"])
        state["turn_indices"] = matching_turn_indices
        # Prefer the agent inferred from the node name when it appears in
        # agents_seen. Legacy fan-out payloads sometimes stamp all sibling
        # reviewers with the same node name, making agents_seen a mix of
        # (business_stakeholder, ml_modeler, ml_reviewer) for an
        # ``ml_reviewer_*`` state — in that case the inferred agent is the
        # authoritative one. Fall back to the first turn's agent otherwise.
        inferred_agent = _agent_for_node(node)
        if agents_seen:
            state["agent"] = (
                inferred_agent if inferred_agent in agents_seen else agents_seen[0]
            )
        else:
            state["agent"] = inferred_agent
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

    # Attach recorded calls (skill / tool / workflow) to their owning state by
    # node name. Calls without a node (recorded outside any boundary) are
    # dropped — they cannot be rendered against a State Detail view.
    recorded_calls_by_node: dict[str, list[dict[str, Any]]] = {}
    for call in skill_calls or []:
        node = call.get("node")
        if not node:
            continue
        # Ensure a ``layer`` field exists for legacy payloads produced before
        # tool/workflow layers were recorded.
        call_with_layer = dict(call)
        call_with_layer.setdefault("layer", "skill")
        recorded_calls_by_node.setdefault(node, []).append(call_with_layer)
    for state in states:
        calls_for_state = recorded_calls_by_node.get(state.get("node") or "", [])
        state["recorded_calls"] = calls_for_state
        # Legacy key retained so back-compat consumers (and the JS fallback)
        # continue to see the same data under the original name.
        state["skill_calls"] = calls_for_state

    # Agents list — only those that appear in turns or states. The synthetic
    # ``router`` lane is always appended at the end so the Timeline view has a
    # dedicated rightmost column for routing decisions.
    agent_ids: list[str] = []
    for annotated in annotated_turns:
        aid = annotated["agent"]
        if aid not in agent_ids:
            agent_ids.append(aid)
    for state in states:
        aid = state.get("agent")
        if isinstance(aid, str) and aid and aid not in agent_ids:
            agent_ids.append(aid)
    # Drop any prior "router" entry and re-append so it's always last.
    agent_ids = [aid for aid in agent_ids if aid != "router"]
    agent_ids.append("router")
    agents = [
        {"id": aid, "label": _agent_label(aid), "color": _agent_color(aid)}
        for aid in agent_ids
    ]

    # Router events: for each pair of consecutive states where we know the
    # router that produced the transition, emit one chip on the Router lane.
    router_events = _synthesize_router_events(states)

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

    summary_rows = _group_states_into_rows(states)
    summary_column_order = _agent_column_order(states, agent_ids)

    return {
        "meta": full_meta,
        "agents": agents,
        "states": states,
        "turns": annotated_turns,
        "router_events": router_events,
        "summary": {
            "rows": summary_rows,
            "column_order": summary_column_order,
        },
    }


def _synthesize_router_events(
    states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Emit one router chip per known state -> state transition.

    Walks ``states`` in execution order. For each state that was followed
    temporally by one or more successor states (fan-out), emit one event
    per ``(prev, curr)`` pair whose router name is registered in
    :data:`_ROUTER_BY_TRANSITION`. Fan-out siblings all anchor at the same
    ``at_ms`` (the prev state's end time).

    The ``elapsed_ms`` field is the visible chip height — at least 50ms so
    instantaneous transitions still render as a clickable target.
    """
    events: list[dict[str, Any]] = []
    if not states:
        return events

    ordered = sorted(states, key=lambda s: s.get("started_at_ms") or 0.0)

    # Bucket siblings by their (approximately equal) start time.
    siblings: dict[int, list[dict[str, Any]]] = {}
    sibling_order: list[int] = []
    tolerance_ms = 50.0
    for state in ordered:
        start = state.get("started_at_ms")
        if start is None:
            continue
        matched_key: int | None = None
        for key in sibling_order:
            if abs(key - float(start)) <= tolerance_ms:
                matched_key = key
                break
        if matched_key is None:
            matched_key = int(float(start))
            sibling_order.append(matched_key)
            siblings[matched_key] = []
        siblings[matched_key].append(state)

    # For each sibling group, the "previous" group that ended just before it
    # drives the router chips.
    for bucket_idx, key in enumerate(sibling_order):
        if bucket_idx == 0:
            continue
        prev_bucket = siblings[sibling_order[bucket_idx - 1]]
        curr_bucket = siblings[key]
        # The router always fires after the prev bucket fully finishes.
        prev_end = max(
            (s.get("ended_at_ms") or s.get("started_at_ms") or 0.0)
            for s in prev_bucket
        )
        for prev in prev_bucket:
            prev_node = prev.get("node")
            for curr in curr_bucket:
                router_name = _ROUTER_BY_TRANSITION.get(
                    (prev_node, curr.get("node"))
                )
                if not router_name:
                    continue
                at_ms = float(prev_end)
                curr_started = float(curr.get("started_at_ms") or prev_end)
                elapsed_ms = max(curr_started - at_ms, 50.0)
                events.append(
                    {
                        "type": "router",
                        "from_node": prev_node,
                        "to_node": curr.get("node"),
                        "router_name": router_name,
                        "at_ms": at_ms,
                        "elapsed_ms": elapsed_ms,
                    }
                )
    return events


def _infer_agent_from_node(node: str | None) -> str | None:
    """Infer an agent id from a graph node name by longest-prefix match.

    Returns ``None`` when no prefix or override matches — callers can then
    decide whether to substitute ``"unknown"`` or treat the node as
    uninferable. Centralising the match here (rather than splitting on ``_``
    and taking the first token) prevents ``data_engineer_feedback`` and
    similar multi-word agents from being mis-classified as their first
    token.
    """
    if not isinstance(node, str) or not node:
        return None
    if node in _NODE_TO_AGENT_OVERRIDE:
        return _NODE_TO_AGENT_OVERRIDE[node]
    for prefix in _AGENT_PREFIXES_LONGEST_FIRST:
        if node == prefix or node.startswith(prefix + "_"):
            # The ``eda`` family always maps to ``eda_analyst`` even though
            # there's no agent literally named ``eda``.
            if prefix == "eda":
                return "eda_analyst"
            return prefix
    return None


def _agent_for_node(node: str | None) -> str:
    """Best-guess agent id from a graph node name.

    Thin wrapper around :func:`_infer_agent_from_node` that returns the
    legacy ``"unknown"`` sentinel when inference fails.
    """
    inferred = _infer_agent_from_node(node)
    return inferred if inferred is not None else "unknown"


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
  --agent-router: #6B6B6B;
  --agent-unknown: #64748b;
  --bg: #FBF6EE;
  --fg: #222;
  --muted: #888;
  --border: #DDD;
  --card-bg: #FFF;
  --accent: #FF5A00;
  --layer-skill: #8854CC;
  --layer-tool: #44AA77;
  --layer-workflow: #3F7CAC;
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
  font-size: 11px;
  min-width: 120px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.flow-strip .flow-node:hover { box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
.flow-strip .flow-node .flow-node-name { font-weight: 600; }
.flow-strip .flow-node .flow-node-sub { color: var(--muted); font-size: 10px; }
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

/* ---- Summary swimlane grid ---- */
.summary-view header { margin-bottom: 12px; }
.summary-view header h2 { margin: 0 0 4px; font-size: 16px; }
.summary-view header .subtitle { margin: 0; color: var(--muted); font-size: 12px; }
.summary-grid-wrapper {
  overflow-x: auto;
  width: 100%;
  padding: 4px 0 16px;
}
.summary-grid {
  display: grid;
  gap: 8px;
  min-width: max-content;
  align-items: stretch;
}
.summary-col-header {
  position: sticky;
  top: 0;
  background: var(--bg);
  font-weight: 600;
  padding: 6px 8px;
  border-top: 4px solid var(--agent-color, var(--muted));
  text-align: center;
  font-size: 11px;
  z-index: 10;
}
.summary-col-header.router {
  border-top-color: var(--muted);
  font-style: italic;
  color: var(--muted);
}
.summary-cell {
  min-height: 100px;
  display: flex;
  flex-direction: column;
}
.summary-cell.empty {
  /* preserves grid cell; no visible content */
}
.summary-cell.filled {
  padding: 6px;
  border: 1px solid var(--border);
  border-left: 4px solid var(--agent-color, var(--muted));
  border-radius: 6px;
  background: var(--card-bg);
  cursor: pointer;
  transition: box-shadow 0.15s ease;
  gap: 4px;
  max-height: 180px;
  overflow: hidden;
  line-height: 1.3;
}
.summary-cell.filled:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
.summary-cell.filled .node-name { font-weight: 600; font-size: 12px; word-break: break-word; }
.summary-cell.filled .phase { color: var(--muted); font-size: 10px; }
.summary-cell.filled .meta { margin-top: 6px; font-size: 10px; color: var(--muted); }
.summary-cell.filled .summary-line {
  margin-top: 6px;
  font-size: 11px;
  color: #333;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.summary-cell.router {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100px;
}
.router-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  background: #EEE;
  font-size: 10px;
  color: #555;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  white-space: nowrap;
}
.summary-cell.filled.has-predecessor::before {
  content: "\2193";
  display: block;
  text-align: center;
  color: var(--muted);
  font-size: 1em;
  line-height: 1;
  margin-top: -6px;
  margin-bottom: 2px;
}

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
.turn-header .turn-title {
  font-weight: 600;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.turn-header .agent-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--agent-color, var(--agent-unknown));
}
.turn-header .turn-timing { margin-left: auto; font-size: 12px; color: var(--muted); }
.turn-metadata {
  background: rgba(0, 0, 0, 0.025);
  border: 1px solid var(--border);
  border-left: 4px solid var(--agent-color, var(--agent-unknown));
  border-radius: 6px;
  padding: 10px 12px;
  margin: 0 0 12px;
}
.turn-metadata h4 {
  margin: 0 0 6px;
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.metadata-grid {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 12px;
  margin: 0;
  font-size: 12px;
}
.metadata-grid dt {
  font-weight: 600;
  color: #555;
}
.metadata-grid dd {
  margin: 0;
  color: #222;
  word-break: break-word;
}
.skill-call-list {
  margin: 0;
  padding-left: 16px;
}
.skill-call-list li { margin: 1px 0; }
.skill-call-list code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}
.skill-call-list .skill-elapsed,
.skill-call-list .call-elapsed {
  color: var(--muted);
  font-size: 11px;
  margin-left: 4px;
}
.skill-call-list li.recorded-call { display: flex; gap: 6px; align-items: baseline; }
.call-layer {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #FFF;
  background: var(--agent-unknown);
  flex: 0 0 auto;
}
.call-layer-skill { background: var(--layer-skill); }
.call-layer-tool { background: var(--layer-tool); }
.call-layer-workflow { background: var(--layer-workflow); }
.call-trace-summary {
  font-size: 11px;
  color: var(--muted);
  margin: 2px 0 4px;
}
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
  overflow-x: auto;
}
.lane {
  flex: 1;
  min-width: 160px;
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
  /* Hidden: state names now live in the dedicated State column. The band
   * backgrounds remain as subtle horizontal guides across the other lanes. */
  display: none;
}
/* ---- State column (leftmost in Timeline) ---- */
.lane.state-lane { max-width: 200px; min-width: 180px; }
.lane.state-lane .state-header {
  font-weight: 600;
  color: var(--fg);
  border-bottom-color: var(--border);
}
.state-body { position: relative; }
.state-box {
  position: absolute;
  left: 4px; right: 4px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 4px solid var(--muted);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  overflow: hidden;
  z-index: 2;
}
.state-box:hover { box-shadow: 0 2px 6px rgba(0,0,0,0.1); background: #FFF; }
.state-box .state-box-name { font-weight: 600; font-size: 12px; }
.state-box .state-box-sub { color: var(--muted); font-size: 10px; margin-top: 2px; }
/* Router lane: visually distinct (italic, muted) per the Summary view's
 * precedent. Router chips are smaller, dashed, and muted-gray filled. */
.lane.router-lane { max-width: 180px; }
.lane.router-lane .lane-header {
  font-style: italic;
  color: var(--muted);
  border-bottom-color: var(--agent-router);
}
.item.silent-state-chip {
  background: rgba(255,255,255,0.7);
  color: var(--muted);
  border: 1px dashed var(--border);
  font-style: italic;
  opacity: 0.85;
}
.item.silent-state-chip:hover { opacity: 1; background: #FFF; }
.item.router-chip {
  background: #F1EFE8;
  color: #555;
  border: 1px dashed #B8B3A6;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 10px;
  padding: 2px 6px;
  opacity: 0.6;
}
.item.router-chip.active { opacity: 1; }
.item.router-chip .item-title { font-weight: 600; font-size: 10px; }
.item.router-chip .item-sub { font-size: 9px; opacity: 0.8; }
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

// --- view 1: summary (swimlane layout) ---
function renderSummary(app) {
  const section = el('section', { className: 'summary-view' });
  const header = el('header', null, [
    el('h2', null, 'State Summary'),
  ]);
  section.appendChild(header);
  if (DATA.meta.error) {
    section.appendChild(el('div', { className: 'error-banner' }, 'Run error: ' + DATA.meta.error));
  }
  if (!DATA.states.length) {
    header.appendChild(el('p', { className: 'subtitle' }, 'No states recorded for this run.'));
    app.appendChild(section);
    return;
  }

  const summary = DATA.summary || { rows: [], column_order: [] };
  const rows = summary.rows || [];
  const colOrder = summary.column_order || [];
  const stateByNode = {};
  DATA.states.forEach(s => { stateByNode[s.node] = s; });

  // Defensive fallback: if we have states but no column order (all unknowns),
  // fall back to the flat card grid so nothing is lost.
  if (!colOrder.length || !rows.length) {
    header.appendChild(el('p', { className: 'subtitle' },
      DATA.states.length + ' states executed.'));
    const grid = el('div', { className: 'card-grid' });
    DATA.states.forEach(state => {
      const agentId = state.agent || 'unknown';
      const agent = findAgent(agentId);
      const agentColor = agentVar(agentId);
      grid.appendChild(el('article', {
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
      ]));
    });
    section.appendChild(grid);
    app.appendChild(section);
    return;
  }

  header.appendChild(el('p', { className: 'subtitle' },
    DATA.states.length + ' states executed across ' + colOrder.length + ' agent' +
    (colOrder.length === 1 ? '' : 's') +
    '. Click any box to open that state\u2019s conversation.'));

  // Flow strip: horizontal scrolling view of the entire execution route.
  const strip = el('div', { className: 'flow-strip' });
  const orderedStates = DATA.states.slice().sort((a, b) => a.started_at_ms - b.started_at_ms);
  orderedStates.forEach((state, idx) => {
    const color = agentVar(state.agent);
    const flowNode = el('div', {
      className: 'flow-node',
      style: { borderLeftColor: color },
      onclick: () => navigate('#state/' + encodeURIComponent(state.node)),
    }, [
      el('div', { className: 'flow-node-name' }, state.node),
      el('div', { className: 'flow-node-sub' }, (state.agent || '') + ' \u00b7 ' + fmtMs(state.elapsed_ms || 0)),
    ]);
    strip.appendChild(flowNode);
    if (idx < orderedStates.length - 1) {
      strip.appendChild(el('div', { className: 'flow-arrow' }, '\u2192'));
    }
  });
  section.appendChild(strip);

  const N = colOrder.length;
  // Summary lane widths reduced to ~2/3 of original per user feedback:
  // agent columns 180px -> 120px min, router column 120px -> 90px.
  const gridTemplate = 'repeat(' + N + ', 140px) 90px';
  const wrapper = el('div', { className: 'summary-grid-wrapper' });
  const grid = el('div', {
    className: 'summary-grid',
    style: { gridTemplateColumns: gridTemplate },
  });

  // --- Header row: agent columns + Router column ---
  colOrder.forEach(agentId => {
    const agent = findAgent(agentId);
    const label = agent ? agent.label : agentId;
    const head = el('div', {
      className: 'summary-col-header',
      style: { '--agent-color': agentVar(agentId) },
    }, label);
    // Inline style var fallback for browsers that don't inherit custom props via setAttribute.
    head.style.setProperty('--agent-color', agentVar(agentId));
    grid.appendChild(head);
  });
  const routerHead = el('div', { className: 'summary-col-header router' }, 'Router');
  grid.appendChild(routerHead);

  // --- Time rows ---
  rows.forEach((rowNodes, rowIdx) => {
    const filledCols = new Set();
    rowNodes.forEach(node => {
      const state = stateByNode[node];
      if (!state) return;
      const agentId = state.agent || 'unknown';
      const col = colOrder.indexOf(agentId) + 1;
      if (col < 1) return;
      filledCols.add(col);
      const classes = 'summary-cell filled' + (rowIdx > 0 ? ' has-predecessor' : '');
      const cell = el('div', {
        className: classes,
        'data-node': node,
        style: { gridColumn: String(col) },
        onclick: () => navigate('#state/' + encodeURIComponent(node)),
      }, [
        el('div', { className: 'node-name' }, node),
        (state.phase ? el('div', { className: 'phase' }, state.phase) : null),
        el('div', { className: 'meta' },
          (state.status || 'running') + ' \u00b7 ' + fmtMs(state.elapsed_ms) +
          ' \u00b7 ' + (state.turn_indices ? state.turn_indices.length : 0) + ' turn' +
          ((state.turn_indices && state.turn_indices.length === 1) ? '' : 's')),
        (state.summary ? el('div', { className: 'summary-line' }, state.summary) : null),
      ]);
      cell.style.setProperty('--agent-color', agentVar(agentId));
      grid.appendChild(cell);
    });
    // Empty cells for agents that didn't fire this row
    for (let c = 1; c <= N; c++) {
      if (!filledCols.has(c)) {
        grid.appendChild(el('div', {
          className: 'summary-cell empty',
          style: { gridColumn: String(c) },
        }));
      }
    }
    // Router column: show the router name that produced THIS row's entries.
    // The predecessor sits in the previous row; use its routed_via if available,
    // otherwise fall back to the routed_via recorded on any state in this row.
    let routerLabel = '';
    if (rowIdx > 0) {
      const prevRow = rows[rowIdx - 1] || [];
      for (const prevNode of prevRow) {
        const prevState = stateByNode[prevNode];
        if (prevState && prevState.routed_via) { routerLabel = prevState.routed_via; break; }
      }
    }
    if (rowIdx > 0) {
      grid.appendChild(el('div', {
        className: 'summary-cell router',
        style: { gridColumn: String(N + 1) },
      }, [
        el('div', { className: 'router-chip' }, '\u2193 ' + (routerLabel || '(unknown)')),
      ]));
    } else {
      grid.appendChild(el('div', {
        className: 'summary-cell empty',
        style: { gridColumn: String(N + 1) },
      }));
    }
  });

  wrapper.appendChild(grid);
  section.appendChild(wrapper);
  app.appendChild(section);
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
  turns.forEach(turn => app.appendChild(renderTurnCard(turn, state)));
}

function renderTurnCard(turn, state) {
  const agentId = turn.agent || 'unknown';
  const agent = findAgent(agentId);
  const agentColor = agentVar(agentId);
  const usage = turn.usage || {};
  const tokensIn = usage.input_tokens != null ? usage.input_tokens : 0;
  const tokensOut = usage.output_tokens != null ? usage.output_tokens : 0;
  const tokensTotal = usage.total_tokens != null
    ? usage.total_tokens
    : (tokensIn + tokensOut);
  const tokenStr = usage.input_tokens != null
    ? ('in ' + tokensIn + ' / out ' + tokensOut + ' / total ' + tokensTotal)
    : '(none reported)';
  const card = el('article', {
    className: 'turn-card',
    style: { borderLeftColor: agentColor, '--agent-color': agentColor },
  }, [
    el('div', { className: 'turn-header' }, [
      el('span', { className: 'turn-index' }, '#' + turn.turn_index),
      el('span', { className: 'turn-title' }, [
        el('span', { className: 'agent-dot', style: { background: agentColor } }),
        (agent ? agent.label : agentId),
      ]),
      el('span', { className: 'turn-timing' }, fmtMs(turn.elapsed_ms)),
    ]),
    renderTurnMetadataBox(turn, state, {
      agentLabel: agent ? agent.label : agentId,
      agentColor: agentColor,
      tokenStr: tokenStr,
    }),
    renderMessagesBlock(turn.messages_sent || []),
    renderResponseBlock(turn),
  ]);
  card.style.setProperty('--agent-color', agentColor);
  return card;
}

function renderTurnMetadataBox(turn, state, ctx) {
  const dl = el('dl', { className: 'metadata-grid' });
  function row(label, value) {
    dl.appendChild(el('dt', null, label));
    dl.appendChild(el('dd', null, value));
  }
  row('Agent', ctx.agentLabel);
  row('Task', turn.task || '(none)');
  row('Model', turn.model || 'unknown');
  row('Capability', turn.capability || 'unknown');
  row('Cost tier', turn.cost_tier || 'unknown');
  row('Duration', fmtMs(turn.elapsed_ms));
  row('Tokens', ctx.tokenStr);

  // Recorded calls live on the state, not the turn — show every call recorded
  // for the owning state on each turn card. This keeps the metadata
  // self-contained and matches the State Detail mental model.
  // Falls back to the legacy ``skill_calls`` key so older DATA blobs still render.
  const recordedCalls = (state && (state.recorded_calls || state.skill_calls)) || [];
  dl.appendChild(el('dt', null, 'Function calls'));
  if (!recordedCalls.length) {
    dl.appendChild(el('dd', { className: 'muted' }, '(none recorded)'));
  } else {
    const counts = { skill: 0, tool: 0, workflow: 0 };
    recordedCalls.forEach(call => {
      const layer = call.layer || 'skill';
      if (counts.hasOwnProperty(layer)) counts[layer] += 1;
    });
    const summaryParts = [];
    if (counts.skill) summaryParts.push(counts.skill + ' skill call' + (counts.skill === 1 ? '' : 's'));
    if (counts.tool) summaryParts.push(counts.tool + ' tool call' + (counts.tool === 1 ? '' : 's'));
    if (counts.workflow) summaryParts.push(counts.workflow + ' workflow call' + (counts.workflow === 1 ? '' : 's'));

    const dd = el('dd');
    if (summaryParts.length) {
      dd.appendChild(el('div', { className: 'call-trace-summary' }, summaryParts.join(' · ')));
    }
    const ul = el('ul', { className: 'skill-call-list' });
    recordedCalls.forEach(call => {
      const layer = call.layer || 'skill';
      const li = el('li', { className: 'recorded-call' }, [
        el('span', { className: 'call-layer call-layer-' + layer }, layer),
        el('code', null, call.skill || '(unknown)'),
        el('span', { className: 'call-elapsed' },
          '(' + fmtMs(call.elapsed_ms) + ')'),
      ]);
      ul.appendChild(li);
    });
    dd.appendChild(ul);
    dl.appendChild(dd);
  }

  const box = el('div', {
    className: 'turn-metadata',
    style: { borderLeftColor: ctx.agentColor, '--agent-color': ctx.agentColor },
  }, [
    el('h4', null, 'Metadata'),
    dl,
  ]);
  box.style.setProperty('--agent-color', ctx.agentColor);
  return box;
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
function layoutLaneChips(laneItems) {
  // laneItems is an array of {started_at_ms, elapsed_ms, ...} sorted by
  // started_at_ms. For each item, cap its rendered height so it never
  // extends past the next item's start time in the same lane. Pure
  // layout pass — writes a ``_render_height_ms`` field.
  laneItems.sort((a, b) => a.started_at_ms - b.started_at_ms);
  for (let i = 0; i < laneItems.length - 1; i++) {
    const gap = laneItems[i + 1].started_at_ms - laneItems[i].started_at_ms;
    if (gap < laneItems[i].elapsed_ms) {
      // Minimum truncated-chip height bumped 16 -> 24 to match the
      // rendered minimum and keep overlapping chips readable.
      laneItems[i]._render_height_ms = Math.max(gap - 4, 24);
    } else {
      laneItems[i]._render_height_ms = laneItems[i].elapsed_ms;
    }
  }
  if (laneItems.length > 0) {
    const last = laneItems[laneItems.length - 1];
    last._render_height_ms = last.elapsed_ms;
  }
}

function renderTimeline(app) {
  app.appendChild(el('h2', { className: 'view-title' }, 'Timeline'));
  if (!DATA.turns.length) {
    app.appendChild(el('div', { className: 'muted' }, 'No turns recorded.'));
    return;
  }
  const routerEvents = DATA.router_events || [];
  const totalMs = Math.max(
    DATA.meta.duration_ms || 0,
    ...DATA.turns.map(t => t.started_at_ms + t.elapsed_ms),
    ...DATA.states.map(s => s.ended_at_ms || 0),
    ...routerEvents.map(r => (r.at_ms || 0) + (r.elapsed_ms || 0)),
  );
  const state = { cursor: 0, playing: false, speed: 1 };
  // Timeline vertical density: 0.15 px/ms = 150 px/s. Previous value scaled to
  // ~0.05 px/ms for typical runs, which cramped same-lane chips. Per user
  // feedback: more vertical room so overlapping chips are less cramped (the
  // overlap-truncation logic in layoutLaneChips is preserved intentionally).
  const pxPerMs = 0.025;
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
  // Column order: every agent appearing in DATA.agents, then Router as the
  // rightmost column. Defensive: move any stray "router" entry to the tail.
  const lanes = el('div', { className: 'timeline-lanes', style: { height: (laneHeight + 40) + 'px' } });
  let agents = DATA.agents.length ? DATA.agents.slice() : [{ id: 'unknown', label: 'unknown', color: '#64748b' }];
  const routerIdx = agents.findIndex(a => a.id === 'router');
  let routerAgent;
  if (routerIdx >= 0) {
    routerAgent = agents.splice(routerIdx, 1)[0];
  } else {
    routerAgent = { id: 'router', label: 'Router', color: 'var(--agent-router)' };
  }
  agents.push(routerAgent);
  const laneRefs = {};
  // State column (leftmost): lists each state's node name vertically positioned
  // to its time window, so you can read the execution order top-to-bottom
  // without scanning individual chips.
  const stateLane = el('div', { className: 'lane state-lane' }, [
    el('div', { className: 'lane-header state-header' }, 'State'),
  ]);
  const stateBody = el('div', { className: 'lane-body state-body', style: { height: laneHeight + 'px' } });
  stateLane.appendChild(stateBody);
  lanes.appendChild(stateLane);
  DATA.states.forEach(s => {
    if (s.ended_at_ms == null) return;
    const top = s.started_at_ms * pxPerMs;
    const height = Math.max(24, (s.ended_at_ms - s.started_at_ms) * pxPerMs);
    const agentColor = agentVar(s.agent);
    const box = el('div', {
      className: 'state-box',
      style: { top: top + 'px', height: height + 'px', borderLeftColor: agentColor },
      onclick: () => navigate('#state/' + encodeURIComponent(s.node)),
    }, [
      el('div', { className: 'state-box-name' }, s.node),
      (s.phase ? el('div', { className: 'state-box-sub' }, s.phase) : null),
    ]);
    stateBody.appendChild(box);
  });
  agents.forEach(a => {
    const isRouter = a.id === 'router';
    const lane = el('div', { className: 'lane' + (isRouter ? ' router-lane' : '') }, [
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
  // Partition turn chips by lane so we can run per-lane overlap truncation.
  const laneItemsByAgent = {};
  DATA.turns.forEach(turn => {
    const laneId = laneRefs[turn.agent] ? turn.agent : Object.keys(laneRefs)[0];
    if (!laneItemsByAgent[laneId]) laneItemsByAgent[laneId] = [];
    laneItemsByAgent[laneId].push({
      kind: 'turn',
      turn: turn,
      started_at_ms: turn.started_at_ms,
      elapsed_ms: turn.elapsed_ms,
    });
  });
  routerEvents.forEach(evt => {
    if (!laneItemsByAgent.router) laneItemsByAgent.router = [];
    laneItemsByAgent.router.push({
      kind: 'router',
      event: evt,
      started_at_ms: evt.at_ms,
      elapsed_ms: evt.elapsed_ms,
    });
  });
  // States without an LLM turn (e.g. data_engineer_execute, ml_modeler_handoff,
  // evaluation) still need a visual marker in their agent's lane so every run
  // piece is traceable, not just the LLM-calling ones.
  DATA.states.forEach(state => {
    if (state.turn_indices && state.turn_indices.length > 0) return;
    if (state.ended_at_ms == null) return;
    const laneId = laneRefs[state.agent] ? state.agent : null;
    if (!laneId) return;
    if (!laneItemsByAgent[laneId]) laneItemsByAgent[laneId] = [];
    laneItemsByAgent[laneId].push({
      kind: 'silent_state',
      state: state,
      started_at_ms: state.started_at_ms,
      elapsed_ms: Math.max(state.ended_at_ms - state.started_at_ms, 100),
    });
  });
  // Layout pass per lane: cap chip heights so they don't overlap the next
  // chip's start time in the same lane.
  Object.keys(laneItemsByAgent).forEach(laneId => {
    layoutLaneChips(laneItemsByAgent[laneId]);
  });
  // Render chips.
  const chips = [];
  Object.keys(laneItemsByAgent).forEach(laneId => {
    const laneBody = laneRefs[laneId];
    if (!laneBody) return;
    laneItemsByAgent[laneId].forEach(item => {
      const renderMs = item._render_height_ms != null ? item._render_height_ms : item.elapsed_ms;
      const top = item.started_at_ms * pxPerMs;
      if (item.kind === 'turn') {
        const turn = item.turn;
        const agentColor = agentVar(turn.agent);
        const height = Math.max(24, renderMs * pxPerMs);
        const chip = el('div', {
          className: 'item',
          style: { top: top + 'px', height: height + 'px', background: agentColor },
          onclick: () => {
            if (turn.node) navigate('#state/' + encodeURIComponent(turn.node));
          },
        }, [
          el('div', { className: 'item-title' }, '#' + turn.turn_index + ' ' + (turn.task || turn.kind)),
          el('div', { className: 'item-sub' }, fmtMs(turn.elapsed_ms)),
        ]);
        laneBody.appendChild(chip);
        chips.push({ chip: chip, start: turn.started_at_ms });
      } else if (item.kind === 'silent_state') {
        const s = item.state;
        const agentColor = agentVar(s.agent);
        const height = Math.max(24, renderMs * pxPerMs);
        const chip = el('div', {
          className: 'item silent-state-chip',
          style: { top: top + 'px', height: height + 'px', borderColor: agentColor },
          title: s.node + ' (no LLM call)',
          onclick: () => navigate('#state/' + encodeURIComponent(s.node)),
        }, [
          el('div', { className: 'item-title' }, s.node),
          el('div', { className: 'item-sub' }, '(no LLM) \u00b7 ' + fmtMs(s.elapsed_ms || 0)),
        ]);
        laneBody.appendChild(chip);
        chips.push({ chip: chip, start: s.started_at_ms });
      } else if (item.kind === 'router') {
        const evt = item.event;
        // Min chip height bumped 16 -> 24 to match turn chips and give more
        // visual room per user feedback on timeline density.
        const height = Math.max(24, renderMs * pxPerMs);
        const chip = el('div', {
          className: 'item router-chip',
          title: (evt.from_node || '') + ' \u2192 ' + (evt.to_node || ''),
          style: { top: top + 'px', height: height + 'px' },
        }, [
          el('div', { className: 'item-title' }, evt.router_name || 'router'),
          el('div', { className: 'item-sub' }, '\u2192 ' + (evt.to_node || '')),
        ]);
        laneBody.appendChild(chip);
        chips.push({ chip: chip, start: evt.at_ms });
      }
    });
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
    skill_calls: list[dict[str, Any]] | None = None,
) -> str:
    """Render a full self-contained HTML document for a recorded run.

    The ``node_boundaries`` parameter is optional for back-compat with callers
    that pre-date the boundary-capture work; when omitted, state cards are
    synthesized from the turns themselves. The ``skill_calls`` parameter is
    likewise optional — when omitted, the per-state metadata box renders
    "(none recorded)" for skill calls.
    """
    data = _build_data_dict(
        turns, node_boundaries or [], agent_decisions, meta, skill_calls=skill_calls
    )
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
    skill_calls: list[dict[str, Any]] | None = None,
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
        turns,
        agent_decisions,
        meta_with_path,
        node_boundaries=node_boundaries,
        skill_calls=skill_calls,
    )
    primary_path.write_text(document, encoding="utf-8")

    latest_path = primary_path.parent / "conversation_latest.html"
    try:
        shutil.copy2(primary_path, latest_path)
    except OSError:
        latest_path.write_text(document, encoding="utf-8")

    return primary_path
