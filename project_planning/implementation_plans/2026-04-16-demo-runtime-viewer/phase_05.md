# Demo Runtime Viewer Implementation Plan — Phase 5

**Goal:** Port the mockup's Page 4 into `demo_viewer.html` — the processed-data preview, the four delta cards, the seven-card agent rail, and the click-to-slide drawer. Recorded agents (Orchestrator, EDA Analyst, Data Engineer) populate from `window.DEMO_LOG.artifacts`; the other four are explicitly scripted with a visible `SCRIPTED` badge.

**Architecture:** All markup and styles come from `demo_mockup.html` lines 724–1128 verbatim. Three modifications: (1) processed df + delta cards read from the event log, (2) recorded agent panes (`orch`, `eda`, `de`) render dynamically from artifacts, (3) scripted panes (`mlm`, `mlr`, `biz`, `rep`) render from a module-level `DEMO_CANNED` constant and carry a `SCRIPTED — not executed in this demo run` header badge. Existing slider mechanics (`.p4-slider.open-*` class → `translateX(-960px)`) remain unchanged.

**Tech Stack:** Vanilla JS (ES2017+). No dependencies.

**Scope:** Phase 5 of 7 from `2026-04-16-demo-runtime-viewer.md`.

**Codebase verified:** 2026-04-16. Phase 3 left a `<div class="page p4"><div class="tag">PAGE 4 — SUMMARY</div><div class="body"><h1>Summary (Phase 5 stub)</h1></div></div>` placeholder. Phase 4 added an auto-advance `goTo('summary')` call that expects Page 4 to be populated when it fires. The mockup's `openAgent(which)` / `closeAgent()` helpers and the `AGENT_LABELS` / `ALL_CLASSES` constants (mockup lines 1101–1123) are the exact contract the rail `onclick` attrs use. `.detail-pane.eda`, `.detail-pane.de`, `.detail-pane.orch`, `.detail-pane.mlm`, `.detail-pane.mlr`, `.detail-pane.biz`, `.detail-pane.rep` are all present in the mockup CSS; reuse them.

---

## Acceptance Criteria Coverage

This phase implements and verifies:

### demo-runtime-viewer.AC6: Output & Summary drawer
- **demo-runtime-viewer.AC6.1 Success:** Page 4 shows `df.head(10)` of the processed dataframe from `artifacts.processed_df_head` plus the four delta cards.
- **demo-runtime-viewer.AC6.2 Success:** The seven-card agent rail matches the mockup: Orchestrator, EDA Analyst, Data Engineer, ML Modeler, ML Reviewer, Business Stakeholder, Report Writer.
- **demo-runtime-viewer.AC6.3 Success:** Clicking any card translates the slider by `-960px` over 520ms and displays only that agent's pane.
- **demo-runtime-viewer.AC6.4 Success:** Orchestrator, EDA Analyst, and Data Engineer panes populate from recorded JSON.
- **demo-runtime-viewer.AC6.5 Success:** ML Modeler, ML Reviewer, Business Stakeholder, Report Writer panes display a "SCRIPTED — not executed in this demo run" header badge and render canned content from a static `DEMO_CANNED` block in the HTML.
- **demo-runtime-viewer.AC6.6 Success:** Clicking BACK closes the drawer. Clicking a different card while one is open swaps panes without an intermediate close.

---

