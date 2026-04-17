"""Tests for the SPA HTML conversation report emitter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from multi_agent_ds.tools.html_report import (
    _agent_color_map,
    _build_data_dict,
    render_conversation_html,
    write_conversation_html,
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
    assert {a["id"] for a in data["agents"]} == {"eda_analyst", "ml_modeler"}
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
