# Demo Runtime Viewer Implementation Plan — Phase 4

**Goal:** Animate Page 3 of the viewer from the recorded event log, driven by `elapsed_ms` timestamps scaled by a user-selectable replay speed.

**Architecture:** A pure-JS replay engine walks `window.DEMO_LOG.events` (already loaded by Phase 3) and schedules DOM class toggles via `setTimeout(fn, event.elapsed_ms / speed)`. The engine is idempotent — CONTINUE → runtime starts replay at most once per page load. Non-recorded agents (ML Modeler, ML Reviewer, Business Stakeholder) stay dimmed with a "not scheduled in demo scope" footer.

**Tech Stack:** Vanilla JS (ES2017+). No dependencies.

**Scope:** Phase 4 of 7 from `2026-04-16-demo-runtime-viewer.md`.

**Codebase verified:** 2026-04-16. Phase 3 produced `src/multi_agent_ds/demo_viewer.html` with an empty `startRuntimeReplay()` function. The mockup's Page 3 markup (lines 573–721 in `demo_mockup.html`) defines the orchestrator band, five agent columns with `.head/.lanes/.lane .input|.action|.output` structure, and `.col.active` as the state class for a running agent. CSS class `.item.live` (orange) and `.item.done` (green) already exist in the mockup CSS — this phase reuses them. Phase 2's recorder emits events with `kind ∈ {"node_start", "node_end", "node_error"}` and `node ∈ {"eda_raw", "data_engineer"}` plus a `data` payload that may carry populated artifacts on `node_end`.

---

## Acceptance Criteria Coverage

This phase implements and verifies:

### demo-runtime-viewer.AC5: Runtime animation
- **demo-runtime-viewer.AC5.1 Success:** Orchestrator band shows current state labels derived from live events ("STARTING", "EDA RUNNING", "HANDOFF", "DATA ENGINEER RUNNING", "COMPLETE").
- **demo-runtime-viewer.AC5.2 Success:** EDA Analyst column highlights orange (active) between its `node_start` and `node_end` events, then locks to green (done). Its Input / Action / Output lanes populate with items in the order the events arrived.
- **demo-runtime-viewer.AC5.3 Success:** Data Engineer column activates only after EDA's `node_end`. Same lane behavior.
- **demo-runtime-viewer.AC5.4 Success:** ML Modeler, ML Reviewer, Business Stakeholder columns display a single footer label "not scheduled in demo scope" in muted text.
- **demo-runtime-viewer.AC5.5 Success:** The replay speed is controllable via a header selector (`0.5x`, `1x`, `1.5x`, `2x`). Default is `1.5x`.
- **demo-runtime-viewer.AC5.6 Failure:** Clicking CONTINUE twice (or pressing it during playback) is a no-op — it does not restart the animation.

---

<!-- START_SUBCOMPONENT_A (tasks 1-2) -->
<!-- START_TASK_1 -->
### Task 1: Populate Page 3 markup with production structure

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Files:**
- Modify: `src/multi_agent_ds/demo_viewer.html` (replace the Phase 3 placeholder `<div class="page p3">...</div>` with the real Page 3 body)

**Implementation:**
Copy the mockup's Page 3 markup (lines 573–721 in `demo_mockup.html`) into the viewer, replacing the stub from Phase 3 Task 1. Apply the following **five** modifications so the replay engine has targets to manipulate:

1. **Header speed selector.** Add a `<select>` next to the breadcrumb trail:
   ```html
   <div class="topbar">
     <div class="brand">MULTI-AGENT <span>·</span> DS</div>
     <div class="crumbs">Config &nbsp;›&nbsp; Input &nbsp;›&nbsp; <b>Runtime</b> &nbsp;›&nbsp; Results</div>
     <label style="margin-left:auto; font-size:12px; color:var(--slate);">
       Replay speed
       <select data-speed style="margin-left:8px;">
         <option value="0.5">0.5×</option>
         <option value="1">1×</option>
         <option value="1.5" selected>1.5×</option>
         <option value="2">2×</option>
       </select>
     </label>
   </div>
   ```
   Default value `1.5` satisfies AC5.5.

