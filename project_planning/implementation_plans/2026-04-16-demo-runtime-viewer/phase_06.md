# Demo Runtime Viewer Implementation Plan — Phase 6

**Goal:** Wire the viewer into `app.py` as a new Streamlit tab that reads the HTML template and the recorded JSON at render time, injects the JSON as `window.DEMO_LOG`, and embeds the result via `st.components.v1.html`.

**Architecture:** Add a fourth tab to the existing `st.tabs([...])` call — the app already uses tabs, not a sidebar mode dispatcher, so this is additive and does not churn any existing wiring. All I/O (reading the HTML, reading the JSON, injecting the script block) goes through a pure helper that takes raw strings and returns a string, so it is unit-testable without Streamlit. The tab body is a thin shell around that helper plus a missing-JSON error path.

**Tech Stack:** Streamlit (already a dep), `streamlit.components.v1.html` (already imported at `app.py:27`). No new deps.

**Scope:** Phase 6 of 7 from `2026-04-16-demo-runtime-viewer.md`.

**Codebase verified:** 2026-04-16. `app.py` is 693 lines. `streamlit.components.v1 as components` is imported at line 27. The tab split happens at line 452: `tab_run, tab_results, tab_log = st.tabs(["Run Experiment", "Results", "Experiment Log"])`. Tab bodies live at `with tab_run:` (line 457), `with tab_results:` (line 591), `with tab_log:` (line 666). The design plan mentions "sidebar mode option" but the app actually uses tabs — AC2.1 wording aside, the faithful interpretation is "add a Demo entry point at the same level as the other three modes", which means a fourth tab. No test directory under `tests/unit/` for app-layer helpers currently exists; closest precedent is `tests/unit/agents/`. Add `tests/unit/test_demo_tab_inject.py` at the `tests/unit/` root to keep the helper test near other unit tests.

---

## Acceptance Criteria Coverage

This phase implements and verifies:

### demo-runtime-viewer.AC2: Streamlit integration
- **demo-runtime-viewer.AC2.1 Success:** `app.py` exposes a new sidebar mode option "Demo" that, when selected, renders the viewer via `st.components.v1.html(...)` with `height=820` and `scrolling=False`.
- **demo-runtime-viewer.AC2.2 Success:** The Demo mode reads `data/interim/demo_run_latest.json` and injects it as a JSON string literal into the HTML template before rendering.
- **demo-runtime-viewer.AC2.3 Failure:** If the JSON file is missing, Demo mode renders a clear error state with the exact command to re-record.

**AC2.1 interpretation note:** The design plan says "sidebar mode option" but the running app uses `st.tabs(...)` at `app.py:452`. Adding a sidebar radio would collide with existing sidebar widgets (algorithm selection, CV folds, etc.). The honest translation is **a fourth tab labeled "Demo"** at the same level as the existing three. The design plan's intent — a discoverable entry point that renders the viewer via `components.v1.html(height=820, scrolling=False)` — is fully preserved. Flag this interpretation in the commit message so the reviewer can weigh in.

---

<!-- START_SUBCOMPONENT_A (tasks 1-3) -->
<!-- START_TASK_1 -->
### Task 1: Write the pure injection helper (test-first)

