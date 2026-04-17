"""Standalone Streamlit app for the recorded demo replay.

Run with:
    uv run streamlit run src/multi_agent_ds/demo_app.py

Exists so the recorded-pipeline viewer can be shown in isolation from
``app.py`` — no MLflow auto-launch, no pipeline imports, no sidebar
controls — which makes it suitable for screen recording and for demoing
the viewer without the main dashboard's side effects.

Reuses ``demo_viewer.html`` and the pure ``inject_demo_log`` helper.
Adds no new business logic. The Demo tab inside ``app.py`` is kept as-is;
this module is an additional entry point, not a replacement.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from multi_agent_ds.orchestration.demo_viewer_loader import inject_demo_log

# ── Page chrome ───────────────────────────────────────────────────────
# Wide layout + collapsed sidebar + hidden Streamlit header/footer so
# the viewer iframe dominates the maximized browser viewport.
st.set_page_config(
    page_title="Multi-Agent DS — Demo Replay",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
      /* Give the viewer the full width of the page and drop default
         top/bottom padding so a maximized browser window shows the
         viewer, not empty Streamlit chrome. Horizontal padding is also
         zeroed so the iframe is wide enough to fit the viewer's fixed
         1280 px page frame — otherwise the right edge (CONTINUE button,
         right-most table columns) gets clipped and is unreachable. */
      div[data-testid="stAppViewContainer"] > .main .block-container {
          padding: 0.5rem 0 0 0 !important;
          max-width: 100% !important;
      }
      header[data-testid="stHeader"] { display: none; }
      footer { display: none; }
      /* Kill the collapsed-sidebar rail entirely — no sidebar is used by
         this page, and the reserved gutter pushes the iframe rightward,
         which reads as a "phantom left sidebar" shift. */
      section[data-testid="stSidebar"] { display: none !important; }
      [data-testid="collapsedControl"] { display: none !important; }
      [data-testid="stSidebarCollapsedControl"] { display: none !important; }
      /* Make the components.html iframe take the full available width
         with no inherited border artifact. */
      iframe { width: 100% !important; border: 0 !important; display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Paths (same inference used by app.py's Demo tab) ──────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if not (_REPO_ROOT / "pyproject.toml").exists():
    raise RuntimeError(f"repo root inference failed at {_REPO_ROOT}")

_VIEWER_HTML_PATH = Path(__file__).parent / "demo_viewer.html"
_DEMO_LOG_PATH = _REPO_ROOT / "data" / "interim" / "demo_run_latest.json"
_RECORD_CMD = "uv run python -m multi_agent_ds.orchestration.demo_recorder"

# Tall enough for a maximized browser viewport on a MacBook Pro
# (~1100 CSS px). The viewer's internal pages are ~820 px, so any
# remaining vertical space reads as breathing room rather than scroll.
_VIEWER_HEIGHT = 1100

# ── Body ──────────────────────────────────────────────────────────────
if not _DEMO_LOG_PATH.exists():
    st.error(
        f"No recording found at `{_DEMO_LOG_PATH}`.\n\n"
        f"Generate one with:\n\n```bash\n{_RECORD_CMD}\n```"
    )
elif not _VIEWER_HTML_PATH.exists():
    st.error(
        f"Viewer template missing at `{_VIEWER_HTML_PATH}`. "
        "This should not happen — check your install."
    )
else:
    viewer_html = _VIEWER_HTML_PATH.read_text()
    demo_log_json = _DEMO_LOG_PATH.read_text()
    try:
        rendered = inject_demo_log(viewer_html, demo_log_json)
    except ValueError as exc:
        st.error(f"Could not prepare demo viewer: {exc}")
    else:
        # scrolling=True is a safety net: if the user's viewport is
        # narrower than 1280 px (the viewer's fixed page width), the
        # iframe grows a scrollbar instead of silently clipping the
        # CONTINUE button and right-most table columns. With the CSS
        # above zeroing block-container padding and hiding the sidebar
        # rail, a maximized MBP viewport is comfortably wider than
        # 1280 px and no scrollbar should appear in practice.
        components.html(rendered, height=_VIEWER_HEIGHT, scrolling=True)