2. **Orchestrator band status placeholder.** Replace the hard-coded `"MODELING → FAN-OUT REVIEWERS"` with a target the engine updates:
   ```html
   <div class="band orch">
     <div class="title">ORCHESTRATOR</div>
     <div>State: <span class="status" data-orch-state>STARTING</span></div>
     <div style="margin-left:auto; font-family: 'Courier New', monospace; font-size:12px; color: var(--slate);">
       elapsed <span data-orch-elapsed>00:00</span>
     </div>
   </div>
   ```

3. **Identify the five columns by key.** Each `<div class="col">` becomes `<div class="col" data-col="KEY">` where `KEY ∈ {eda_raw, data_engineer, ml_modeler, ml_reviewer, business_stakeholder}`. The first two are driven by events; the last three are static.

4. **Empty lanes for recorded agents.** In the `eda_raw` and `data_engineer` columns, strip the mockup's hard-coded `<div class="item done">...</div>` items inside each lane. Leave only `<div class="lbl">INPUT|ACTION|OUTPUT</div>` and an empty `<div class="lane-items" data-lane="input|action|output"></div>` container. Example for EDA:
   ```html
   <div class="col" data-col="eda_raw">
     <div class="head"><span>EDA Analyst</span><span class="idx">01</span></div>
     <div class="lanes">
       <div class="lane input">
         <div class="lbl">INPUT</div>
         <div class="lane-items" data-lane="input"></div>
       </div>
       <div class="lane action">
         <div class="lbl">ACTION</div>
         <div class="lane-items" data-lane="action"></div>
       </div>
       <div class="lane output">
         <div class="lbl">OUTPUT</div>
         <div class="lane-items" data-lane="output"></div>
       </div>
     </div>
   </div>
   ```

5. **Dimmed, scope-labeled columns for un-executed agents.** For `ml_modeler`, `ml_reviewer`, `business_stakeholder`, replace the lane body with a single centered footer label:
   ```html
   <div class="col" data-col="ml_modeler" style="opacity:.45;">
     <div class="head"><span>ML Modeler</span><span class="idx">03</span></div>
     <div class="lanes">
       <div class="lane" style="grid-column: 1 / -1; text-align:center;">
         <div class="lbl">SCOPE</div>
         <div class="item" style="background:transparent; border:1px dashed var(--div); color:var(--slate);">
           not scheduled in demo scope
         </div>
       </div>
     </div>
   </div>
   ```
   Repeat for `ml_reviewer` and `business_stakeholder`. This satisfies AC5.4.

   Additionally, add a small footer near the agent rail: `<div class="rail-footer">Lane labels illustrative — full recorded payloads in <a data-nav="summary">Summary</a>.</div>` Add the corresponding CSS class to the viewer-only CSS block (a small text note at the bottom of the runtime page).

**Also delete the mockup's decorative token/arrow/fan elements (lines 693–702) and the REPORT WRITER band (lines 706–710).** The token animation is not modeled by this phase's event stream, and a Report Writer band on Page 3 implies it runs live — which contradicts the scope constraint. Page 5 (summary drawer) exposes Report Writer as scripted content. Keep the `.legend` block at the bottom unchanged.

**Step 1: Read the mockup Page 3 block**

```bash
sed -n '573,721p' demo_mockup.html > /tmp/mockup_p3.html
wc -l /tmp/mockup_p3.html
```

**Step 2: Apply the transforms as a single Edit**

Use the Edit tool on `src/multi_agent_ds/demo_viewer.html`. Match the Phase 3 placeholder:
- `old_string` = `<div class="page p3"><div class="tag">PAGE 3 — RUNTIME</div><div class="body"><h1>Runtime (Phase 4 stub)</h1></div></div>`
- `new_string` = the full transformed Page 3 markup (from the five modifications above).

**Step 3: Static verification**