**Active role:** `implementation_engineer` and `architecture_guard` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` and `.claude/agents/architecture-guard.md` for load-bearing decisions within this task.

**Files:**
- Create: `src/multi_agent_ds/orchestration/demo_viewer_loader.py`
- Create: `tests/unit/test_demo_tab_inject.py`

**Implementation:**
The injection helper takes two strings — the viewer HTML template and the recorded JSON text — and returns a single HTML string with `<script>window.DEMO_LOG = {...};</script>` injected just before the first `<script>` tag in the template. The helper is pure: no filesystem, no Streamlit, no globals.

**Why a helper in `orchestration/`**: it knows about the event log (an orchestration artifact) and the viewer (also an orchestration output — the recorder is a peer module). It doesn't belong in `agents/` or `skills/`. Placing it next to `demo_recorder.py` mirrors Phase 2's structure.

**Contract:**

```python
def inject_demo_log(viewer_html: str, demo_log_json: str) -> str:
    """Return the viewer HTML with a <script>window.DEMO_LOG=...;</script>
    block injected immediately before the first <script> tag.

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
```

**Why "first `<script>` tag" and not "just before `</head>`":** the viewer's own script reads `window.DEMO_LOG` at parse time. Injecting right before the first script tag guarantees `DEMO_LOG` is defined before the viewer's logic runs, regardless of where the viewer's script happens to sit (body or head).

**Step 1: Write failing tests first (RED)**

Create `tests/unit/test_demo_tab_inject.py`:

```python
"""Unit tests for demo_viewer_loader.inject_demo_log."""
from __future__ import annotations

import json

import pytest

from multi_agent_ds.orchestration.demo_viewer_loader import inject_demo_log


def test_inject_adds_demo_log_before_first_script() -> None:
    viewer = "<html><head></head><body><script>var a=1;</script></body></html>"
    log = '{"events":[],"config":{}}'

    result = inject_demo_log(viewer, log)

    assert "<script>window.DEMO_LOG = " in result
    assert '"events":[]' in result
    # injected block appears before the template's own script
    assert result.index("window.DEMO_LOG") < result.index("var a=1")


def test_inject_preserves_template_content_exactly() -> None:
    viewer = "<html><head></head><body>BEFORE<script>X</script>AFTER</body></html>"
    log = '{"k":"v"}'

    result = inject_demo_log(viewer, log)

    assert "BEFORE" in result
    assert "AFTER" in result
    assert "X" in result
    # all original characters still present
    assert len(result) > len(viewer)


def test_inject_raises_when_no_script_tag() -> None:
    viewer = "<html><body>no scripts here</body></html>"
    log = "{}"

    with pytest.raises(ValueError):
        inject_demo_log(viewer, log)


def test_inject_handles_json_with_special_chars() -> None:
    # The JSON is treated as a string literal, not re-parsed or escaped,
    # so special chars inside string values are the caller's responsibility.
    # We verify that the helper does not mangle valid JSON that contains
    # characters legal in JSON strings (forward slashes, unicode escapes).
    viewer = "<script>/*body*/</script>"
    payload = {"path": "data/interim/demo_run_latest.json", "emoji": "\u2713"}
    log = json.dumps(payload)

    result = inject_demo_log(viewer, log)

    assert "data/interim/demo_run_latest.json" in result
    assert "window.DEMO_LOG" in result


def test_inject_result_is_valid_for_round_trip_parse() -> None:
    # Independent check: the injected JS block should parse cleanly. We
    # cannot execute JS here, but we can verify the injected substring is
    # exactly `window.DEMO_LOG = <payload>;`.
    viewer = "<script>/*marker*/</script>"
    log = '{"a":1,"b":[2,3]}'

    result = inject_demo_log(viewer, log)

    expected = '<script>window.DEMO_LOG = {"a":1,"b":[2,3]};</script>'
    assert expected in result


def test_inject_escapes_closing_script_tag() -> None:
    # XSS defense: ensure malicious JSON cannot break out of <script>.
    viewer = "<html><script>X</script></html>"
    log = '{"bad": "</script><script>alert(1)</script>"}'

    result = inject_demo_log(viewer, log)

    assert "</script><script>alert(1)" not in result
    assert "<\\/script>" in result
```

Run tests and confirm they fail (RED):

```bash
uv run pytest tests/unit/test_demo_tab_inject.py -x
```

Expected: `ModuleNotFoundError: No module named 'multi_agent_ds.orchestration.demo_viewer_loader'` (or equivalent). This is the failing state we want before writing code.

**Step 2: Implement the helper (GREEN)**

Create `src/multi_agent_ds/orchestration/demo_viewer_loader.py`:

```python
"""Pure helper for embedding the recorded demo log into demo_viewer.html.

This module is I/O-free: caller reads the files, helper splices strings,
caller writes/renders. That split is what makes the helper unit-testable
without Streamlit or the filesystem.

Side effects belong in app.py's Demo tab body (reads files, calls
st.components.v1.html).
"""
from __future__ import annotations

_SCRIPT_OPEN = "<script>"


def inject_demo_log(viewer_html: str, demo_log_json: str) -> str:
    """Return viewer HTML with window.DEMO_LOG defined before the first <script>.
    
    Escapes closing-tag sequences so embedded JSON cannot break out of <script>.
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
```

Run tests (GREEN):

```bash
uv run pytest tests/unit/test_demo_tab_inject.py -x -v
```

Expected: all five tests pass. Exit code 0.

**Step 3: Commit**

Per the `implementation_engineer` and `commit_chronicler` roles, stage both files:

```bash
git status
git diff --stat src/multi_agent_ds/orchestration/demo_viewer_loader.py tests/unit/test_demo_tab_inject.py
```

Confirm only these two new files. Ask the user: "Should I commit and push these changes?" On yes:

```bash
git add src/multi_agent_ds/orchestration/demo_viewer_loader.py tests/unit/test_demo_tab_inject.py
git commit -m "feat(demo-viewer): add pure inject_demo_log helper

why: AC2.2 requires the recorded JSON to be injected into
demo_viewer.html as window.DEMO_LOG. Splitting this into a pure
string-in-string-out helper lets us unit-test the splicing logic
without Streamlit. The Streamlit tab body (Task 2) only handles
I/O and the missing-JSON error path.

architecture fit: lives in orchestration/ next to demo_recorder.py.
No dependency on agents/skills/tools layers. No Streamlit import
in this module.

