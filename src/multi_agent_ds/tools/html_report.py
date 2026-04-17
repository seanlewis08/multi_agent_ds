"""Pure HTML emitter for recorded agent conversations.

Produces a single self-contained HTML document — no Jinja2, no external CSS,
no JavaScript — showing every recorded adapter turn grouped by pipeline
phase, with collapsible system prompts and pretty-printed structured
responses.

Inputs are plain dicts (see
``multi_agent_ds.tools.conversation_recorder.ConversationRecorder.flush``)
so this module is not coupled to the recorder types.
"""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CAPABILITY_COLORS: dict[str, str] = {
    "coding": "#2563eb",  # blue
    "balanced": "#16a34a",  # green
    "reasoning": "#9333ea",  # purple
}
_DEFAULT_CAPABILITY_COLOR = "#64748b"  # slate

# Phase-banded left border colors — rotated per distinct phase.
_PHASE_PALETTE: tuple[str, ...] = (
    "#2563eb",
    "#16a34a",
    "#9333ea",
    "#f59e0b",
    "#dc2626",
    "#0891b2",
    "#7c3aed",
    "#ea580c",
)


def _escape(value: Any) -> str:
    """HTML-escape any value after string coercion."""
    return html.escape(str(value), quote=True)


def _capability_color(capability: str) -> str:
    """Return the brand color for a capability label."""
    return _CAPABILITY_COLORS.get(capability, _DEFAULT_CAPABILITY_COLOR)


def _assign_phases_to_turns(
    turns: list[dict[str, Any]],
    agent_decisions: list[dict[str, Any]],
) -> list[str]:
    """Assign a phase label to each turn in chronological order.

    Heuristic: recorded turns are monotonic per-agent in call order. For each
    turn with ``agent=A``, its phase is the phase of the ``n``th entry in
    ``agent_decisions`` whose agent is ``A``, where ``n`` is the per-agent
    call count observed so far in the turn list.
    """
    # Build per-agent phase lists from agent_decisions (order preserved).
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
            # Clamp to last phase if we've exhausted the decisions list.
            phase = phases_for_agent[min(index, len(phases_for_agent) - 1)]
        else:
            phase = "unknown"
        assignments.append(phase)
        per_agent_counter[agent] = index + 1
    return assignments


def _phase_color_map(phase_order: list[str]) -> dict[str, str]:
    """Assign a distinct palette color to each phase in first-seen order."""
    mapping: dict[str, str] = {}
    seen: list[str] = []
    for phase in phase_order:
        if phase in mapping:
            continue
        mapping[phase] = _PHASE_PALETTE[len(seen) % len(_PHASE_PALETTE)]
        seen.append(phase)
    return mapping


def _format_response_body(turn: dict[str, Any]) -> str:
    """Pretty-print the response payload for display."""
    response = turn.get("response") or {}
    kind = turn.get("kind")
    if kind == "structured":
        parsed = response.get("parsed", response)
        return json.dumps(parsed, indent=2, sort_keys=True, default=str)
    # chat
    content = response.get("content")
    if content is None:
        return json.dumps(response, indent=2, sort_keys=True, default=str)
    return str(content)


def _format_messages(messages_sent: list[dict[str, Any]]) -> tuple[str, str]:
    """Return (system_prompt_text, user_prompt_text) extracted from the messages."""
    system_parts: list[str] = []
    user_parts: list[str] = []
    for message in messages_sent:
        role = message.get("role")
        content = message.get("content", "")
        if role == "system":
            system_parts.append(str(content))
        else:
            # Everything non-system (user, tool, assistant, etc.) is rendered
            # in the "user prompt" panel with a role prefix for clarity.
            if role and role != "user":
                user_parts.append(f"[{role}]\n{content}")
            else:
                user_parts.append(str(content))
    return ("\n\n".join(system_parts), "\n\n".join(user_parts))


def _sum_tokens(turns: list[dict[str, Any]]) -> tuple[int, int]:
    """Sum input and output tokens across all turns."""
    total_in = 0
    total_out = 0
    for turn in turns:
        usage = turn.get("usage") or {}
        total_in += int(usage.get("input_tokens") or 0)
        total_out += int(usage.get("output_tokens") or 0)
    return total_in, total_out


