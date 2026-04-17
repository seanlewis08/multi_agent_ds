"""Pure helper for embedding the recorded demo log into demo_viewer.html.

This module is I/O-free: caller reads the files, helper splices strings,
caller writes/renders. That split is what makes the helper unit-testable
without Streamlit or the filesystem.

Side effects belong in app.py's Demo tab body (reads files, calls
st.components.v1.html).

pattern: Functional Core + Imperative Shell
"""
from __future__ import annotations

_SCRIPT_OPEN = "<script>"


def inject_demo_log(viewer_html: str, demo_log_json: str) -> str:
    """Return viewer HTML with window.DEMO_LOG defined before the first <script>.

    Escapes closing-tag sequences so embedded JSON cannot break out of <script>.

    Parameters
    ----------
    viewer_html
        Full text of src/multi_agent_ds/demo_viewer.html.
    demo_log_json
        Raw JSON text (as read from data/interim/demo_run_latest.json).
        Must be valid JSON — this function does not re-parse it.

    Raises
    ------
    ValueError
        If viewer_html does not contain a <script> tag.
    """
    idx = viewer_html.find(_SCRIPT_OPEN)
    if idx == -1:
        raise ValueError(
            "viewer_html contains no <script> tag; cannot inject DEMO_LOG"
        )
    # Escape closing-tag sequence so embedded JSON cannot break out of <script>.
    safe = demo_log_json.replace("</", "<\\/")
    injection = f"<script>window.DEMO_LOG = {safe};</script>\n  "
    return viewer_html[:idx] + injection + viewer_html[idx:]