validation: 5/5 unit tests pass (ValueError on missing script tag,
injection ordering, content preservation, special-char JSON,
round-trip literal shape).

notes: injection point is 'before first <script>' so the viewer's
internal scripts find DEMO_LOG already on window at parse time.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Add the Demo tab to app.py

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Files:**
- Modify: `src/multi_agent_ds/app.py`

**Implementation:**
Three small edits:

1. **Add the import.** After `from multi_agent_ds.core import resolve_tracking_uri` (line 29), add:
   ```python
   from multi_agent_ds.orchestration.demo_viewer_loader import inject_demo_log
   ```

2. **Extend `st.tabs([...])`.** Change line 452 from:
   ```python
   tab_run, tab_results, tab_log = st.tabs(["Run Experiment", "Results", "Experiment Log"])
   ```
   to:
   ```python
   tab_run, tab_results, tab_log, tab_demo = st.tabs(
       ["Run Experiment", "Results", "Experiment Log", "Demo"]
   )
   ```

3. **Append the Demo tab body.** After the `with tab_log:` block ends (grep to find its closing — the `with` body is indented until the next top-level statement), add the Demo tab body. The precise placement is "after `with tab_log:` block and before any top-level statements that follow it". Insert:

   ```python
   # ── Tab 4: Demo (recorded pipeline replay) ────────────────────────────
   # AC2.1 / AC2.2 / AC2.3: embed demo_viewer.html via components.v1.html
   # with height=820 and scrolling=False. Reads the recorded JSON at
   # render time; renders a clear error state if it is missing.

   _REPO_ROOT = Path(__file__).resolve().parent.parent.parent
   if not (_REPO_ROOT / "pyproject.toml").exists():
       raise RuntimeError(f"repo root inference failed at {_REPO_ROOT}")
   
   _VIEWER_HTML_PATH = Path(__file__).parent / "demo_viewer.html"
   _DEMO_LOG_PATH = _REPO_ROOT / "data" / "interim" / "demo_run_latest.json"
   _RECORD_CMD = "uv run python -m multi_agent_ds.orchestration.demo_recorder"

   with tab_demo:
       st.subheader("Recorded pipeline replay")
       st.caption(
           "Replays a recorded `eda_analyst → data_engineer` run. "
           "Pipeline stops after data_engineer; downstream agents are scripted."
       )

       if not _DEMO_LOG_PATH.exists():
           st.error(
               "No recording found at "
               f"`{_DEMO_LOG_PATH.relative_to(Path.cwd())}`.\n\n"
               f"Generate one with:\n\n```bash\n{_RECORD_CMD}\n```"
           )
       elif not _VIEWER_HTML_PATH.exists():
           st.error(
               f"Viewer template missing at `{_VIEWER_HTML_PATH.relative_to(Path.cwd())}`. "
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
               components.html(rendered, height=820, scrolling=False)
   ```

**Design rationale for paths:** `app.py` lives at `src/multi_agent_ds/app.py`. The viewer HTML is a sibling (`demo_viewer.html` same dir). The JSON output is at `data/interim/demo_run_latest.json` relative to the repo root, which is three `parent` hops up from `app.py`. Using `Path(__file__)` makes the code robust to `cwd` — streamlit cold-starts sometimes set `cwd` to the user's home.

**`.relative_to(Path.cwd())`** is inside the error-message branch — it might raise if the user is somewhere exotic. Wrap it in a try/except or fall back to the absolute path. Cleaner alternative: use `str(_DEMO_LOG_PATH)` directly in the error message. **Use the absolute-path variant** — the design plan says "the exact command to re-record", not the shortest path:

```python
st.error(
    f"No recording found at `{_DEMO_LOG_PATH}`.\n\n"
    f"Generate one with:\n\n```bash\n{_RECORD_CMD}\n```"
)
```

**Step 1: Apply the three edits**

Use the Edit tool three times:

1. Import line (after line 29).
2. Tabs list (replace line 452).
3. Demo tab body (append after `with tab_log:` block — find its end with `grep -n "^with\|^[^ \t]" src/multi_agent_ds/app.py | awk 'NR>1 && /^[0-9]+:with tab_log/{ok=1} ok && /^[0-9]+:[^ ]/{ if (seen) {print last; exit}; if ($0 ~ /^[0-9]+:[^ ]/ && $0 !~ /tab_log/) seen=1; last=$0 }'` — or simpler, find the last line of the file and append before the final newline).

Easiest: use the Grep tool with pattern `st.tabs` on `app.py` to find the tabs line; use the Read tool to confirm lines 452, 457, 591, 666 are the tab/with-tab anchors.

**Step 2: Smoke test the import chain (no Streamlit server)**