_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: #f8fafc;
  color: #0f172a;
}
header.page-header {
  background: #0f172a;
  color: #f8fafc;
  padding: 24px 32px;
}
header.page-header h1 { margin: 0 0 4px; font-size: 22px; }
header.page-header .meta { font-size: 13px; color: #cbd5e1; }
header.page-header .stats { margin-top: 8px; font-size: 13px; }
header.page-header .stats span { margin-right: 16px; }
header.page-header .error-banner {
  background: #7f1d1d; color: #fee2e2; padding: 10px 14px;
  border-radius: 6px; margin-top: 12px; font-size: 13px;
}
.layout {
  display: flex;
  gap: 24px;
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}
nav.sidebar {
  width: 240px;
  flex: 0 0 240px;
  position: sticky;
  top: 24px;
  align-self: flex-start;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(15,23,42,0.06);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
}
nav.sidebar h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em;
  color: #64748b; margin: 0 0 8px; }
nav.sidebar ul { list-style: none; padding: 0; margin: 0 0 16px; }
nav.sidebar li { margin: 4px 0; }
nav.sidebar a {
  display: block; padding: 6px 10px; border-radius: 4px; font-size: 13px;
  color: #0f172a; text-decoration: none;
}
nav.sidebar a:hover { background: #e2e8f0; }
main { flex: 1; min-width: 0; }
.empty-notice {
  background: #fff; border-radius: 8px; padding: 32px; text-align: center;
  color: #64748b; box-shadow: 0 1px 2px rgba(15,23,42,0.06);
}
article.turn-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px rgba(15,23,42,0.06);
  border-left: 4px solid #64748b;
}
.turn-header {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-bottom: 12px;
}
.turn-header .turn-index {
  font-size: 12px; color: #64748b; margin-right: 4px;
}
.badge {
  display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 12px;
  color: #fff; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.03em;
}
.badge.agent { background: #334155; }
.badge.task { background: #475569; }
.badge.model { background: #1e293b; }
.badge.phase { background: #0f172a; }
.turn-timing {
  margin-left: auto; font-size: 12px; color: #64748b;
}
details.system-prompt {
  background: #f1f5f9; border-radius: 6px; padding: 8px 12px; margin-bottom: 10px;
}
details.system-prompt summary {
  cursor: pointer; font-size: 13px; font-weight: 600; color: #334155;
}
.user-prompt, .response {
  margin-top: 10px;
}
.user-prompt h4, .response h4 {
  margin: 0 0 6px; font-size: 13px; color: #475569; text-transform: uppercase;
  letter-spacing: 0.04em;
}
pre {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
}
.error { color: #b91c1c; font-weight: 600; }
@media (max-width: 900px) {
  .layout { flex-direction: column; }
  nav.sidebar { width: 100%; position: static; }
}
"""


def _render_header(meta: dict[str, Any], turns: list[dict[str, Any]]) -> str:
    """Render the top banner with run-level metadata."""
    title = _escape(meta.get("title", "Agent Conversation Report"))
    started_at = _escape(meta.get("started_at", ""))
    duration_ms = meta.get("duration_ms")
    duration_str = f"{float(duration_ms):.0f} ms" if duration_ms is not None else "—"
    turn_count = _escape(meta.get("turn_count", len(turns)))
    tokens_in, tokens_out = _sum_tokens(turns)
    html_output_path = _escape(meta.get("html_output_path", ""))
    entry_node = _escape(meta.get("entry_node", ""))
    data_path = _escape(meta.get("data_path") or "")
    error = meta.get("error")

    error_html = ""
    if error:
        error_html = f'<div class="error-banner">Run error: {_escape(error)}</div>'

    return f"""
    <header class="page-header">
      <h1>{title}</h1>
      <div class="meta">
        <span>Started: {started_at}</span>
        <span> | Entry node: {entry_node}</span>
        <span> | Data path: {data_path}</span>
      </div>
      <div class="stats">
        <span>Duration: {_escape(duration_str)}</span>
        <span>Turns: {turn_count}</span>
        <span>Input tokens: {tokens_in}</span>
        <span>Output tokens: {tokens_out}</span>
        <span>Report path: {html_output_path}</span>
      </div>
      {error_html}
    </header>
    """


def _render_sidebar(
    turn_phases: list[str],
    turns: list[dict[str, Any]],
) -> str:
    """Render the left-hand navigation listing each phase once."""
    first_turn_by_phase: dict[str, int] = {}
    phase_order: list[str] = []
    for phase, turn in zip(turn_phases, turns):
        if phase not in first_turn_by_phase:
            first_turn_by_phase[phase] = int(turn.get("turn_index", 0))
            phase_order.append(phase)

    if not phase_order:
        return '<nav class="sidebar"><h2>Phases</h2><p style="font-size:13px;color:#64748b;">No turns.</p></nav>'

    items = "\n".join(
        f'<li><a href="#turn-{first_turn_by_phase[phase]}">{_escape(phase)}</a></li>'
        for phase in phase_order
    )
    return f"""
    <nav class="sidebar">
      <h2>Phases</h2>
      <ul>{items}</ul>
    </nav>
    """


def _render_turn(
    turn: dict[str, Any],
    phase: str,
    phase_color: str,
) -> str:
    """Render one turn card."""
    turn_index = int(turn.get("turn_index", 0))
    agent = _escape(turn.get("agent", "unknown"))
    task = _escape(turn.get("task") or "—")
    model = _escape(turn.get("model", "unknown"))
    capability = turn.get("capability", "unknown")
    capability_label = _escape(capability)
    cost_tier = _escape(turn.get("cost_tier", "unknown"))
    kind = _escape(turn.get("kind", "chat"))
    started_at = _escape(turn.get("started_at", ""))
    elapsed_ms = turn.get("elapsed_ms")
    elapsed_str = f"{float(elapsed_ms):.0f} ms" if elapsed_ms is not None else "—"
    capability_color = _capability_color(str(capability))

    system_text, user_text = _format_messages(turn.get("messages_sent") or [])
    response_body = _format_response_body(turn)

    usage = turn.get("usage") or {}
    usage_str = (
        f"{usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out"
        if usage
        else "no usage reported"
    )

    system_block = ""
    if system_text:
        system_block = (
            f'<details class="system-prompt"><summary>System prompt</summary>'
            f"<pre>{_escape(system_text)}</pre></details>"
        )

    return f"""
    <article class="turn-card" id="turn-{turn_index}" data-phase="{_escape(phase)}"
             style="border-left-color: {phase_color};">
      <div class="turn-header">
        <span class="turn-index">#{turn_index}</span>
        <span class="badge agent">{agent}</span>
        <span class="badge task">{task}</span>
        <span class="badge model" style="background: {capability_color};">{capability_label}/{cost_tier}</span>
        <span class="badge model">{model}</span>
        <span class="badge phase">{_escape(phase)}</span>
        <span class="turn-timing">{started_at} &middot; {_escape(elapsed_str)} &middot; {_escape(usage_str)}</span>
      </div>
      {system_block}
      <div class="user-prompt">
        <h4>User prompt</h4>
        <pre>{_escape(user_text)}</pre>
      </div>
      <div class="response">
        <h4>Response ({kind})</h4>
        <pre>{_escape(response_body)}</pre>
      </div>
    </article>
    """


def render_conversation_html(
    turns: list[dict[str, Any]],
    agent_decisions: list[dict[str, Any]],
    meta: dict[str, Any],
) -> str:
    """Render a full self-contained HTML document for a recorded run."""
    turn_phases = _assign_phases_to_turns(turns, agent_decisions)
    phase_colors = _phase_color_map(turn_phases)

    header_html = _render_header(meta, turns)
    sidebar_html = _render_sidebar(turn_phases, turns)

    if not turns:
        body_html = (
            '<div class="empty-notice">No turns were recorded for this run.</div>'
        )
    else:
        body_html = "\n".join(
            _render_turn(turn, phase, phase_colors.get(phase, _DEFAULT_CAPABILITY_COLOR))
            for turn, phase in zip(turns, turn_phases)
        )

    title = _escape(meta.get("title", "Agent Conversation Report"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>{_CSS}</style>
</head>
<body>
  {header_html}
  <div class="layout">
    {sidebar_html}
    <main>{body_html}</main>
  </div>
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
    document = render_conversation_html(turns, agent_decisions, meta_with_path)
    primary_path.write_text(document, encoding="utf-8")

    latest_path = primary_path.parent / "conversation_latest.html"
    try:
        shutil.copy2(primary_path, latest_path)
    except OSError:
        # Fall back to re-writing the content if copy2 fails (e.g., on a
        # filesystem that disallows metadata copy).
        latest_path.write_text(document, encoding="utf-8")

    return primary_path
