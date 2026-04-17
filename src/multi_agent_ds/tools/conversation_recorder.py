"""Conversation recording infrastructure for agent-facing LLM adapters.

Pure in-memory recording. No I/O, no logging. A ``ConversationRecorder`` is
activated by the ``conversation_recording()`` context manager, and any
``RecordingOpenAIAdapter`` that wraps a real adapter will append a
``ConversationTurn`` to the active recorder on every ``chat`` or
``structured_output`` call. If there is no active recorder, the wrapper is
a zero-overhead pass-through.

The recorder is held in a ``ContextVar`` so that nested scopes (for example
two concurrent pipeline runs in the same process) cannot see each other's
turns.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ConversationTurn:
    """One recorded adapter call (chat or structured_output)."""

    turn_index: int
    agent: str
    task: str | None
    capability: str
    cost_tier: str
    model: str
    kind: str  # "chat" or "structured"
    messages_sent: list[dict[str, Any]]
    response: dict[str, Any]
    usage: dict[str, int] | None
    started_at: str  # ISO8601 UTC
    elapsed_ms: float
    node: str | None = None


@dataclass(frozen=True)
class NodeBoundary:
    """A LangGraph node start/end/error event, captured via astream_events."""

    kind: str  # "start" | "end" | "error"
    node: str
    ts: str  # ISO8601 UTC
    elapsed_ms: float


class ConversationRecorder:
    """Ordered collection of adapter turns for a single pipeline run."""

    def __init__(self) -> None:
        self.turns: list[ConversationTurn] = []
        self.node_boundaries: list[NodeBoundary] = []
        self.current_node: str | None = None

    def record(self, turn: ConversationTurn) -> None:
        """Append one turn to the recorder."""
        self.turns.append(turn)

    def record_boundary(self, boundary: NodeBoundary) -> None:
        """Append a node boundary and update ``current_node``.

        A ``start`` boundary sets ``current_node`` so subsequent turns recorded
        before the matching ``end`` are stamped with that node name. An ``end``
        or ``error`` boundary for the currently-active node clears it.
        """
        self.node_boundaries.append(boundary)
        if boundary.kind == "start":
            self.current_node = boundary.node
        elif boundary.kind in {"end", "error"}:
            if self.current_node == boundary.node:
                self.current_node = None

    def flush(self) -> list[dict[str, Any]]:
        """Return all turns as plain dicts (safe for JSON / HTML emission)."""
        return [asdict(turn) for turn in self.turns]

    def flush_boundaries(self) -> list[dict[str, Any]]:
        """Return all node boundaries as plain dicts."""
        return [asdict(boundary) for boundary in self.node_boundaries]


_active_recorder: ContextVar[ConversationRecorder | None] = ContextVar(
    "_active_recorder", default=None
)


@contextmanager
def conversation_recording() -> Iterator[ConversationRecorder]:
    """Activate a fresh recorder for the enclosed scope.

    Usage::

        with conversation_recording() as recorder:
            await compiled.ainvoke(initial_state)
        turns = recorder.flush()
    """
    recorder = ConversationRecorder()
    token = _active_recorder.set(recorder)
    try:
        yield recorder
    finally:
        _active_recorder.reset(token)


def get_active_recorder() -> ConversationRecorder | None:
    """Return the recorder active in the current context, or None."""
    return _active_recorder.get()


class RecordingOpenAIAdapter:
    """Transparent wrapper around a real adapter that records each call.

    The wrapper implements the two methods agents actually call (``chat`` and
    ``structured_output``) and forwards all other attribute access via
    ``__getattr__`` so existing agent code (which reads ``adapter.config``,
    for example) continues to work unchanged.
    """

    def __init__(
        self,
        wrapped: Any,
        *,
        agent: str,
        task: str | None,
    ) -> None:
        self._wrapped = wrapped
        self._agent = agent
        self._task = task

    @property
    def config(self) -> Any:
        """Expose the wrapped adapter's config for callers that introspect it."""
        return self._wrapped.config

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Forward a chat call and record the turn."""
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        response = self._wrapped.chat(messages, tools=tools)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record(
            kind="chat",
            messages_sent=messages,
            response=response,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
        )
        return response

    def structured_output(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Forward a structured_output call and record the turn."""
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        response = self._wrapped.structured_output(messages, schema)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._record(
            kind="structured",
            messages_sent=messages,
            response=response,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
        )
        return response

    def _record(
        self,
        *,
        kind: str,
        messages_sent: list[dict[str, Any]],
        response: dict[str, Any],
        started_at: str,
        elapsed_ms: float,
    ) -> None:
        """Build and commit a ``ConversationTurn`` to the active recorder."""
        recorder = get_active_recorder()
        if recorder is None:
            return

        config = getattr(self._wrapped, "config", None)
        capability = getattr(config, "capability", "unknown")
        cost_tier = getattr(config, "cost_tier", "unknown")
        model = getattr(config, "model", "unknown")
        usage = response.get("usage") if isinstance(response, dict) else None

        turn = ConversationTurn(
            turn_index=len(recorder.turns),
            agent=self._agent,
            task=self._task,
            capability=capability,
            cost_tier=cost_tier,
            model=model,
            kind=kind,
            messages_sent=messages_sent,
            response=response,
            usage=usage,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
            node=recorder.current_node,
        )
        recorder.record(turn)

    def __getattr__(self, name: str) -> Any:
        """Forward arbitrary attribute access to the wrapped adapter."""
        # Avoid recursion for our own private attributes.
        if name in {"_wrapped", "_agent", "_task"}:
            raise AttributeError(name)
        return getattr(self._wrapped, name)