<!-- START_SUBCOMPONENT_A (tasks 1-2) -->
<!-- START_TASK_1 -->
### Task 1: Port Page 4 markup (main panel + agent rail + drawer shell)

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Files:**
- Modify: `src/multi_agent_ds/demo_viewer.html` (replace the Phase 3 Page 4 stub with the mockup's full Page 4 body)

**Implementation:**
Copy mockup lines 724–1098 (the entire `<div class="page p4">` through its closing `</div>`) plus the `openAgent` / `closeAgent` helpers and the `AGENT_LABELS` / `ALL_CLASSES` constants from lines 1101–1123. Integrate the helpers into the viewer's existing `<script>` block — do not introduce a second script tag.

**Four markup modifications** before pasting:

1. **Processed df table → renderable target.** Replace `<thead>...</thead><tbody>...</tbody>` (hard-coded rows) with:
   ```html
   <table>
     <thead data-out-head></thead>
     <tbody data-out-body></tbody>
   </table>
   ```
   Replace the footer caption `data/processed/demo_run_0417A.parquet · 500,000 × 24` with:
   ```html
   <div style="font-size:11px; color: var(--slate); margin-top:6px; font-family:'Courier New', monospace;"
        data-out-caption>—</div>
   ```

2. **Delta cards → data-bound.** Replace the four `.delta` divs' numeric/label contents with template holes:
   ```html
   <div class="delta-row">
     <div class="delta good"><div class="num" data-delta="roc_auc">n/a</div><div class="lbl">ROC-AUC (best trial)</div></div>
     <div class="delta"><div class="num" data-delta="feature_delta">n/a</div><div class="lbl">features after encoding</div></div>
     <div class="delta"><div class="num" data-delta="missing_delta">n/a</div><div class="lbl">missing cells</div></div>
     <div class="delta"><div class="num" data-delta="runtime">n/a</div><div class="lbl">end-to-end runtime</div></div>
   </div>
   ```
   The literal string `n/a` is the default for unavailable metrics per the design plan.

3. **Rail card `role` subtitles → data-bound.** Keep the seven `<div class="agent-card" onclick="openAgent(...)">` blocks verbatim, but wrap each `.role` text in a `data-role` target so the renderer can override it with real counts for recorded agents. Example for EDA:
   ```html
   <div class="agent-card" onclick="openAgent('eda')">
     <div class="avatar">EA</div>
     <div class="meta">
       <div class="name">EDA Analyst</div>
       <div class="role" data-role="eda">loading…</div>
     </div>
     <div class="chev">›</div>
   </div>
   ```
   Do this for all seven cards — the renderer in Task 2 will decide whether each line shows real data or the canned subtitle.

4. **Drawer panes → split into dynamic vs scripted.** Keep the seven `<div class="detail-pane ...">` outer shells but:
   - For `.eda`, `.de`, `.orch`: replace the entire inner body with a single placeholder `<div data-pane-body="eda|de|orch">rendering…</div>`. Task 2 fills them.
   - For `.mlm`, `.mlr`, `.biz`, `.rep`: leave the mockup's canned HTML intact, but prepend a badge row at the top of each pane:
     ```html
     <div class="scripted-badge" style="grid-column: 1 / -1; display:flex; gap:8px; align-items:center; padding:8px 12px; background:rgba(255,182,128,.12); border:1px solid #FFB680; border-radius:8px; color:#FFB680; font-size:11px; letter-spacing:.08em; text-transform:uppercase;">
       <span>●</span> SCRIPTED — not executed in this demo run
     </div>
     ```
     This satisfies AC6.5 and is honest about what the audience is looking at.

**Also fix the detail-pane visibility rule.** The mockup's rule `.p4-slider.open-eda .detail-pane.eda { display: grid; }` already exists, but each `.detail-pane` defaults to `display: none` — confirm this by grepping the viewer. If no display rule exists yet, add:
```css
.p4-detail .detail-pane { display: none; }
.p4-slider.open-orch .detail-pane.orch,
.p4-slider.open-eda  .detail-pane.eda,
.p4-slider.open-de   .detail-pane.de,
.p4-slider.open-mlm  .detail-pane.mlm,
.p4-slider.open-mlr  .detail-pane.mlr,
.p4-slider.open-biz  .detail-pane.biz,
.p4-slider.open-rep  .detail-pane.rep { display: grid; }
```
These should already exist in the copied CSS (mockup line ~374); skip if present.

**Remove the mockup's stamp element** (`<div class="stamp">RUN <b>#0417-A</b></div>`, mockup line 730) — the recorded run has no hard-coded ID. Or replace with a data-bound target `<div class="stamp" data-run-stamp>RUN —</div>` that the renderer fills from `window.DEMO_LOG.recorded_at`. Use the second option; it's more demo-honest.

**Step 1: Extract the markup block**

```bash
sed -n '724,1098p' demo_mockup.html > /tmp/mockup_p4.html
sed -n '1101,1124p' demo_mockup.html > /tmp/mockup_p4_js.html
wc -l /tmp/mockup_p4.html /tmp/mockup_p4_js.html
```

**Step 2: Apply the transforms**

Replace the Page 4 stub in `src/multi_agent_ds/demo_viewer.html` with the transformed markup (per the four modifications above). In the existing `<script>` block, add the `AGENT_LABELS`, `ALL_CLASSES`, `openAgent`, and `closeAgent` helpers from `/tmp/mockup_p4_js.html`, placed near the top of the script (they don't depend on any later definitions).

**Step 3: Static verification**

```bash
uv run python -c "
from pathlib import Path
html = Path('src/multi_agent_ds/demo_viewer.html').read_text()
for agent in ['orch', 'eda', 'de', 'mlm', 'mlr', 'biz', 'rep']:
    assert f\"onclick=\\\"openAgent('{agent}')\\\"\" in html, f'rail card for {agent} missing'
for pane in ['eda', 'de', 'orch']:
    assert f'data-pane-body=\"{pane}\"' in html, f'dynamic pane body for {pane} missing'
assert 'data-out-head' in html and 'data-out-body' in html, 'output table targets missing'
for key in ['roc_auc', 'feature_delta', 'missing_delta', 'runtime']:
    assert f'data-delta=\"{key}\"' in html, f'delta target {key} missing'
for agent in ['eda', 'de', 'orch', 'mlm', 'mlr', 'biz', 'rep']:
    assert f'data-role=\"{agent}\"' in html, f'rail subtitle target for {agent} missing'
assert 'SCRIPTED' in html and 'not executed in this demo run' in html, 'SCRIPTED badge missing'
assert 'function openAgent' in html and 'function closeAgent' in html, 'drawer helpers missing'
print('static checks passed')
"
```

Expected: prints `static checks passed`.

**Step 4: Commit**

```bash
git status
git add src/multi_agent_ds/demo_viewer.html
git commit -m "feat(demo-viewer): add Page 4 summary layout and drawer shell

why: AC6.2 requires the seven-card agent rail; AC6.3 requires the
slider mechanics; AC6.5 requires SCRIPTED badges on un-executed
agents. This task ports the mockup's Page 4 verbatim with the
four template modifications needed for data binding in Task 2.

architecture fit: markup + openAgent/closeAgent helpers only. All
slider CSS is reused unchanged from the mockup — no new layout
primitives introduced.

validation: static checks confirm all seven rail cards, three
dynamic pane bodies, four delta targets, seven role subtitle
targets, and the SCRIPTED badge are present.

notes: run stamp and processed df table are data-bound for real
values in Task 2. ml_modeler/ml_reviewer/business_stakeholder/
report_writer panes keep the mockup's canned HTML but carry a
visible SCRIPTED badge per design plan scope constraint.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Render real data into delta cards, processed table, rail subtitles, and recorded-agent panes

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Files:**
- Modify: `src/multi_agent_ds/demo_viewer.html` (add `renderSummary()` and helper renderers)

**Implementation:**
`renderSummary()` is called at page load (like `renderConfig` and `renderInputPreview`). It populates everything on Page 4 that depends on recorded data:

1. Run stamp (`[data-run-stamp]`) from `recorded_at`
2. Delta cards from `artifacts`
3. Processed-df table from `artifacts.processed_df_head` and stats
4. Rail subtitles for each agent
5. Three dynamic drawer panes (orch, eda, de)

Scripted panes do not need rendering — their HTML is already in the DOM from Task 1.

**Expected `window.DEMO_LOG.artifacts` shape** (from Phase 2 recorder):

```jsonc
{
  "raw_eda_insights": { ... },            // EDA agent output
  "prep_plan":        { ... },            // Data Engineer output
  "processed_df_head": [ { col: val, ... }, ... ],  // up to 10 rows
  "input_df_head":     [ ... ],
  "input_df_stats":    { rows, cols, target, positive_rate, numeric_count, categorical_count, missing_pct },
  "processed_df_stats": { rows, cols, path, missing_pct_after }  // optional — renderer treats missing keys as n/a
}
```

**Design-plan caveat (AC6.1 interpretation):** ROC-AUC is produced by `ml_modeler`, which does not run in this demo. Per the design plan: "any unavailable metric shows `n/a`". The delta card renderer reads `artifacts.processed_df_stats.best_roc_auc` if present (it won't be in this demo) and falls back to `n/a`. Don't stub a plausible number — honesty.

**Step 1: Add `DEMO_CANNED` constant**

At the top of the `<script>` block, add a small catalog of subtitle strings for rail cards. Canned panes already live in HTML; `DEMO_CANNED` only holds rail subtitle copy:

```javascript
const DEMO_CANNED = {
  rail_subtitles: {
    mlm: '5 trials · best AUC 0.847 (scripted)',
    mlr: 'verdict: approve · 2 flags (scripted)',
    biz: 'verdict: approve · interpretable (scripted)',
    rep: 'experiment_report.md · 4 sections (scripted)',
  },
};
```

The `(scripted)` suffix on every un-executed agent's rail subtitle makes the demo honest at a glance, before the user even clicks into the pane.

**Step 2: Add `renderSummary()` and helpers**

Insert after `renderInputPreview()`:

```javascript
function _runStampText(log) {
  if (!log || !log.recorded_at) return 'RUN —';
  // recorded_at is ISO-8601; extract HHMM-X style from the time part for a demo-style stamp.
  const d = new Date(log.recorded_at);
  if (Number.isNaN(d.getTime())) return 'RUN —';
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mi = String(d.getUTCMinutes()).padStart(2, '0');
  return `RUN #${mm}${dd}-${hh}${mi}`;
}

function _fmtRuntime(ms) {
  if (ms == null) return 'n/a';
  const total = Math.floor(ms / 1000);
  const mm = String(Math.floor(total / 60)).padStart(2, '0');
  const ss = String(total % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

function renderSummary() {
  const log = window.DEMO_LOG || {};
  const artifacts = log.artifacts || {};
  const inputStats = artifacts.input_df_stats || {};
  const outStats   = artifacts.processed_df_stats || {};
  const outRows    = artifacts.processed_df_head || [];

  // --- Run stamp ---
  const stamp = document.querySelector('[data-run-stamp]');
  if (stamp) stamp.innerHTML = _runStampText(log).replace(/RUN (#.+)/, 'RUN <b>$1</b>');

  // --- Delta cards ---
  const setDelta = (key, text) => {
    const el = document.querySelector(`[data-delta="${key}"]`);
    if (el) el.textContent = text;
  };
  const toggleDeltaGood = (key, good) => {
    const card = document.querySelector(`[data-delta="${key}"]`).parentElement;
    if (card) card.classList.toggle('good', good);
  };
  // ROC-AUC is always 'n/a' in demo scope (ml_modeler does not run). Update both here
  // and the SCRIPTED badge logic if the recorder is ever extended to include ml_modeler output.
  setDelta('roc_auc', outStats.best_roc_auc != null ? outStats.best_roc_auc.toFixed(3) : 'n/a');
  toggleDeltaGood('roc_auc', outStats.best_roc_auc != null);
  const featuresPresent = inputStats.cols != null && outStats.cols != null;
  if (featuresPresent) {
    setDelta('feature_delta', `${inputStats.cols} → ${outStats.cols}`);
  } else {
    setDelta('feature_delta', 'n/a');
  }
  toggleDeltaGood('feature_delta', featuresPresent && outStats.cols !== inputStats.cols);
  const missingImproved = inputStats.missing_pct != null && outStats.missing_pct_after != null
    && outStats.missing_pct_after < inputStats.missing_pct;
  if (inputStats.missing_pct != null && outStats.missing_pct_after != null) {
    setDelta('missing_delta', `${fmtPct(inputStats.missing_pct)} → ${fmtPct(outStats.missing_pct_after)}`);
  } else if (inputStats.missing_pct != null) {
    setDelta('missing_delta', `${fmtPct(inputStats.missing_pct)} → n/a`);
  } else {
    setDelta('missing_delta', 'n/a');
  }
  toggleDeltaGood('missing_delta', missingImproved);
  setDelta('runtime', _fmtRuntime(log.duration_ms));
  toggleDeltaGood('runtime', log.duration_ms != null);

  // --- Processed df table ---
  const outHead = document.querySelector('[data-out-head]');
  const outBody = document.querySelector('[data-out-body]');
  const caption = document.querySelector('[data-out-caption]');
  if (outHead && outBody) {
    outHead.innerHTML = '';
    outBody.innerHTML = '';
    if (outRows.length === 0) {
      outBody.innerHTML = '<tr><td style="text-align:center;color:var(--slate);padding:16px;">(not recorded)</td></tr>';
    } else {
      const targetCol = inputStats.target;
      let cols = Object.keys(outRows[0]).slice(0, 11);
      if (targetCol && cols.includes(targetCol)) {
        cols = cols.filter((c) => c !== targetCol).concat([targetCol]);
      }
      const tr = document.createElement('tr');
      cols.forEach((col) => {
        const th = document.createElement('th');
        th.textContent = col;
        if (col === targetCol) { th.classList.add('target'); th.style.color = '#FFB680'; }
        tr.appendChild(th);
      });
      outHead.appendChild(tr);
      outRows.slice(0, 10).forEach((row) => {
        const rtr = document.createElement('tr');
        cols.forEach((col) => {
          const td = document.createElement('td');
          const v = row[col];
          td.textContent = (v == null) ? '—' : String(v);
          if (col === targetCol) td.classList.add('target');
          rtr.appendChild(td);
        });
        outBody.appendChild(rtr);
      });
    }
  }
  if (caption) {
    const path = outStats.path || 'data/interim/processed_df.parquet';
    const shape = (outStats.rows != null && outStats.cols != null)
      ? `${fmtNum(outStats.rows)} × ${outStats.cols}` : 'shape unknown';
    caption.textContent = `${path} · ${shape}`;
  }

  // --- Rail subtitles ---
  const setRole = (key, text) => {
    const el = document.querySelector(`[data-role="${key}"]`);
    if (el) el.textContent = text;
  };
  const eventCount = (Array.isArray(log.events) ? log.events.length : 0);
  const edaInsights = artifacts.raw_eda_insights || {};
  const edaBullets = Array.isArray(edaInsights.headline_findings) ? edaInsights.headline_findings.length
                   : Object.keys(edaInsights).length;
  const prepPlan = artifacts.prep_plan || {};
  const transformCount = Object.keys(prepPlan).length;
  setRole('orch', `routes state · ${eventCount} events`);
  setRole('eda', edaBullets > 0 ? `${edaBullets} insights · profiling, leakage` : 'recorded');
  setRole('de',  transformCount > 0 ? `${transformCount} transform groups · impute, encode` : 'recorded');
  setRole('mlm', DEMO_CANNED.rail_subtitles.mlm);
  setRole('mlr', DEMO_CANNED.rail_subtitles.mlr);
  setRole('biz', DEMO_CANNED.rail_subtitles.biz);
  setRole('rep', DEMO_CANNED.rail_subtitles.rep);

  // --- Recorded agent panes ---
  _renderOrchPane(log);
  _renderEdaPane(artifacts);
  _renderDePane(artifacts);
}

function _renderOrchPane(log) {
  const host = document.querySelector('[data-pane-body="orch"]');
  if (!host) return;
  const events = Array.isArray(log.events) ? log.events : [];
  const nodes = Array.from(new Set(events.map((e) => e.node))).filter(Boolean);
  const transitions = events.filter((e) => e.kind === 'node_start' || e.kind === 'node_end').length;
  host.innerHTML = `
    <div class="dcard" style="grid-column: 1 / -1;">
      <h5>ROUTING DECISIONS</h5>
      <ul>
        <li>Recorded path: <code>${nodes.join(' → ')}</code></li>
        <li>${transitions} node transitions observed</li>
        <li>Recorded at <code>${log.recorded_at || '—'}</code></li>
      </ul>
    </div>
    <div class="dcard">
      <h5>EVENT COUNTS</h5>
      <div class="stat-row">
        <div class="s"><div class="n">${events.length}</div><div class="l">total events</div></div>
        <div class="s"><div class="n">${transitions}</div><div class="l">node transitions</div></div>
      </div>
      <div class="stat-row" style="margin-top:8px;">
        <div class="s"><div class="n">${_fmtRuntime(log.duration_ms)}</div><div class="l">duration</div></div>
        <div class="s"><div class="n">${nodes.length}</div><div class="l">nodes</div></div>
      </div>
    </div>
  `;
}

function _renderEdaPane(artifacts) {
  const host = document.querySelector('[data-pane-body="eda"]');
  if (!host) return;
  const insights = artifacts.raw_eda_insights || {};
  const json = JSON.stringify(insights, null, 2);
  host.innerHTML = `
    <div class="dcard" style="grid-column: 1 / -1;">
      <h5>RAW INSIGHTS (handed to Data Engineer)</h5>
      <div class="code">${_escapeHtml(json) || '—'}</div>
    </div>
  `;
}

function _renderDePane(artifacts) {
  const host = document.querySelector('[data-pane-body="de"]');
  if (!host) return;
  const plan = artifacts.prep_plan || {};
  const json = JSON.stringify(plan, null, 2);
  host.innerHTML = `
    <div class="dcard" style="grid-column: 1 / -1;">
      <h5>PREP PLAN (handed to ML Modeler — scripted in this demo)</h5>
      <div class="code">${_escapeHtml(json) || '—'}</div>
    </div>
  `;
}

function _escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Initial render on load.
renderSummary();
```

**Design notes for the commit:**

1. **Recorded panes are minimal.** The mockup's rich `dcard` layouts for ML Modeler etc. are kept as-is (they are scripted). The recorded panes show the actual JSON — ugly but honest. For demo day this is the right tradeoff: real > pretty when the audience knows which is which.
2. **Rail subtitles for recorded agents** report event/insight/transform counts. If counts are missing, they fall back to `recorded`.
3. **`_escapeHtml`** is used everywhere JSON is interpolated, preventing XSS from any string field that might contain `<` or `&`.

**Step 3: Static verification**

```bash
uv run python -c "
from pathlib import Path
html = Path('src/multi_agent_ds/demo_viewer.html').read_text()
assert 'function renderSummary' in html, 'renderSummary missing'
assert 'function _renderOrchPane' in html, '_renderOrchPane missing'
assert 'function _renderEdaPane'  in html, '_renderEdaPane missing'
assert 'function _renderDePane'   in html, '_renderDePane missing'
assert 'function _escapeHtml'     in html, '_escapeHtml missing'
assert 'DEMO_CANNED'              in html, 'DEMO_CANNED missing'
assert \"'(scripted)'\" in html or '(scripted)' in html, 'scripted subtitle missing'
print('static checks passed')
"
```

Expected: prints `static checks passed`.

**Step 4: Manual verification with real recording**

Rebuild `/tmp/demo_viewer_e2e.html` (same command as Phase 4 Task 2 Step 4):

```bash
uv run python -c "
import json
from pathlib import Path
log = Path('data/interim/demo_run_latest.json').read_text()
viewer = Path('src/multi_agent_ds/demo_viewer.html').read_text()
injected = viewer.replace('<script>', f'<script>window.DEMO_LOG = {log};</script>\n  <script>', 1)
Path('/tmp/demo_viewer_e2e.html').write_text(injected)
print('open /tmp/demo_viewer_e2e.html and click through RUN → CONTINUE')
"
```

Click through the full flow. Visual checklist on Page 4:

- [ ] Run stamp reads `RUN #MMDD-HHMM` based on the JSON's `recorded_at`.
- [ ] Delta card 1 (ROC-AUC) reads `n/a`.
- [ ] Delta card 2 (features after encoding) shows `17 → N` if the recorder emitted `processed_df_stats.cols`, else `n/a`.
- [ ] Delta card 3 (missing cells) shows either `3.1% → X%` or `3.1% → n/a`.
- [ ] Delta card 4 (runtime) shows `MM:SS` from `duration_ms`.
- [ ] Processed df table renders up to 10 rows with the target column pinned last and highlighted.
- [ ] Caption under the table shows the real output path.
- [ ] Rail shows all seven cards. Recorded-agent subtitles show event/insight/transform counts. Scripted-agent subtitles carry `(scripted)` suffix.
- [ ] Clicking Orchestrator opens the orch pane with recorded transition counts.
- [ ] Clicking EDA Analyst opens the eda pane with the real JSON.
- [ ] Clicking Data Engineer opens the de pane with the real prep plan JSON.
- [ ] Clicking any of ML Modeler / ML Reviewer / Business Stakeholder / Report Writer shows the scripted pane with the `SCRIPTED — not executed in this demo run` badge at the top.
- [ ] BACK closes the drawer.
- [ ] Clicking a different card while one is open swaps panes with no intermediate close state (smooth slide).
- [ ] No console errors.

**Step 5: Commit**

```bash
git add src/multi_agent_ds/demo_viewer.html
git commit -m "feat(demo-viewer): render Page 4 recorded data + rail + drawer

why: AC6.1/6.2/6.4 require Page 4 to show the processed df, delta
cards, seven-card rail, and recorded agent panes populated from
window.DEMO_LOG.artifacts. This task fills all the data-bound
targets added in Task 1.

architecture fit: renderSummary is a pure DOM renderer; no new
libraries. _escapeHtml guards JSON interpolation. DEMO_CANNED only
holds rail subtitle copy — full scripted pane HTML lives in the
DOM from Task 1.

validation: static checks confirm renderSummary and three per-pane
renderers exist. Visual check with real recording confirmed delta
fallback to n/a for unavailable metrics (ROC-AUC in particular,
since ml_modeler does not run in this demo).

notes: recorded panes show raw JSON — honest over pretty. Scripted
agents' rail subtitles include '(scripted)' suffix for at-a-glance
honesty before drawer is opened.
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
Walk each AC and record pass/fail.

**Step 1: AC6.1 — Processed df + delta cards**

Open `/tmp/demo_viewer_e2e.html`, click RUN → CONTINUE → wait for auto-advance. Confirm:
- Processed table shows 10 rows from `artifacts.processed_df_head`.
- Four delta cards render (some may show `n/a` — acceptable).

**Step 2: AC6.2 — Seven-card rail**

Verify rail cards in order: Orchestrator (Crew), EDA Analyst, Data Engineer, ML Modeler, ML Reviewer, Business Stakeholder (Domain agents), Report Writer (Crew). Count = 7.

**Step 3: AC6.3 — Slide animation**

Click any card. Watch the `.p4-slider` element in devtools — expect `transform: translateX(-960px)` applied with a 520ms transition. Visually: the main panel slides left, the detail panel fills the viewport.

**Step 4: AC6.4 — Recorded panes**

Open Orchestrator → shows node transition counts from real events. Open EDA Analyst → shows real `raw_eda_insights` JSON. Open Data Engineer → shows real `prep_plan` JSON. None of these show placeholder text.

**Step 5: AC6.5 — Scripted panes with badge**

Open each of ML Modeler, ML Reviewer, Business Stakeholder, Report Writer. Each pane's first row is the `SCRIPTED — not executed in this demo run` badge with orange accent. The rest of the pane is the mockup's canned content.

**Step 6: AC6.6 — Close and swap**

With a drawer open, click BACK → slider returns to `translateX(0)`. Click a card, then click another card without BACK — the slider should re-point smoothly to the second pane without flickering through a closed state.

**Step 7: Document results**

Present six pass/fail results in the end-of-slice summary.

No commit in this task.
<!-- END_TASK_3 -->

## Phase 5 Done-When

- [ ] Page 4 markup contains processed-df table, four delta cards, seven-card rail, and seven drawer panes (three dynamic + four scripted with badges).
- [ ] `renderSummary()` populates all data-bound targets on page load.
- [ ] Opening any card transitions the slider smoothly; BACK closes it; swapping cards is glitch-free.
- [ ] Recorded panes show real artifacts; scripted panes show the canned mockup content with a visible `SCRIPTED` badge.
- [ ] Two commits landed (Tasks 1, 2). Task 3 is verification only.
