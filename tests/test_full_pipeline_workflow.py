"""Tests for ``run_full_pipeline`` orchestration and HTML emission."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from multi_agent_ds.tools.conversation_recorder import (
    RecordingOpenAIAdapter,
    get_active_recorder,
)
from multi_agent_ds.workflows import full_pipeline as full_pipeline_module


class _FakeConfig:
    capability = "balanced"
    cost_tier = "cheap"
    model = "gpt-4.1-mini"


class _FakeAdapter:
    """Adapter stub that plays back a structured response."""

    def __init__(self) -> None:
        self.config = _FakeConfig()

    def chat(self, messages: list[dict[str, Any]], tools: Any = None) -> dict[str, Any]:
        return {
            "content": "ok",
            "tool_calls": [],
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        }

    def structured_output(
        self, messages: list[dict[str, Any]], schema: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "parsed": {"summary": "fine"},
            "usage": {"input_tokens": 4, "output_tokens": 5, "total_tokens": 9},
        }


class _FakeCompiledGraph:
    """Minimal LangGraph-compatible object exposing ``astream_events``.

    Mimics the shape of LangGraph's ``v2`` event stream: emits an
    ``on_chain_start``/``on_chain_end`` pair around each "node", drives a real
    ``RecordingOpenAIAdapter`` so the recorder sees turns, and returns the
    final state via the last ``on_chain_end`` payload.
    """

    def __init__(
        self,
        record_calls: list[dict[str, Any]],
        *,
        emit_router_callable: bool = False,
    ) -> None:
        self._record_calls = record_calls
        self._emit_router_callable = emit_router_callable

    async def astream_events(
        self, initial_state: dict[str, Any], version: str = "v2"
    ):
        # Exercise the recorder-aware build_adapter path inside the simulated
        # node so turns are stamped with the active node name.
        adapter = RecordingOpenAIAdapter(
            _FakeAdapter(), agent="eda_analyst", task="raw_review"
        )
        self._record_calls.append(initial_state)

        # node 1
        yield {"event": "on_chain_start", "name": "eda_raw", "data": {"input": initial_state}}
        adapter.structured_output(
            [
                {"role": "system", "content": "sys-1"},
                {"role": "user", "content": "user-1"},
            ],
            {"title": "FakeSchema"},
        )
        adapter.structured_output(
            [
                {"role": "system", "content": "sys-2"},
                {"role": "user", "content": "user-2"},
            ],
            {"title": "FakeSchema"},
        )
        partial_state = {
            "data_path": initial_state.get("data_path"),
            "agent_decisions": [
                {"agent": "eda_analyst", "phase": "raw_eda"},
                {"agent": "eda_analyst", "phase": "raw_eda"},
            ],
        }
        yield {"event": "on_chain_end", "name": "eda_raw", "data": {"output": partial_state}}
        if self._emit_router_callable:
            # LangGraph emits on_chain_start/end for conditional-edge router
            # callables themselves — these are NOT real nodes and must be
            # filtered by the recorder's boundary gate.
            yield {
                "event": "on_chain_start",
                "name": "route_after_raw_eda",
                "data": {"input": partial_state},
            }
            yield {
                "event": "on_chain_end",
                "name": "route_after_raw_eda",
                "data": {"output": partial_state},
            }
        # Internal LangGraph wrapper events should be ignored by the boundary
        # filter — include one to make sure.
        yield {"event": "on_chain_end", "name": "LangGraph", "data": {"output": partial_state}}


class _FakeGraphBuilder:
    def __init__(
        self,
        record_calls: list[dict[str, Any]],
        *,
        emit_router_callable: bool = False,
    ) -> None:
        self._record_calls = record_calls
        self._emit_router_callable = emit_router_callable

    def compile(self) -> _FakeCompiledGraph:
        return _FakeCompiledGraph(
            self._record_calls, emit_router_callable=self._emit_router_callable
        )


def _fake_build_graph_factory(
    record_calls: list[dict[str, Any]], *, emit_router_callable: bool = False
):
    def _fake_build_graph(entry_node: str = "eda_raw") -> _FakeGraphBuilder:
        return _FakeGraphBuilder(
            record_calls, emit_router_callable=emit_router_callable
        )

    return _fake_build_graph


def test_run_full_pipeline_writes_html_and_records_turns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        full_pipeline_module,
        "build_graph",
        _fake_build_graph_factory(record_calls),
    )

    html_path = tmp_path / "full_run.html"

    result = asyncio.run(
        full_pipeline_module.run_full_pipeline(
            data_path="data/raw/synthetic_dataset.parquet",
            settings={"llm": {}, "data": {}},
            entry_node="eda_raw",
            html_output=html_path,
            record=True,
        )
    )

    assert result["error"] is None
    assert result["turn_count"] == 2
    assert result["html_path"] == str(html_path)
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
    # SPA shell + embedded data blob.
    assert "const DATA =" in content
    assert "eda_analyst" in content
    # Two structured turns made it into the embedded payload.
    assert content.count('"kind": "structured"') == 2
    # Boundaries captured from the simulated astream_events run.
    assert "eda_raw" in content
    # Sidebar "conversation_latest.html" copy should also exist.
    assert (tmp_path / "conversation_latest.html").exists()
    # Recorder is reset back to None after the run.
    assert get_active_recorder() is None
    # Initial state was passed through to the compiled graph.
    assert record_calls and record_calls[0]["data_path"] == "data/raw/synthetic_dataset.parquet"


def test_router_callable_events_filtered_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bug A: LangGraph emits events for ``route_after_*`` router callables.

    These are conditional-edge routing functions, not real graph nodes, and
    must be rejected by the recorder's boundary gate so they don't appear as
    spurious ``unknown``-agent states in the HTML report.
    """
    record_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        full_pipeline_module,
        "build_graph",
        _fake_build_graph_factory(record_calls, emit_router_callable=True),
    )

    html_path = tmp_path / "router_filtered.html"
    asyncio.run(
        full_pipeline_module.run_full_pipeline(
            data_path=None,
            settings={"llm": {}, "data": {}},
            entry_node="eda_raw",
            html_output=html_path,
            record=True,
        )
    )

    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")
    # The router callable name must NOT appear as a state node in the
    # embedded DATA payload (it may appear elsewhere, e.g. as a router-chip
    # label, which is fine — we only care about the states list).
    import json as _json
    import re as _re

    match = _re.search(r"const DATA = (\{.*?\});\s*\n", content, _re.DOTALL)
    assert match, "Embedded DATA blob not found"
    data = _json.loads(match.group(1))
    state_nodes = [s["node"] for s in data["states"]]
    assert "route_after_raw_eda" not in state_nodes, (
        f"router callable leaked into states: {state_nodes}"
    )


