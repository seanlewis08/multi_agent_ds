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

    def __init__(self, record_calls: list[dict[str, Any]]) -> None:
        self._record_calls = record_calls

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
        # Internal LangGraph wrapper events should be ignored by the boundary
        # filter — include one to make sure.
        yield {"event": "on_chain_end", "name": "LangGraph", "data": {"output": partial_state}}


class _FakeGraphBuilder:
    def __init__(self, record_calls: list[dict[str, Any]]) -> None:
        self._record_calls = record_calls

    def compile(self) -> _FakeCompiledGraph:
        return _FakeCompiledGraph(self._record_calls)


def _fake_build_graph_factory(record_calls: list[dict[str, Any]]):
    def _fake_build_graph(entry_node: str = "eda_raw") -> _FakeGraphBuilder:
        return _FakeGraphBuilder(record_calls)

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
