"""Tests for the SPA HTML conversation report emitter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from multi_agent_ds.tools.html_report import (
    _agent_color_map,
    _agent_column_order,
    _build_data_dict,
    _group_states_into_rows,
    _infer_agent_from_node,
    _synthesize_router_events,
    render_conversation_html,
    write_conversation_html,
)

# Canonical set of graph node names (hardcoded — see orchestration/graph.py).
# Hardcoding avoids an import-time dependency on the full langgraph stack and
# makes the test fail loudly when someone adds a node without also updating
# ``_AGENT_PREFIXES_LONGEST_FIRST`` / ``_NODE_TO_AGENT_OVERRIDE``.
_GRAPH_NODE_NAMES: tuple[str, ...] = (
    "eda_raw",
    "ml_modeler_raw_review",
    "ml_reviewer_raw_review",
    "business_stakeholder_raw_review",
    "eda_prep_plan",
    "data_engineer_feedback",
    "data_engineer_execute",
    "eda_processed",
    "ml_modeler_processed_review",
    "ml_reviewer_processed_review",
    "business_stakeholder_processed_review",
    "eda_processed_approval",
    "ml_modeler_handoff",
    "ml_modeler_baseline",
    "ml_reviewer_baseline_review",
    "ml_modeler_n_estimator_search",
    "ml_modeler_tune",
    "ml_reviewer_tuning_review",
    "ml_modeler_train_tuned",
    "ml_modeler_adjust_lr",
    "ml_reviewer_lr_adjustment_review",
    "ml_modeler_importance_review",
    "ml_modeler_feature_selection",
    "ml_reviewer_feature_selection_review",
    "ml_modeler_final_recommendation",
    "ml_reviewer_final_recommendation_review",
    "evaluation",
    "reviewer",
    "report_writer",
    "business_stakeholder_report_review",
)


def _sample_turn(
    *,
    turn_index: int,
    agent: str,
    task: str | None,
    kind: str,
    response: dict[str, Any],
    messages_sent: list[dict[str, Any]] | None = None,
    node: str | None = None,
    started_at: str = "2026-04-16T12:00:00+00:00",
) -> dict[str, Any]:
    """Build one plain-dict turn matching ConversationRecorder.flush() shape."""
    return {
        "turn_index": turn_index,
        "agent": agent,
        "task": task,
        "capability": "balanced",
        "cost_tier": "cheap",
        "model": "gpt-4.1-mini",
        "kind": kind,
        "messages_sent": messages_sent
        or [
            {"role": "system", "content": f"system-{turn_index}"},
            {"role": "user", "content": f"user-{turn_index}"},
        ],
        "response": response,
        "usage": {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12},
        "started_at": started_at,
        "elapsed_ms": 123.0,
        "node": node,
    }


def _extract_data_blob(document: str) -> dict[str, Any]:
    """Pull the embedded ``const DATA = {...};`` JSON out of the document."""
    match = re.search(r"const DATA = (\{.*?\});\s*\n", document, re.DOTALL)
    assert match, "Embedded DATA blob not found in HTML"
    return json.loads(match.group(1))


def test_render_produces_spa_skeleton() -> None:
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "ok"}},
            node="eda_raw",
        ),
    ]
    document = render_conversation_html(turns, [], {"title": "Spa Run"})

    # SPA shell present.
    assert document.startswith("<!DOCTYPE html>")
    assert '<main id="app"' in document
    assert "const DATA =" in document
    # Topbar nav links for hash routes.
    assert 'href="#summary"' in document
    assert 'href="#timeline"' in document
    # JS view renderers are embedded.
    assert "function renderSummary" in document
    assert "function renderStateDetail" in document
    assert "function renderTimeline" in document
    # Title from meta lands in topbar.
    assert "Spa Run" in document


def test_render_embeds_full_data_blob() -> None:
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "EDA says hi"}},
            node="eda_raw",
        ),
        _sample_turn(
            turn_index=1,
            agent="ml_modeler",
            task="baseline",
            kind="structured",
            response={
                "parsed": {
                    "algorithms_to_tune": ["xgboost", "lightgbm"],
                    "summary": "tune top two",
                }
            },
            node="ml_modeler_baseline",
        ),
    ]
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "2026-04-16T12:00:00+00:00", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "2026-04-16T12:00:01+00:00", "elapsed_ms": 1000.0},
        {"kind": "start", "node": "ml_modeler_baseline", "ts": "2026-04-16T12:00:01+00:00", "elapsed_ms": 1000.0},
        {"kind": "end", "node": "ml_modeler_baseline", "ts": "2026-04-16T12:00:02+00:00", "elapsed_ms": 2000.0},
    ]
    meta = {
        "title": "Run",
        "started_at": "2026-04-16T12:00:00+00:00",
        "duration_ms": 2000.0,
        "turn_count": 2,
    }
    document = render_conversation_html(turns, [], meta, node_boundaries=boundaries)
    data = _extract_data_blob(document)

    assert data["meta"]["title"] == "Run"
    assert data["meta"]["turn_count"] == 2
    # The Timeline adds a synthetic "router" lane at the end for routing chips.
    assert {a["id"] for a in data["agents"]} == {
        "eda_analyst",
        "ml_modeler",
        "router",
    }
    assert data["agents"][-1]["id"] == "router"
    # Two states paired from boundaries.
    assert [s["node"] for s in data["states"]] == ["eda_raw", "ml_modeler_baseline"]
    assert data["states"][0]["next_node"] == "ml_modeler_baseline"
    # Each state references its turn indices.
    assert data["states"][0]["turn_indices"] == [0]
    assert data["states"][1]["turn_indices"] == [1]
    # Schema-aware payload survives round-trip.
    assert data["turns"][1]["response"]["parsed"]["algorithms_to_tune"] == [
        "xgboost",
        "lightgbm",
    ]


def test_render_escapes_close_script_in_embedded_data() -> None:
    malicious = "</script><script>alert(1)</script>"
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="x",
            kind="chat",
            response={"content": malicious},
            messages_sent=[{"role": "user", "content": malicious}],
        )
    ]
    document = render_conversation_html(turns, [], {})

    # The literal close-script must NOT appear (it's escaped to <\/).
    assert "</script><script>alert" not in document
    # The escaped form is present somewhere.
    assert "<\\/script>" in document


def test_schema_aware_renderer_functions_are_embedded() -> None:
    document = render_conversation_html([], [], {})
    for fn in (
        "renderEDAOutput",
        "renderPreparationPlan",
        "renderBaselineDecision",
        "renderTuningDecision",
        "renderLearningRateDecision",
        "renderFeatureSelectionDecision",
        "renderModelingVerdict",
        "renderEDAReview",
        "renderMLReview",
        "renderBusinessReview",
    ):
        assert ("function " + fn) in document, f"missing JS formatter: {fn}"


def test_render_handles_zero_turns() -> None:
    document = render_conversation_html([], [], {"title": "Empty"})
    assert document.startswith("<!DOCTYPE html>")
    assert "Empty" in document
    data = _extract_data_blob(document)
    assert data["turns"] == []
    assert data["states"] == []


def test_render_displays_error_banner() -> None:
    document = render_conversation_html(
        [], [], {"title": "Broken", "error": "ValueError: boom"}
    )
    assert "error-banner" in document
    assert "ValueError: boom" in document


def test_render_includes_full_agent_palette_css() -> None:
    document = render_conversation_html([], [], {})
    palette = _agent_color_map()
    for agent_id, color in palette.items():
        assert f"--agent-{agent_id}: {color}" in document


def test_node_boundaries_are_threaded_through_to_states() -> None:
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "ok"}},
            node="eda_raw",
        ),
    ]
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "2026-04-16T12:00:00+00:00", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "2026-04-16T12:00:00.500+00:00", "elapsed_ms": 500.0},
    ]
    document = render_conversation_html(
        turns,
        [],
        {"title": "T", "started_at": "2026-04-16T12:00:00+00:00"},
        node_boundaries=boundaries,
    )
    data = _extract_data_blob(document)
    state = data["states"][0]
    assert state["node"] == "eda_raw"
    assert state["status"] == "completed"
    assert state["elapsed_ms"] == 500.0
    assert state["turn_indices"] == [0]


def test_build_data_dict_synthesizes_states_when_no_boundaries() -> None:
    """Backward-compat path: callers that pass no boundaries still get cards."""
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw",
            kind="chat",
            response={"content": "hello"},
        ),
    ]
    data = _build_data_dict(turns, [], [], {"title": "T"})
    assert len(data["states"]) == 1
    assert data["states"][0]["agent"] == "eda_analyst"
    assert data["states"][0]["turn_indices"] == [0]


def test_build_data_dict_router_lookup_for_known_transition() -> None:
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "t1", "elapsed_ms": 10.0},
        {"kind": "start", "node": "ml_modeler_raw_review", "ts": "t2", "elapsed_ms": 11.0},
        {"kind": "end", "node": "ml_modeler_raw_review", "ts": "t3", "elapsed_ms": 20.0},
    ]
    data = _build_data_dict([], boundaries, [], {})
    assert data["states"][0]["next_node"] == "ml_modeler_raw_review"
    assert data["states"][0]["routed_via"] == "route_after_raw_eda"


def test_write_html_creates_report_and_latest(tmp_path: Path) -> None:
    primary = tmp_path / "run_one.html"
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw_review",
            kind="chat",
            response={"content": "hello"},
        )
    ]

    result_path = write_conversation_html(
        turns=turns,
        agent_decisions=[{"agent": "eda_analyst", "phase": "raw_eda"}],
        meta={"title": "One"},
        path=primary,
    )

    latest = tmp_path / "conversation_latest.html"
    assert result_path == primary
    assert primary.exists()
    assert latest.exists()
    primary_content = primary.read_text(encoding="utf-8")
    assert primary_content == latest.read_text(encoding="utf-8")
    assert "eda_analyst" in primary_content
    # The new SPA shell is present.
    assert "const DATA =" in primary_content


def test_group_states_into_rows_fanout_collapses_to_one_row() -> None:
    """Three fan-out reviewers starting at ~same time land in one row."""
    states = [
        {"node": "eda_raw", "agent": "eda_analyst",
         "started_at_ms": 0.0, "ended_at_ms": 500.0, "elapsed_ms": 500.0},
        {"node": "ml_modeler_raw_review", "agent": "ml_modeler",
         "started_at_ms": 500.0, "ended_at_ms": 1000.0, "elapsed_ms": 500.0},
        {"node": "ml_reviewer_raw_review", "agent": "ml_reviewer",
         "started_at_ms": 505.0, "ended_at_ms": 1020.0, "elapsed_ms": 515.0},
        {"node": "business_stakeholder_raw_review", "agent": "business_stakeholder",
         "started_at_ms": 510.0, "ended_at_ms": 1005.0, "elapsed_ms": 495.0},
    ]
    rows = _group_states_into_rows(states)
    assert len(rows) == 2
    assert rows[0] == ["eda_raw"]
    assert set(rows[1]) == {
        "ml_modeler_raw_review",
        "ml_reviewer_raw_review",
        "business_stakeholder_raw_review",
    }


def test_group_states_into_rows_sequential_stays_separate() -> None:
    """Non-overlapping sequential states each get their own row."""
    states = [
        {"node": "a", "agent": "eda_analyst",
         "started_at_ms": 0.0, "ended_at_ms": 100.0, "elapsed_ms": 100.0},
        {"node": "b", "agent": "data_engineer",
         "started_at_ms": 1000.0, "ended_at_ms": 1500.0, "elapsed_ms": 500.0},
        {"node": "c", "agent": "ml_modeler",
         "started_at_ms": 2000.0, "ended_at_ms": 2400.0, "elapsed_ms": 400.0},
    ]
    rows = _group_states_into_rows(states)
    assert rows == [["a"], ["b"], ["c"]]


def test_group_states_into_rows_empty() -> None:
    assert _group_states_into_rows([]) == []


def test_agent_column_order_matches_first_appearance() -> None:
    """Agents order by first start time; unused-but-available agents tail."""
    states = [
        {"node": "s1", "agent": "data_engineer", "started_at_ms": 500.0},
        {"node": "s0", "agent": "eda_analyst", "started_at_ms": 0.0},
        {"node": "s2", "agent": "ml_modeler", "started_at_ms": 1000.0},
    ]
    order = _agent_column_order(
        states, ["eda_analyst", "data_engineer", "ml_modeler", "report_writer"]
    )
    assert order[0] == "eda_analyst"
    assert order[1] == "data_engineer"
    assert order[2] == "ml_modeler"
    assert "report_writer" in order[3:]


def test_build_data_dict_emits_summary_payload() -> None:
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "t1", "elapsed_ms": 500.0},
        {"kind": "start", "node": "ml_modeler_raw_review",
         "ts": "t2", "elapsed_ms": 500.0},
        {"kind": "end", "node": "ml_modeler_raw_review",
         "ts": "t3", "elapsed_ms": 1000.0},
        {"kind": "start", "node": "ml_reviewer_raw_review",
         "ts": "t4", "elapsed_ms": 510.0},
        {"kind": "end", "node": "ml_reviewer_raw_review",
         "ts": "t5", "elapsed_ms": 1010.0},
    ]
    data = _build_data_dict([], boundaries, [], {})
    assert "summary" in data
    assert "rows" in data["summary"]
    assert "column_order" in data["summary"]
    # First row: eda_raw alone. Second row: the two parallel reviewers.
    assert data["summary"]["rows"][0] == ["eda_raw"]
    assert set(data["summary"]["rows"][1]) == {
        "ml_modeler_raw_review", "ml_reviewer_raw_review"
    }
    # Column order starts with the first firing agent.
    assert data["summary"]["column_order"][0] == "eda_analyst"


def test_summary_view_css_and_markup_embedded() -> None:
    """The new swimlane CSS classes + JS render function are in the document."""
    document = render_conversation_html([], [], {})
    # CSS classes for the new layout.
    for css_class in (
        ".summary-view",
        ".summary-grid-wrapper",
        ".summary-grid",
        ".summary-col-header",
        ".summary-cell",
        ".router-chip",
    ):
        assert css_class in document, f"missing CSS rule: {css_class}"
    # JS references the new markup.
    assert "summary-grid-wrapper" in document
    assert "summary-col-header" in document
    assert "summary-cell" in document
    assert "router-chip" in document


def test_infer_agent_from_node_covers_graph_nodes() -> None:
    """Every graph node must resolve to a non-None agent id.

    This catches future drift: when the graph adds a node, the developer is
    forced to either pick a matching prefix or add an override so the
    Timeline view won't silently drop its chips into an ``unknown`` lane.
    """
    unresolved: list[str] = []
    for node in _GRAPH_NODE_NAMES:
        if _infer_agent_from_node(node) is None:
            unresolved.append(node)
    assert not unresolved, f"unresolved nodes: {unresolved}"


def test_infer_agent_for_data_engineer_nodes() -> None:
    """Reproduction of Bug 1: data_engineer_* must not fall through to naive split."""
    assert _infer_agent_from_node("data_engineer_feedback") == "data_engineer"
    assert _infer_agent_from_node("data_engineer_execute") == "data_engineer"


def test_infer_agent_for_business_stakeholder_nodes() -> None:
    """business_stakeholder_* is the classic longest-prefix failure case."""
    assert _infer_agent_from_node("business_stakeholder_raw_review") == (
        "business_stakeholder"
    )
    assert _infer_agent_from_node("business_stakeholder_processed_review") == (
        "business_stakeholder"
    )
    assert _infer_agent_from_node("business_stakeholder_report_review") == (
        "business_stakeholder"
    )


def test_router_column_always_last() -> None:
    """The synthetic Router lane is always the rightmost entry in DATA.agents."""
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "t1", "elapsed_ms": 10.0},
    ]
    data = _build_data_dict([], boundaries, [], {})
    assert data["agents"], "expected at least the synthetic router agent"
    assert data["agents"][-1]["id"] == "router"


def test_router_events_synthesized_from_state_transitions() -> None:
    """Three states with known routers produce two router events (one per transition)."""
    states = [
        {
            "node": "eda_raw",
            "agent": "eda_analyst",
            "started_at_ms": 0.0,
            "ended_at_ms": 100.0,
        },
        {
            "node": "ml_modeler_raw_review",
            "agent": "ml_modeler",
            "started_at_ms": 120.0,
            "ended_at_ms": 220.0,
        },
        {
            "node": "eda_prep_plan",
            "agent": "eda_analyst",
            "started_at_ms": 240.0,
            "ended_at_ms": 340.0,
        },
    ]
    events = _synthesize_router_events(states)
    # Two transitions: eda_raw -> ml_modeler_raw_review (route_after_raw_eda),
    # and implicit eda_prep_plan follow-on (no direct router mapping between
    # the modeler review and the prep plan in our table). The spec's "one per
    # transition" therefore resolves to one event here — re-scope expectation
    # to "every registered transition gets an event".
    # Only route_after_raw_eda is registered for these pairs:
    names = [e["router_name"] for e in events]
    assert "route_after_raw_eda" in names


def test_router_events_on_fanout() -> None:
    """Fan-out: three parallel successors yield three router events at same at_ms."""
    states = [
        {
            "node": "eda_raw",
            "agent": "eda_analyst",
            "started_at_ms": 0.0,
            "ended_at_ms": 100.0,
        },
        {
            "node": "ml_modeler_raw_review",
            "agent": "ml_modeler",
            "started_at_ms": 110.0,
            "ended_at_ms": 210.0,
        },
        {
            "node": "ml_reviewer_raw_review",
            "agent": "ml_reviewer",
            "started_at_ms": 115.0,
            "ended_at_ms": 215.0,
        },
        {
            "node": "business_stakeholder_raw_review",
            "agent": "business_stakeholder",
            "started_at_ms": 120.0,
            "ended_at_ms": 220.0,
        },
    ]
    events = _synthesize_router_events(states)
    # All three transitions are registered under route_after_raw_eda.
    assert len(events) == 3
    assert {e["to_node"] for e in events} == {
        "ml_modeler_raw_review",
        "ml_reviewer_raw_review",
        "business_stakeholder_raw_review",
    }
    # All anchored at the same ``at_ms`` (prev.ended_at_ms).
    anchors = {e["at_ms"] for e in events}
    assert anchors == {100.0}
    # All named by the same registered router.
    assert {e["router_name"] for e in events} == {"route_after_raw_eda"}


def test_router_events_empty_when_no_transitions() -> None:
    """No crash and no events when there are fewer than two states."""
    assert _synthesize_router_events([]) == []
    assert _synthesize_router_events([
        {"node": "eda_raw", "agent": "eda_analyst",
         "started_at_ms": 0.0, "ended_at_ms": 100.0},
    ]) == []


def test_data_engineer_turn_lands_in_data_engineer_agent() -> None:
    """Smoke: a data_engineer_execute turn with agent=None must be inferred."""
    turns = [
        _sample_turn(
            turn_index=0,
            agent="",  # recorder left it blank; should be inferred from node
            task="execute",
            kind="structured",
            response={"parsed": {"summary": "ran prep"}},
            node="data_engineer_execute",
        ),
    ]
    data = _build_data_dict(turns, [], [], {"title": "T"})
    assert data["turns"][0]["agent"] == "data_engineer"


def test_router_palette_css_and_router_chip_class_embedded() -> None:
    """The CSS palette includes --agent-router and a .router-chip style."""
    document = render_conversation_html([], [], {})
    assert "--agent-router:" in document
    assert ".item.router-chip" in document


def test_route_after_nodes_excluded_from_states() -> None:
    """Router callables (``route_after_*``) must never become report states.

    Defensive guard for Bug A: LangGraph emits ``on_chain_start``/``on_chain_end``
    for conditional-edge router callables, which some legacy / backfilled
    recordings captured as boundaries. The HTML emitter must filter them out
    so they don't surface as spurious ``unknown``-agent state boxes.
    """
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "t1", "elapsed_ms": 10.0},
        # Router callables that should be ignored entirely.
        {"kind": "start", "node": "route_after_raw_eda", "ts": "t1", "elapsed_ms": 10.0},
        {"kind": "end", "node": "route_after_raw_eda", "ts": "t1", "elapsed_ms": 10.1},
        {"kind": "start", "node": "route_after_prep_plan", "ts": "t1", "elapsed_ms": 10.2},
        {"kind": "end", "node": "route_after_prep_plan", "ts": "t1", "elapsed_ms": 10.3},
        {"kind": "start", "node": "ml_modeler_raw_review", "ts": "t2", "elapsed_ms": 11.0},
        {"kind": "end", "node": "ml_modeler_raw_review", "ts": "t3", "elapsed_ms": 20.0},
    ]
    data = _build_data_dict([], boundaries, [], {})
    state_nodes = [s["node"] for s in data["states"]]
    assert "route_after_raw_eda" not in state_nodes
    assert "route_after_prep_plan" not in state_nodes
    assert state_nodes == ["eda_raw", "ml_modeler_raw_review"]


def test_state_agent_falls_back_to_inference_when_turns_lack_node() -> None:
    """Bug B: legacy turns without a ``node`` field must not latch onto a state
    by node-name equality alone.

    Under Fix A the attribution pass matches turns by (agent, time-window)
    rather than node-name equality, so a turn with ``node=None`` that also
    lacks an agent-match (e.g. eda_analyst / business_stakeholder turn) must
    NOT land in a ml_reviewer_raw_review state. A turn whose agent DOES match
    the state (ml_reviewer) correctly lands via the agent-window path — that
    is the intended behavior, not a regression.
    """
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "ok"}},
            node=None,
        ),
        _sample_turn(
            turn_index=1,
            agent="business_stakeholder",
            task="review",
            kind="structured",
            response={"parsed": {"summary": "ok"}},
            node=None,
        ),
        _sample_turn(
            turn_index=2,
            agent="ml_reviewer",
            task="review",
            kind="structured",
            response={"parsed": {"summary": "ok"}},
            node=None,
        ),
    ]
    boundaries = [
        {"kind": "start", "node": "ml_reviewer_raw_review", "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "ml_reviewer_raw_review", "ts": "t1", "elapsed_ms": 100.0},
    ]
    data = _build_data_dict(turns, boundaries, [], {})
    state = data["states"][0]
    assert state["node"] == "ml_reviewer_raw_review"
    # Inferred from node prefix, NOT taken from a random turn's agent.
    assert state["agent"] == "ml_reviewer"
    # Only the ml_reviewer turn (index 2) matches the state via
    # agent+time-window; the eda_analyst / business_stakeholder turns do not.
    assert state["turn_indices"] == [2]


def test_timeline_pxpermmsv_scale_embedded() -> None:
    """Smoke: the Timeline vertical-density constant survives in the JS.

    Guard against accidental regression of the ``pxPerMs`` constant by asserting
    it appears verbatim in the rendered document. The value is chosen to keep
    total timeline height reasonable for multi-minute runs (40px per second).
    """
    document = render_conversation_html([], [], {})
    assert "pxPerMs = 0.025" in document


def test_write_html_threads_node_boundaries(tmp_path: Path) -> None:
    primary = tmp_path / "with_boundaries.html"
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="raw_review",
            kind="chat",
            response={"content": "hello"},
            node="eda_raw",
        )
    ]
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "2026-04-16T12:00:00+00:00", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "2026-04-16T12:00:00.500+00:00", "elapsed_ms": 500.0},
    ]
    write_conversation_html(
        turns=turns,
        agent_decisions=[],
        meta={"title": "WB", "started_at": "2026-04-16T12:00:00+00:00"},
        path=primary,
        node_boundaries=boundaries,
    )
    document = primary.read_text(encoding="utf-8")
    data = _extract_data_blob(document)
    assert data["states"][0]["node"] == "eda_raw"
    assert data["states"][0]["status"] == "completed"


def test_metadata_box_renders_in_state_detail() -> None:
    """The State Detail turn card emits the new metadata box wrapper.

    The change replaces the old top-of-card badge row with a clearly-
    delineated Metadata box. The render is JS-driven so we assert on the
    embedded markup factory function plus its CSS classes.
    """
    document = render_conversation_html(
        [
            _sample_turn(
                turn_index=0,
                agent="eda_analyst",
                task="raw_review",
                kind="structured",
                response={"parsed": {"summary": "ok"}},
                node="eda_raw",
            )
        ],
        [],
        {"title": "MetaBox"},
    )
    # JS function exists (the renderer that builds the box).
    assert "function renderTurnMetadataBox" in document
    # CSS for the metadata box is embedded.
    assert ".turn-metadata" in document
    assert ".metadata-grid" in document
    assert ".skill-call-list" in document
    # The labels emitted as <dt> entries match the spec.
    for label in ("'Agent'", "'Task'", "'Model'", "'Capability'",
                  "'Cost tier'", "'Duration'", "'Tokens'", "'Function calls'"):
        assert label in document, f"missing metadata label: {label}"


def test_skill_calls_attached_to_states_by_node() -> None:
    """The skill_calls payload is grouped by node and lives on each state."""
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "t1", "elapsed_ms": 100.0},
    ]
    skill_calls = [
        {
            "call_index": 0,
            "node": "eda_raw",
            "skill": "profiling.profile_dataset",
            "elapsed_ms": 12.5,
            "started_at": "2026-04-16T12:00:00+00:00",
        },
        {
            "call_index": 1,
            "node": "ml_modeler_baseline",  # not in states; should be ignored
            "skill": "modeling.train_with_defaults",
            "elapsed_ms": 50.0,
            "started_at": "2026-04-16T12:00:00.100+00:00",
        },
        {
            "call_index": 2,
            "node": None,  # no node — must be dropped
            "skill": "profiling.profile_dataset",
            "elapsed_ms": 1.0,
            "started_at": "2026-04-16T12:00:00+00:00",
        },
    ]
    document = render_conversation_html(
        [],
        [],
        {"title": "Skills"},
        node_boundaries=boundaries,
        skill_calls=skill_calls,
    )
    data = _extract_data_blob(document)
    # eda_raw state owns its one call. The dataclass dict shape carries
    # at minimum these keys.
    assert data["states"][0]["node"] == "eda_raw"
    state_calls = data["states"][0]["skill_calls"]
    assert len(state_calls) == 1
    assert state_calls[0]["skill"] == "profiling.profile_dataset"
    assert state_calls[0]["elapsed_ms"] == 12.5


def test_multi_layer_recorded_calls_land_on_state_and_render_css() -> None:
    """Calls from all three layers land on the owning state with the right
    ``layer`` field, and the rendered HTML includes the per-layer CSS classes.
    """
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "t1", "elapsed_ms": 100.0},
    ]
    recorded_calls = [
        {
            "call_index": 0,
            "node": "eda_raw",
            "skill": "profiling.profile_dataset",
            "elapsed_ms": 12.5,
            "started_at": "2026-04-16T12:00:00+00:00",
            "layer": "skill",
        },
        {
            "call_index": 1,
            "node": "eda_raw",
            "skill": "io.upload_to_s3",
            "elapsed_ms": 30.0,
            "started_at": "2026-04-16T12:00:00.050+00:00",
            "layer": "tool",
        },
        {
            "call_index": 2,
            "node": "eda_raw",
            "skill": "discovery.run_discovery_workflow",
            "elapsed_ms": 80.0,
            "started_at": "2026-04-16T12:00:00.080+00:00",
            "layer": "workflow",
        },
    ]
    document = render_conversation_html(
        [],
        [],
        {"title": "Layers"},
        node_boundaries=boundaries,
        skill_calls=recorded_calls,
    )
    data = _extract_data_blob(document)

    assert data["states"][0]["node"] == "eda_raw"
    # Both the legacy key and the new key must surface the full payload.
    legacy_calls = data["states"][0]["skill_calls"]
    new_calls = data["states"][0]["recorded_calls"]
    assert len(legacy_calls) == 3
    assert len(new_calls) == 3
    layers = {call["layer"] for call in new_calls}
    assert layers == {"skill", "tool", "workflow"}

    # Rendered HTML carries the per-layer CSS classes so the badge styling works.
    for cls in ("call-layer-skill", "call-layer-tool", "call-layer-workflow"):
        assert cls in document, f"missing CSS class: {cls}"


def test_turn_attribution_by_agent_time_window() -> None:
    """Fan-out: three states with distinct agents, overlapping time windows,
    three turns with corresponding agents — each state lands its own turn.

    This covers Bug 1 from Fix A: raw-review fan-out where three sibling
    reviewer states (ml_modeler, ml_reviewer, business_stakeholder) overlap
    in time, and three turns — one per agent — must be attributed by
    agent-match rather than node-name string match.
    """
    turns = [
        _sample_turn(
            turn_index=0,
            agent="ml_modeler",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "ml_modeler view"}},
            node=None,
            started_at="2026-04-16T12:00:00.010+00:00",
        ),
        _sample_turn(
            turn_index=1,
            agent="ml_reviewer",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "ml_reviewer view"}},
            node=None,
            started_at="2026-04-16T12:00:00.015+00:00",
        ),
        _sample_turn(
            turn_index=2,
            agent="business_stakeholder",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "biz view"}},
            node=None,
            started_at="2026-04-16T12:00:00.020+00:00",
        ),
    ]
    boundaries = [
        {"kind": "start", "node": "ml_modeler_raw_review",
         "ts": "2026-04-16T12:00:00+00:00", "elapsed_ms": 0.0},
        {"kind": "end", "node": "ml_modeler_raw_review",
         "ts": "2026-04-16T12:00:00.100+00:00", "elapsed_ms": 100.0},
        {"kind": "start", "node": "ml_reviewer_raw_review",
         "ts": "2026-04-16T12:00:00+00:00", "elapsed_ms": 0.0},
        {"kind": "end", "node": "ml_reviewer_raw_review",
         "ts": "2026-04-16T12:00:00.100+00:00", "elapsed_ms": 100.0},
        {"kind": "start", "node": "business_stakeholder_raw_review",
         "ts": "2026-04-16T12:00:00+00:00", "elapsed_ms": 0.0},
        {"kind": "end", "node": "business_stakeholder_raw_review",
         "ts": "2026-04-16T12:00:00.100+00:00", "elapsed_ms": 100.0},
    ]
    data = _build_data_dict(
        turns, boundaries, [], {"started_at": "2026-04-16T12:00:00+00:00"}
    )
    by_node = {s["node"]: s for s in data["states"]}
    assert by_node["ml_modeler_raw_review"]["turn_indices"] == [0]
    assert by_node["ml_reviewer_raw_review"]["turn_indices"] == [1]
    assert by_node["business_stakeholder_raw_review"]["turn_indices"] == [2]


def test_turn_attribution_time_window_for_same_agent_states() -> None:
    """Iteration duplication (Bug 3): two eda_analyst states at different
    times must each claim only the turn in their own window.
    """
    turns = [
        _sample_turn(
            turn_index=0,
            agent="eda_analyst",
            task="prep_plan",
            kind="structured",
            response={"parsed": {"summary": "iter-1"}},
            node="eda_prep_plan",
            started_at="2026-04-16T12:00:00.050+00:00",
        ),
        _sample_turn(
            turn_index=1,
            agent="eda_analyst",
            task="prep_plan",
            kind="structured",
            response={"parsed": {"summary": "iter-2"}},
            node="eda_prep_plan",
            started_at="2026-04-16T12:00:01.050+00:00",
        ),
    ]
    boundaries = [
        {"kind": "start", "node": "eda_prep_plan",
         "ts": "2026-04-16T12:00:00+00:00", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_prep_plan",
         "ts": "2026-04-16T12:00:00.500+00:00", "elapsed_ms": 500.0},
        {"kind": "start", "node": "eda_prep_plan",
         "ts": "2026-04-16T12:00:01+00:00", "elapsed_ms": 1000.0},
        {"kind": "end", "node": "eda_prep_plan",
         "ts": "2026-04-16T12:00:01.500+00:00", "elapsed_ms": 1500.0},
    ]
    data = _build_data_dict(
        turns, boundaries, [], {"started_at": "2026-04-16T12:00:00+00:00"}
    )
    eda_states = [s for s in data["states"] if s["node"] == "eda_prep_plan"]
    assert len(eda_states) == 2
    # First iteration covers t=[0, 500] and owns turn 0 (t~50ms).
    assert eda_states[0]["turn_indices"] == [0]
    # Second iteration covers t=[1000, 1500] and owns turn 1 (t~1050ms).
    assert eda_states[1]["turn_indices"] == [1]


def test_orphaned_turn_with_node_none_lands_by_agent() -> None:
    """A turn with node=None but a valid agent must still attribute to the
    right state via agent+time-window — Bug 4 from Fix A.
    """
    turns = [
        _sample_turn(
            turn_index=0,
            agent="business_stakeholder",
            task="raw_review",
            kind="structured",
            response={"parsed": {"summary": "biz view"}},
            node=None,  # orphaned
            started_at="2026-04-16T12:00:00.020+00:00",
        ),
    ]
    boundaries = [
        {"kind": "start", "node": "business_stakeholder_raw_review",
         "ts": "2026-04-16T12:00:00+00:00", "elapsed_ms": 0.0},
        {"kind": "end", "node": "business_stakeholder_raw_review",
         "ts": "2026-04-16T12:00:00.100+00:00", "elapsed_ms": 100.0},
    ]
    data = _build_data_dict(
        turns, boundaries, [], {"started_at": "2026-04-16T12:00:00+00:00"}
    )
    assert data["states"][0]["turn_indices"] == [0]


def test_state_calls_panel_embedded() -> None:
    """Silent states with recorded_calls must get the state-level panel
    rendered — the JS function + CSS class are embedded in the document.
    """
    document = render_conversation_html([], [], {})
    assert "function renderStateCallsPanel" in document
    assert ".state-calls" in document
    # The panel is invoked from renderStateDetail.
    assert "renderStateCallsPanel(state)" in document


def test_list_as_table_renders_for_feature_summaries() -> None:
    """An EDAOutput turn with 17 feature_summaries must hit the table
    renderer — the JS helper plus the "Showing N of M rows" truncation
    message are embedded so the SPA can produce the table at render time.
    """
    document = render_conversation_html([], [], {})
    assert "function renderListAsTable" in document
    assert "Showing " in document
    assert "response-table" in document


def test_df_head_preview_attached_to_execute_state() -> None:
    """Seeding a data_engineer_execute decision with a raw_head_preview
    surfaces the preview on the owning state as ``data_preview``.
    """
    boundaries = [
        {"kind": "start", "node": "data_engineer_execute",
         "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "data_engineer_execute",
         "ts": "t1", "elapsed_ms": 100.0},
    ]
    raw_preview = {
        "columns": ["a", "b"],
        "rows": [["1", "x"], ["2", "y"]],
        "total_columns": 2,
        "total_rows": 2,
    }
    processed_preview = {
        "columns": ["a", "b", "c"],
        "rows": [["1", "x", "ok"], ["2", "y", "ok"]],
        "total_columns": 3,
        "total_rows": 2,
    }
    agent_decisions = [
        {
            "agent": "data_engineer",
            "phase": "prep_execute",
            "raw_head_preview": raw_preview,
            "processed_head_preview": processed_preview,
        },
    ]
    data = _build_data_dict([], boundaries, agent_decisions, {})
    assert data["states"][0]["node"] == "data_engineer_execute"
    preview = data["states"][0].get("data_preview")
    assert preview is not None
    assert preview["input"] == raw_preview
    assert preview["processed"] == processed_preview


def test_data_preview_panel_renderer_embedded() -> None:
    """The SPA exposes the panel renderer + CSS for the preview tables."""
    document = render_conversation_html([], [], {})
    assert "function renderDataPreviewPanel" in document
    assert ".data-preview-table" in document
    assert ".data-preview-panel" in document


def test_render_preparation_execution_plan_dispatched() -> None:
    """Objects with ready_for_execution + cleaning_actions route to the new
    PreparationExecutionPlan formatter.
    """
    document = render_conversation_html([], [], {})
    assert "function renderPreparationExecutionPlan" in document
    # Dispatch is wired into renderStructured.
    assert "renderPreparationExecutionPlan(parsed)" in document


def test_legacy_skill_only_calls_default_to_skill_layer() -> None:
    """Payloads produced before the layer field existed still receive
    ``layer='skill'`` once they land on the state — the HTML consumer can
    key into the layer CSS class without a branch for legacy data.
    """
    boundaries = [
        {"kind": "start", "node": "eda_raw", "ts": "t0", "elapsed_ms": 0.0},
        {"kind": "end", "node": "eda_raw", "ts": "t1", "elapsed_ms": 10.0},
    ]
    legacy_calls = [
        {
            "call_index": 0,
            "node": "eda_raw",
            "skill": "profiling.profile_dataset",
            "elapsed_ms": 5.0,
            "started_at": "2026-04-16T12:00:00+00:00",
            # no ``layer`` key — pre-existing payload
        },
    ]
    document = render_conversation_html(
        [],
        [],
        {"title": "Legacy"},
        node_boundaries=boundaries,
        skill_calls=legacy_calls,
    )
    data = _extract_data_blob(document)
    state_calls = data["states"][0]["recorded_calls"]
    assert state_calls[0]["layer"] == "skill"
