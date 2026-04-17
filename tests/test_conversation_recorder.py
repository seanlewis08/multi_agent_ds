"""Tests for the conversation recorder and recording adapter wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from multi_agent_ds.tools.conversation_recorder import (
    ConversationRecorder,
    NodeBoundary,
    RecordingOpenAIAdapter,
    conversation_recording,
    get_active_recorder,
)


@dataclass(frozen=True)
class _FakeConfig:
    capability: str = "balanced"
    cost_tier: str = "cheap"
    model: str = "gpt-4.1-mini"


class _FakeWrappedAdapter:
    """Minimal stand-in for OpenAIAdapter for recorder tests."""

    def __init__(self) -> None:
        self.config = _FakeConfig()
        self.chat_calls: list[tuple[list[dict[str, Any]], Any]] = []
        self.structured_calls: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.chat_calls.append((messages, tools))
        return {
            "content": "hello from chat",
            "tool_calls": [],
            "usage": {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8},
        }

    def structured_output(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.structured_calls.append((messages, schema))
        return {
            "parsed": {"ok": True, "schema_title": schema.get("title")},
            "usage": {"input_tokens": 7, "output_tokens": 11, "total_tokens": 18},
        }

    def custom_method(self) -> str:
        return "custom"


def test_recording_adapter_captures_structured_output_turn() -> None:
    wrapped = _FakeWrappedAdapter()
    adapter = RecordingOpenAIAdapter(wrapped, agent="eda_analyst", task="raw_review")
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}]
    schema = {"title": "FakeSchema", "type": "object"}

    with conversation_recording() as recorder:
        result = adapter.structured_output(messages, schema)

    assert result["parsed"] == {"ok": True, "schema_title": "FakeSchema"}
    assert len(recorder.turns) == 1
    turn = recorder.turns[0]
    assert turn.agent == "eda_analyst"
    assert turn.task == "raw_review"
    assert turn.kind == "structured"
    assert turn.messages_sent == messages
    assert turn.response["parsed"] == {"ok": True, "schema_title": "FakeSchema"}
    assert turn.capability == "balanced"
    assert turn.cost_tier == "cheap"
    assert turn.model == "gpt-4.1-mini"
    assert turn.usage == {"input_tokens": 7, "output_tokens": 11, "total_tokens": 18}
    assert turn.turn_index == 0
    assert turn.elapsed_ms >= 0.0
    assert turn.started_at  # non-empty ISO8601 string


def test_recording_adapter_captures_chat_turn() -> None:
    wrapped = _FakeWrappedAdapter()
    adapter = RecordingOpenAIAdapter(wrapped, agent="report_writer", task=None)
    messages = [{"role": "user", "content": "hi"}]

    with conversation_recording() as recorder:
        result = adapter.chat(messages)

    assert result["content"] == "hello from chat"
    assert len(recorder.turns) == 1
    turn = recorder.turns[0]
    assert turn.kind == "chat"
    assert turn.task is None
    assert turn.response["content"] == "hello from chat"


def test_no_recording_when_no_active_recorder() -> None:
    wrapped = _FakeWrappedAdapter()
    adapter = RecordingOpenAIAdapter(wrapped, agent="a", task=None)

    # No contextmanager active — call still works but nothing is recorded.
    assert get_active_recorder() is None
    result = adapter.chat([{"role": "user", "content": "x"}])
    assert result["content"] == "hello from chat"
    # Recorder is still None after the call.
    assert get_active_recorder() is None


def test_contextvar_isolates_nested_scopes() -> None:
    wrapped = _FakeWrappedAdapter()
    adapter = RecordingOpenAIAdapter(wrapped, agent="a", task=None)

    with conversation_recording() as outer:
        adapter.chat([{"role": "user", "content": "outer-1"}])
        with conversation_recording() as inner:
            adapter.chat([{"role": "user", "content": "inner-1"}])
        adapter.chat([{"role": "user", "content": "outer-2"}])

    # Outer sees only its two calls; inner sees only its one call.
    assert len(outer.turns) == 2
    assert len(inner.turns) == 1
    assert inner.turns[0].messages_sent[0]["content"] == "inner-1"
    assert outer.turns[0].messages_sent[0]["content"] == "outer-1"
    assert outer.turns[1].messages_sent[0]["content"] == "outer-2"


def test_getattr_forwards_arbitrary_attributes() -> None:
    wrapped = _FakeWrappedAdapter()
    adapter = RecordingOpenAIAdapter(wrapped, agent="a", task=None)

    # .config is a real property on the wrapper.
    assert adapter.config is wrapped.config
    # .custom_method is only on the wrapped adapter — forwarded via __getattr__.
    assert adapter.custom_method() == "custom"


def test_turn_index_is_monotonic() -> None:
    wrapped = _FakeWrappedAdapter()
    adapter = RecordingOpenAIAdapter(wrapped, agent="a", task=None)

    with conversation_recording() as recorder:
        adapter.chat([{"role": "user", "content": "a"}])
        adapter.structured_output(
            [{"role": "user", "content": "b"}], {"title": "T"}
        )

    assert [turn.turn_index for turn in recorder.turns] == [0, 1]


def test_node_boundary_is_a_frozen_dataclass() -> None:
    boundary = NodeBoundary(kind="start", node="eda_raw", ts="2026-04-16T00:00:00+00:00", elapsed_ms=12.5)
    assert boundary.kind == "start"
    assert boundary.node == "eda_raw"
    assert boundary.elapsed_ms == 12.5
    # Frozen — assignment should raise.
    try:
        boundary.kind = "end"  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot assign" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("NodeBoundary should be frozen")


def test_record_boundary_updates_current_node() -> None:
    recorder = ConversationRecorder()
    assert recorder.current_node is None

    recorder.record_boundary(
        NodeBoundary(kind="start", node="eda_raw", ts="t1", elapsed_ms=0.0)
    )
    assert recorder.current_node == "eda_raw"
    assert recorder.node_boundaries[-1].kind == "start"

    recorder.record_boundary(
        NodeBoundary(kind="end", node="eda_raw", ts="t2", elapsed_ms=10.0)
    )
    assert recorder.current_node is None
    assert len(recorder.node_boundaries) == 2

    # Error boundary also clears current_node when it matches.
    recorder.record_boundary(
        NodeBoundary(kind="start", node="ml_modeler_baseline", ts="t3", elapsed_ms=11.0)
    )
    recorder.record_boundary(
        NodeBoundary(kind="error", node="ml_modeler_baseline", ts="t4", elapsed_ms=12.0)
    )
    assert recorder.current_node is None


def test_turn_is_stamped_with_current_node() -> None:
    wrapped = _FakeWrappedAdapter()
    adapter = RecordingOpenAIAdapter(wrapped, agent="eda_analyst", task="raw")

    with conversation_recording() as recorder:
        recorder.record_boundary(
            NodeBoundary(kind="start", node="eda_raw", ts="t0", elapsed_ms=0.0)
        )
        adapter.chat([{"role": "user", "content": "x"}])
        recorder.record_boundary(
            NodeBoundary(kind="end", node="eda_raw", ts="t1", elapsed_ms=5.0)
        )
        # Outside any node boundary — turn.node should be None.
        adapter.chat([{"role": "user", "content": "y"}])

    assert recorder.turns[0].node == "eda_raw"
    assert recorder.turns[1].node is None


def test_flush_boundaries_returns_dicts() -> None:
    recorder = ConversationRecorder()
    recorder.record_boundary(
        NodeBoundary(kind="start", node="n", ts="t", elapsed_ms=1.0)
    )
    flushed = recorder.flush_boundaries()
    assert flushed == [{"kind": "start", "node": "n", "ts": "t", "elapsed_ms": 1.0}]