def test_run_full_pipeline_emits_metadata_box(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The end-to-end run wires the skill recorder and emits the metadata box.

    The fake graph drives a ``RecordingOpenAIAdapter`` so turns are captured;
    we don't need a real skill call to assert the metadata box wrapper is
    present in the rendered HTML — it renders for every turn unconditionally
    and shows ``(none recorded)`` when the state has no skill calls.
    """
    record_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        full_pipeline_module,
        "build_graph",
        _fake_build_graph_factory(record_calls),
    )

    html_path = tmp_path / "metadata_box.html"
    asyncio.run(
        full_pipeline_module.run_full_pipeline(
            data_path=None,
            settings={"llm": {}, "data": {}},
            entry_node="eda_raw",
            html_output=html_path,
            record=True,
        )
    )

    content = html_path.read_text(encoding="utf-8")
    # The new metadata-box CSS / JS / classes are embedded.
    assert ".turn-metadata" in content
    assert "function renderTurnMetadataBox" in content


def test_run_full_pipeline_without_recording_skips_html(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        full_pipeline_module,
        "build_graph",
        _fake_build_graph_factory(record_calls),
    )

    result = asyncio.run(
        full_pipeline_module.run_full_pipeline(
            data_path=None,
            settings={"llm": {}, "data": {}},
            entry_node="eda_raw",
            html_output=str(tmp_path / "should_not_exist.html"),
            record=False,
        )
    )

    assert result["html_path"] is None
    assert result["turn_count"] == 0
    assert not (tmp_path / "should_not_exist.html").exists()
    assert get_active_recorder() is None