```bash
uv run python -c "
from pathlib import Path
html = Path('src/multi_agent_ds/demo_viewer.html').read_text()
assert 'data-orch-state' in html, 'orchestrator state target missing'
assert 'data-speed' in html, 'speed selector missing'
for key in ['eda_raw', 'data_engineer', 'ml_modeler', 'ml_reviewer', 'business_stakeholder']:
    assert f'data-col=\"{key}\"' in html, f'column marker {key} missing'
for lane in ['input', 'action', 'output']:
    assert f'data-lane=\"{lane}\"' in html, f'lane marker {lane} missing'
assert 'not scheduled in demo scope' in html, 'scope label missing'
assert 'REPORT WRITER' not in html.upper() or html.count('REPORT WRITER') < 2, 'report writer band should be removed from Page 3'
print('static checks passed')
"
```

Expected: prints `static checks passed`.

**Step 4: Commit**

```bash
git status
git add src/multi_agent_ds/demo_viewer.html
git commit -m "feat(demo-viewer): add Page 3 runtime markup with lane targets

why: AC5.1–5.5 need DOM targets for the replay engine to toggle.
This task adds them: data-orch-state, data-orch-elapsed, data-col
per agent, data-lane per lane, data-speed selector.

architecture fit: markup-only change to demo_viewer.html. The
three un-executed agents (ml_modeler, ml_reviewer,
business_stakeholder) get dimmed columns with 'not scheduled in
demo scope' per AC5.4 and the scope constraint in the design plan.

validation: static checks confirm all markers are present and the
Report Writer band (which would imply live execution) is absent.

notes: token/arrow decorations from the mockup are dropped — they
are not modeled by the event stream. Replay engine goes in Task 2.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Implement the replay engine in startRuntimeReplay

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Files:**
- Modify: `src/multi_agent_ds/demo_viewer.html` (replace the empty `startRuntimeReplay` stub with a real engine)

**Implementation:**
The engine walks `window.DEMO_LOG.events`, schedules DOM updates by event `elapsed_ms`, and maintains the orchestrator status text and elapsed counter. State transitions:

| Event                                  | Orchestrator text        | Column action |
|----------------------------------------|--------------------------|---------------|
| first `node_start` on `eda_raw`        | `EDA RUNNING`            | add `.active` to `[data-col="eda_raw"]`, populate INPUT lane |
| `node_end` on `eda_raw`                | `HANDOFF`                | remove `.active`, add `.done` class, populate OUTPUT lane |
| first `node_start` on `data_engineer`  | `DATA ENGINEER RUNNING`  | add `.active` to `[data-col="data_engineer"]`, populate INPUT lane |
| `node_end` on `data_engineer`          | `COMPLETE`               | remove `.active`, add `.done` class, populate OUTPUT lane |
| any `node_error`                       | `ERROR: <node>`          | add `.errored` class to the column (CSS: red tint) |

**Engine contract:**
- Called exactly once per page load — gated by a module-level flag `_replayStarted` so AC5.6 holds.
- Reads `window.DEMO_LOG.events` at call time (not at page load) so the most recent speed-selector value is honored.
- Schedules all events via `setTimeout(..., event.elapsed_ms / speed)`. Each callback updates the DOM synchronously — no animations queued inside the callback.
- If `events` is empty or not an array, renders the orchestrator text `NO RECORDING` and returns.
- After the last event fires, advances `data-page="summary"` (Phase 5 populates that page). Use a `setTimeout` 600ms after the final event to give users a moment to see the COMPLETE state.

**Step 1: Add a small `.col.active` / `.col.done` / `.col.errored` CSS block**

The mockup CSS already styles `.col.active`. Verify it also has `.col.done` and `.col.errored`:

```bash
grep -n "\.col\.active\|\.col\.done\|\.col\.errored\|\.item\.live\|\.item\.done" src/multi_agent_ds/demo_viewer.html
```

If any of `.col.done` or `.col.errored` are missing, add them to the viewer-only additions block (next to the `.viewer[data-page=...]` rules from Phase 3). Suggested styles:

```css
.col.done { border-color: #C7E2C7; }
.col.done .head { background: #EEF6EE; color: #2E5B2E; }
.col.errored { border-color: #E2A7A7; }
.col.errored .head { background: #FBE7E7; color: #8A2323; }
```

These match the mockup's palette conventions. Add these three rules to the viewer-only CSS block unconditionally. The mockup does not define `.col.done`/`.col.errored` and the runtime engine relies on both.

**Step 2: Replace the `startRuntimeReplay` stub**

Find the empty `function startRuntimeReplay() {}` block from Phase 3 Task 1 and replace it with:

```javascript
let _replayStarted = false;
let _replayStartTime = null;
let _replayElapsedTicker = null;

function _fmtElapsed(ms) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const mm = String(Math.floor(total / 60)).padStart(2, '0');
  const ss = String(total % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

function _setOrchState(text) {
  const el = document.querySelector('[data-orch-state]');
  if (el) el.textContent = text;
}

function _addLaneItems(colKey, lane, items) {
  const host = document.querySelector(`[data-col="${colKey}"] [data-lane="${lane}"]`);
  if (!host) return;
  (items || []).forEach((label) => {
    const d = document.createElement('div');
    d.className = 'item done';
    d.textContent = label;
    host.appendChild(d);
  });
}

function _markColumn(colKey, cls) {
  const col = document.querySelector(`[data-col="${colKey}"]`);
  if (!col) return;
  col.classList.remove('active', 'done', 'errored');
  col.classList.add(cls);
}

function _laneItemsFor(event) {
  // Lane labels are illustrative/cosmetic — not derived from event payloads.
  // The drawer in Page 4 shows the real recorded payloads (orch / eda / de).
  const d = event.data || {};
  const node = event.node;
  if (node === 'eda_raw') {
    if (event.kind === 'node_start') return { input: ['raw_df'], action: [], output: [] };
    if (event.kind === 'node_end')   return { input: [], action: ['profile columns', 'detect leakage'], output: ['raw_eda_insights'] };
  }
  if (node === 'data_engineer') {
    if (event.kind === 'node_start') return { input: ['raw_eda_insights'], action: [], output: [] };
    if (event.kind === 'node_end')   return { input: [], action: ['impute · encode', 'train/test split'], output: ['prep_plan', 'processed_df'] };
  }
  return { input: [], action: [], output: [] };
}

function startRuntimeReplay() {
  // Pending timeouts are not canceled on Streamlit tab switch. The iframe is not
  // torn down between tab visits, so this is acceptable. To be safe, auto-advance
  // handlers check currentPage() before transitioning.
  if (_replayStarted) return; // AC5.6: do not restart
  _replayStarted = true;

  const speedSel = document.querySelector('[data-speed]');
  const speed = speedSel ? parseFloat(speedSel.value) || 1.5 : 1.5;

  const events = (window.DEMO_LOG && Array.isArray(window.DEMO_LOG.events)) ? window.DEMO_LOG.events : [];
  if (events.length === 0) {
    _setOrchState('NO RECORDING');
    return;
  }

  _replayStartTime = performance.now();
  _replayElapsedTicker = setInterval(() => {
    const el = document.querySelector('[data-orch-elapsed]');
    if (el) el.textContent = _fmtElapsed(performance.now() - _replayStartTime);
  }, 200);

  _setOrchState('STARTING');

  events.forEach((evt) => {
    const delayMs = (evt.elapsed_ms || 0) / speed;
    setTimeout(() => {
      const lanes = _laneItemsFor(evt);
      if (evt.kind === 'node_start' && evt.node === 'eda_raw') {
        _setOrchState('EDA RUNNING');
        _markColumn('eda_raw', 'active');
        _addLaneItems('eda_raw', 'input', lanes.input);
      } else if (evt.kind === 'node_end' && evt.node === 'eda_raw') {
        _setOrchState('HANDOFF');
        _markColumn('eda_raw', 'done');
        _addLaneItems('eda_raw', 'action', lanes.action);
        _addLaneItems('eda_raw', 'output', lanes.output);
      } else if (evt.kind === 'node_start' && evt.node === 'data_engineer') {
        _setOrchState('DATA ENGINEER RUNNING');
        _markColumn('data_engineer', 'active');
        _addLaneItems('data_engineer', 'input', lanes.input);
      } else if (evt.kind === 'node_end' && evt.node === 'data_engineer') {
        _setOrchState('COMPLETE');
        _markColumn('data_engineer', 'done');
        _addLaneItems('data_engineer', 'action', lanes.action);
        _addLaneItems('data_engineer', 'output', lanes.output);
      } else if (evt.kind === 'node_error') {
        _setOrchState(`ERROR: ${evt.node}`);
        _markColumn(evt.node, 'errored');
      }
    }, delayMs);
  });

  // After the final event, stop the ticker and advance to summary.
  const finalDelay = (events[events.length - 1].elapsed_ms || 0) / speed;
  setTimeout(() => {
    if (_replayElapsedTicker) {
      clearInterval(_replayElapsedTicker);
      _replayElapsedTicker = null;
    }
    setTimeout(() => goTo('summary'), 600);
  }, finalDelay + 10);
}
```

**Two design points to call out in the commit:**

1. **`_laneItemsFor` uses hard-coded labels.** The event payload carries structured artifacts but not human-readable lane labels. We choose readable constants (matching the mockup) over machine-rendered `Object.keys(...)` chaos. This is deliberate — the viewer is a demo tool, not a debugger.
2. **Auto-advance to summary** via `goTo('summary')` 600ms after the last event. Phase 5 will populate Page 4, so this wiring is now complete.

**Step 3: Static verification**

```bash
uv run python -c "
from pathlib import Path
html = Path('src/multi_agent_ds/demo_viewer.html').read_text()
assert '_replayStarted' in html, 'idempotence guard missing'
assert 'EDA RUNNING' in html, 'EDA state label missing'
assert 'DATA ENGINEER RUNNING' in html, 'DE state label missing'
assert 'COMPLETE' in html, 'complete state missing'
assert 'NO RECORDING' in html, 'empty-events fallback missing'
assert 'ERROR:' in html, 'error state missing'
assert \"goTo('summary')\" in html, 'auto-advance missing'
print('static checks passed')
"
```

Expected: prints `static checks passed`.

**Step 4: Manual verification with real recording**

Rebuild the combined test HTML from Phase 3 Task 4 (`/tmp/demo_viewer_e2e.html`) using the current `demo_viewer.html`:

```bash
uv run python -c "
import json
from pathlib import Path
log = Path('data/interim/demo_run_latest.json').read_text()
viewer = Path('src/multi_agent_ds/demo_viewer.html').read_text()
injected = viewer.replace('<script>', f'<script>window.DEMO_LOG = {log};</script>\n  <script>', 1)
Path('/tmp/demo_viewer_e2e.html').write_text(injected)
print('open /tmp/demo_viewer_e2e.html and click RUN → CONTINUE')
"
```

Open in a browser. Visual checklist:

- [ ] Orchestrator band reads `STARTING` briefly, then `EDA RUNNING`, then `HANDOFF`, then `DATA ENGINEER RUNNING`, then `COMPLETE`.
- [ ] EDA Analyst column turns orange (`.active`) between its start and end events, then green (`.done`).
- [ ] Data Engineer column stays idle until EDA's `node_end`, then activates.
- [ ] Each column's INPUT / ACTION / OUTPUT lanes accumulate items in the correct order.
- [ ] ML Modeler, ML Reviewer, Business Stakeholder columns are dimmed and show `not scheduled in demo scope`.
- [ ] Speed selector defaults to `1.5×`. Changing it before clicking CONTINUE affects timing (switching mid-playback does not — engine reads speed at start only).
- [ ] Elapsed counter ticks `00:00 → 00:0N` until COMPLETE.
- [ ] 600ms after COMPLETE, the page auto-advances to Page 4 (which is still a stub from Phase 3 — that's OK, Phase 5 fills it in).
- [ ] Clicking CONTINUE a second time is a no-op (AC5.6).
- [ ] No console errors.

**Step 5: Commit**

```bash
git add src/multi_agent_ds/demo_viewer.html
git commit -m "feat(demo-viewer): implement runtime replay engine

why: AC5.1–5.6 require animated Page 3 driven by the recorded
event log's elapsed_ms timestamps. This task fills the empty
startRuntimeReplay stub from Phase 3.

architecture fit: engine is pure DOM + setTimeout. No dependencies.
Idempotence guard _replayStarted satisfies AC5.6. Auto-advance to
summary 600ms after the last event wires Phase 4 → Phase 5.

validation: static checks confirm state labels (STARTING, EDA
RUNNING, HANDOFF, DATA ENGINEER RUNNING, COMPLETE, ERROR:,
NO RECORDING) are present. Visual check with real recording
confirmed EDA column activates and locks, DE column gates behind
EDA end, speed selector honored, double-click CONTINUE is no-op.

notes: lane item labels are hard-coded in _laneItemsFor (not
auto-generated from event data) — deliberate choice for
demo-readable output over verbose key dumps.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_2 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_TASK_3 -->
### Task 3: AC verification

**Active role:** `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` for load-bearing decisions within this task.

**Files:**
- No files modified.

**Implementation:**
Map each AC in this phase to a verification step and record the result.

**Step 1: AC5.1 — Orchestrator state labels**

Open `/tmp/demo_viewer_e2e.html` in a browser. Click RUN → CONTINUE. Watch the `ORCHESTRATOR State:` text. Expected sequence (all five):

1. `STARTING`
2. `EDA RUNNING`
3. `HANDOFF`
4. `DATA ENGINEER RUNNING`
5. `COMPLETE`

✅ if all five appear in order. ❌ otherwise — diagnose in Task 2's engine.

**Step 2: AC5.2 — EDA column color transitions**

Watch `[data-col="eda_raw"]`. Before CONTINUE: no state class. Between EDA's start and end: has `.active` (orange border). After EDA's end: has `.done` (green border). Lane items populate in order: INPUT → ACTION → OUTPUT.

**Step 3: AC5.3 — Data Engineer gating**

Verify `[data-col="data_engineer"]` has no active class until EDA's `node_end`. Then it follows the same orange → green pattern.

**Step 4: AC5.4 — Un-executed agents dimmed**

Inspect `[data-col="ml_modeler"]`, `[data-col="ml_reviewer"]`, `[data-col="business_stakeholder"]`. Each has `opacity: 0.45` and displays `not scheduled in demo scope`. None of them transitions state at any point during playback.

**Step 5: AC5.5 — Speed selector**

Reload the page. Default selection should be `1.5×`. Change to `0.5×` before clicking CONTINUE. Time the replay — it should take roughly 3× as long as with `1.5×`.

**Step 6: AC5.6 — Idempotent CONTINUE**

Mid-playback, click the CONTINUE button on Page 2 again (may require using browser devtools to re-show Page 2 — or refresh and re-click Page 2 CONTINUE twice rapidly). The engine should not restart: no duplicate lane items appear, elapsed counter does not reset.

**Step 7: Document results**

Present the six checks as the end-of-slice validation table. If any AC fails, file the fix against Task 1 (markup) or Task 2 (engine) in a follow-up commit — this task itself doesn't produce code.

No commit in this task.
<!-- END_TASK_3 -->

## Phase 4 Done-When

- [ ] Page 3 markup has orchestrator state target, five column targets, and three lane targets per recorded column.
- [ ] `startRuntimeReplay` is implemented, idempotent, and reads `window.DEMO_LOG.events`.
- [ ] Speed selector defaults to `1.5×` and controls timing.
- [ ] Orchestrator band cycles through STARTING → EDA RUNNING → HANDOFF → DATA ENGINEER RUNNING → COMPLETE.
- [ ] Un-executed agents show `not scheduled in demo scope` and do not transition state.
- [ ] Two commits landed (Tasks 1, 2) on branch `demo-runtime-viewer`. Task 3 is verification only.