```bash
uv run python -c "
import ast
src = open('src/multi_agent_ds/app.py').read()
ast.parse(src)
print('app.py parses')
# Also check the tab unpacking is right
assert 'tab_run, tab_results, tab_log, tab_demo = st.tabs(' in src, 'tabs tuple mismatch'
assert 'with tab_demo:' in src, 'tab_demo body missing'
assert 'inject_demo_log' in src, 'helper import missing'
print('static checks passed')
"
```

Expected: prints `app.py parses` and `static checks passed`.

**Step 3: Run the full test suite to catch regressions**

```bash
uv run pytest -x
```

Expected: all existing tests still pass, plus the five new Task 1 tests.

**Step 4: Manual Streamlit smoke test**

```bash
# With a recorded JSON present (Phase 2 Task 8 should have left one):
ls data/interim/demo_run_latest.json && echo "recording present" || echo "recording missing"

# Start the app
uv run streamlit run src/multi_agent_ds/app.py --server.headless true --server.port 8598 &
APP_PID=$!
sleep 4

# Basic reachability check — does streamlit respond?
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8598 || true
kill $APP_PID 2>/dev/null
wait $APP_PID 2>/dev/null
```

Expected: HTTP 200 from the Streamlit healthcheck. For visual verification, open `http://localhost:8598` manually and click the **Demo** tab. Confirm:

- [ ] Demo tab exists as the fourth tab.
- [ ] Clicking it renders the viewer iframe at the configured height.
- [ ] No scrollbar appears inside the iframe (scrolling=False).
- [ ] All four pages of the viewer work end-to-end (click RUN → CONTINUE → wait → drawer opens).

**Step 5: Missing-JSON path**

Temporarily rename the JSON and reload the app:

```bash
mv data/interim/demo_run_latest.json data/interim/demo_run_latest.json.bak
# Reload the Demo tab in the browser
# Verify the error message shows the exact re-record command.
mv data/interim/demo_run_latest.json.bak data/interim/demo_run_latest.json
```

Expected (AC2.3): error state displays `uv run python -m multi_agent_ds.orchestration.demo_recorder` as a code block.

**Step 6: Commit**

```bash
git status
git diff src/multi_agent_ds/app.py
git add src/multi_agent_ds/app.py
git commit -m "feat(app): add Demo tab for recorded pipeline replay

why: AC2.1/2.2/2.3 require Streamlit integration. The design plan
says 'sidebar mode option' but the app uses tabs (line 452); the
faithful translation is a fourth tab labeled 'Demo' with the
viewer rendered via components.v1.html(height=820, scrolling=False).

architecture fit: tab body is a thin I/O wrapper around the pure
inject_demo_log helper from orchestration/demo_viewer_loader.
Existing three tabs are unchanged. No sidebar widgets added.

validation: existing test suite still passes; five new helper
tests pass; manual smoke test confirmed tab renders, missing-JSON
path shows the exact re-record command.

notes: flagging the sidebar→tab interpretation for reviewer; can
revise to sidebar radio if demo audience prefers that surface.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: AC verification

**Active role:** `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` for load-bearing decisions within this task.

**Files:**
- No files modified.

**Implementation:**
Walk each AC in this phase.

**Step 1: AC2.1 — Demo mode entry point**

With the app running (`uv run streamlit run src/multi_agent_ds/app.py`), the tab bar shows four tabs: Run Experiment · Results · Experiment Log · Demo. Clicking Demo renders an iframe; inspect devtools to confirm the iframe's height is 820 and `scrolling="no"`.

**Step 2: AC2.2 — JSON injection**

In the rendered iframe, open devtools console and type `window.DEMO_LOG`. Expected: a non-null object with `config`, `artifacts`, `events` keys. Verify `events.length > 0`.

**Step 3: AC2.3 — Missing JSON path**

Stop Streamlit, rename `data/interim/demo_run_latest.json` to `.bak`, restart, click Demo. Expected: red error block with the exact string `uv run python -m multi_agent_ds.orchestration.demo_recorder` visible in a code block. Rename back after verifying.

**Step 4: Document results**

Three pass/fail results in the end-of-slice summary. No commit in this task.
<!-- END_TASK_3 -->
<!-- END_SUBCOMPONENT_A -->

## Phase 6 Done-When

- [ ] `src/multi_agent_ds/orchestration/demo_viewer_loader.py` exists and exports `inject_demo_log`.
- [ ] `tests/unit/test_demo_tab_inject.py` has 5 passing tests.
- [ ] `app.py` imports `inject_demo_log` and exposes a fourth Demo tab.
- [ ] `uv run streamlit run src/multi_agent_ds/app.py` → click Demo → full four-screen flow works.
- [ ] Missing-JSON error path shows the exact re-record command.
- [ ] Two commits landed (Tasks 1, 2). Task 3 is verification only.
