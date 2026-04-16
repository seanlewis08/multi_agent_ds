"""LangGraph debugging helpers for local graph inspection and tracing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any


def get_debug_graph(compiled_graph: Any, xray: int | bool = False) -> Any:
    """Return the compiled LangGraph graph object for inspection."""
    return compiled_graph.get_graph(xray=xray)


def _render_graph_fallback(graph: Any) -> str:
    """Build a dependency-free textual graph summary."""
    node_names = sorted(graph.nodes.keys())
    edge_lines = [f"{edge.source} -> {edge.target}" for edge in graph.edges]
    return "\n".join(
        [
            "LangGraph Debug View",
            "",
            "Nodes:",
            *[f"- {name}" for name in node_names],
            "",
            "Edges:",
            *[f"- {line}" for line in edge_lines],
        ]
    )


def render_graph_ascii(compiled_graph: Any, xray: int | bool = False) -> str:
    """Render the graph as ASCII, falling back to a textual edge list if needed."""
    graph = get_debug_graph(compiled_graph, xray=xray)
    try:
        return graph.draw_ascii()
    except ImportError:
        return _render_graph_fallback(graph)


def render_graph_mermaid(compiled_graph: Any, xray: int | bool = False) -> str:
    """Render the graph as Mermaid text."""
    return get_debug_graph(compiled_graph, xray=xray).draw_mermaid()


async def stream_graph_events(
    compiled_graph: Any,
    input_state: Any,
    *,
    config: Any | None = None,
    version: str = "v2",
    include_names: Sequence[str] | None = None,
    include_types: Sequence[str] | None = None,
    include_tags: Sequence[str] | None = None,
    exclude_names: Sequence[str] | None = None,
    exclude_types: Sequence[str] | None = None,
    exclude_tags: Sequence[str] | None = None,
    **kwargs: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Yield LangGraph execution events for one invocation."""
    async for event in compiled_graph.astream_events(
        input_state,
        config=config,
        version=version,
        include_names=include_names,
        include_types=include_types,
        include_tags=include_tags,
        exclude_names=exclude_names,
        exclude_types=exclude_types,
        exclude_tags=exclude_tags,
        **kwargs,
    ):
        yield event


def collect_graph_events(
    compiled_graph: Any,
    input_state: Any,
    *,
    config: Any | None = None,
    version: str = "v2",
    include_names: Sequence[str] | None = None,
    include_types: Sequence[str] | None = None,
    include_tags: Sequence[str] | None = None,
    exclude_names: Sequence[str] | None = None,
    exclude_types: Sequence[str] | None = None,
    exclude_tags: Sequence[str] | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Collect LangGraph execution events into a list for debugging."""

    async def _collect() -> list[dict[str, Any]]:
        return [
            event
            async for event in stream_graph_events(
                compiled_graph,
                input_state,
                config=config,
                version=version,
                include_names=include_names,
                include_types=include_types,
                include_tags=include_tags,
                exclude_names=exclude_names,
                exclude_types=exclude_types,
                exclude_tags=exclude_tags,
                **kwargs,
            )
        ]

    return asyncio.run(_collect())
