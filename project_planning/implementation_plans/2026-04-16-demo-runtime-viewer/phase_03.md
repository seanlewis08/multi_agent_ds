# Demo Runtime Viewer Implementation Plan — Phase 3

**Goal:** Port pages 1 and 2 of the validated mockup into a production `demo_viewer.html` that reads its values from `window.DEMO_LOG`, with functional RUN / CONTINUE navigation.

**Architecture:** Single self-contained HTML file. Copies CSS verbatim from `demo_mockup.html`. Navigation collapses the mockup's four stacked pages into one visible page at a time via a root `<div class="viewer" data-page="...">` class toggle. No build step, no frameworks, no external JS.

**Tech Stack:** Plain HTML5, CSS, vanilla JS (ES2017+). No dependencies.

**Scope:** Phase 3 of 7 from `2026-04-16-demo-runtime-viewer.md`.

**Codebase verified:** 2026-04-16. `demo_mockup.html` exists at repo root (1128 lines, ~48 KB) and validates visually. `src/multi_agent_ds/demo_viewer.html` does not yet exist. Page 1 layout spans mockup lines 460–514 (`<div class="page p1">`). Page 2 layout spans mockup lines 517–570 (`<div class="page p2">`). The mockup uses CSS classes `.book`, `.page`, `.p1`..`.p4` with all four pages stacked vertically for preview. The production viewer must display one page at a time. Phase 2 introduced the event log JSON shape (`window.DEMO_LOG = { config, artifacts: { input_df_head, input_df_stats, ... }, events: [...] }`).

---

## Acceptance Criteria Coverage

This phase implements and verifies:

### demo-runtime-viewer.AC3: Config screen
- **demo-runtime-viewer.AC3.1 Success:** Page 1 shows source path, target column, rows × cols, positive rate, scale, max_trials, cv_folds, timeout, algorithms, and review settings from `config/settings.yaml`.
- **demo-runtime-viewer.AC3.2 Success:** Clicking the RUN button transitions to the Input Preview screen.

### demo-runtime-viewer.AC4: Input Preview screen
- **demo-runtime-viewer.AC4.1 Success:** Page 2 shows `df.head(10)` of the raw parquet plus a pill-strip with row count, column count, target name, positive rate, numeric count, categorical count, and missing-cell percentage.
- **demo-runtime-viewer.AC4.2 Success:** Clicking CONTINUE transitions to the Runtime screen and starts the replay timer.

**Note:** The replay timer start is stubbed in this phase (a `startRuntimeReplay()` no-op function) and filled in by Phase 4. Phase 3 only needs the CONTINUE button to flip the root class and call the stub.

---

<!-- START_SUBCOMPONENT_A (tasks 1-2) -->
<!-- START_TASK_1 -->
### Task 1: Scaffold demo_viewer.html with copied CSS and empty page shells

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Files:**
- Create: `src/multi_agent_ds/demo_viewer.html`

**Implementation:**
The production viewer starts as a single file containing: doctype, `<head>` with the mockup's `<style>` block copied verbatim, a root `<div class="viewer" data-page="config">`, four empty page divs (`config`, `input`, `runtime`, `summary`), and a `<script>` block with a tiny navigation helper.

The mockup stacks all four pages vertically. The production viewer shows one page at a time via `[data-page="config"] .page.p1 { display: flex; }` style rules (all others `display: none`). This keeps the mockup's CSS untouched but hides non-active pages.

**Step 1: Read the mockup's `<style>` block**

```bash
sed -n '1,450p' demo_mockup.html > /tmp/mockup_head.html
head -20 /tmp/mockup_head.html
grep -n "^</style>" demo_mockup.html | head -1
```

Identify the exact line range of the style block. Mockup opens with `<style>` near line 14 and closes with `</style>` just before the `<body>` tag. Copy the entire block (unchanged) into the new file.

**Step 2: Create the scaffold**

Create `src/multi_agent_ds/demo_viewer.html` with this structure. Do not include any mockup page body yet — that is Tasks 2 and 3.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>multi_agent_ds — demo runtime</title>
  <style>
    /* ==== BEGIN COPIED FROM demo_mockup.html — DO NOT EDIT BY HAND ==== */
    /* paste the mockup's entire <style>...</style> contents here, verbatim */
    /* ==== END COPIED FROM demo_mockup.html ==== */

    /* ==== viewer-only additions (single-page navigation) ==== */
    html, body { margin: 0; padding: 0; background: var(--ink, #0F1219); }
    .viewer .page { display: none; }
    .viewer[data-page="config"]  .page.p1 { display: flex; }
    .viewer[data-page="input"]   .page.p2 { display: flex; }
    .viewer[data-page="runtime"] .page.p3 { display: flex; }
    .viewer[data-page="summary"] .page.p4 { display: flex; }
    .viewer .book { padding: 0; gap: 0; }
    /* override mockup's book padding so the iframe fills height=820 */
  </style>
</head>
<body>
  <div class="viewer" data-page="config">
    <div class="book">
      <!-- Page 1: Config — populated in Task 2 -->
      <!-- Page 2: Input Preview — populated in Task 3 -->
      <!-- Page 3: Runtime — placeholder, filled in Phase 4 -->
      <div class="page p3"><div class="tag">PAGE 3 — RUNTIME</div><div class="body"><h1>Runtime (Phase 4 stub)</h1></div></div>
      <!-- Page 4: Summary — placeholder, filled in Phase 5 -->
      <div class="page p4"><div class="tag">PAGE 4 — SUMMARY</div><div class="body"><h1>Summary (Phase 5 stub)</h1></div></div>
    </div>
  </div>

  <script>
    // DEMO_LOG is injected by Streamlit before this script runs.
    // For standalone file:// testing, fall back to an empty stub.
    window.DEMO_LOG = window.DEMO_LOG || { config: {}, artifacts: {}, events: [] };

    const viewer = document.querySelector('.viewer');

    function goTo(page) {
      if (!['config', 'input', 'runtime', 'summary'].includes(page)) return;
      viewer.setAttribute('data-page', page);
      if (page === 'runtime') startRuntimeReplay();
    }

    function startRuntimeReplay() {
      // Phase 4 fills this in. Phase 3 stub: no-op.
      // Do not remove this function — CONTINUE button relies on it.
    }

    // Bind navigation buttons (populated in Tasks 2 and 3 with data-goto attrs).
    document.addEventListener('click', (e) => {
      const target = e.target.closest('[data-goto]');
      if (!target) return;
      goTo(target.getAttribute('data-goto'));
    });
  </script>
</body>
</html>
```

Two design points to call out in the commit message:

1. **Navigation via root `data-page` attr + CSS visibility** — matches the design doc's "simple class toggles on a root `<div>`" and avoids JS-side DOM removal.
2. **`startRuntimeReplay()` defined but empty** — Phase 4 will implement it. CONTINUE button's `goTo('runtime')` call invokes it regardless, so wiring is done once here.

**Step 3: Paste the mockup's `<style>` contents verbatim**

Use a single edit to replace the `/* paste the mockup's entire <style>...</style> contents here, verbatim */` placeholder. Use the Bash tool to extract the exact range:

```bash
# Find the line numbers of <style> and </style> in the mockup
grep -n "^  <style>\|^</style>\|^<style>" demo_mockup.html
```

Then read that range via the Read tool with `offset` and `limit`, and paste the contents into the scaffold. Do not re-indent or reformat.

**Step 4: Verify no console errors**

```bash
# Open the file in a headless browser (Chromium or Playwright if installed)
# Or simply cat the file and sanity-check
wc -l src/multi_agent_ds/demo_viewer.html
grep -c "data-page=" src/multi_agent_ds/demo_viewer.html
```

Expected: `demo_viewer.html` exists, is at least several hundred lines (CSS dominates), `data-page=` appears at least twice (the root div + the CSS rules). No Python or runtime checks are applicable at this step — Task 2 will add visible content.

**Step 5: Commit**

```bash
git status
git diff --stat src/multi_agent_ds/demo_viewer.html
```

Confirm only the new file is staged.

```bash
git add src/multi_agent_ds/demo_viewer.html
git commit -m "feat(demo-viewer): scaffold demo_viewer.html with mockup CSS

why: demo_recorder now produces a JSON event log (Phase 2). The
viewer needs a skeleton that can be populated page-by-page in
subsequent tasks. Scaffold copies mockup CSS verbatim and adds a
single-page navigation layer via root data-page attribute.

architecture fit: viewer lives in src/multi_agent_ds/ per AC7.2.
Self-contained HTML; no framework dependency; no new paths beyond
the one already registered in PROJECT_TREE.md.

validation: file exists, CSS block is intact, data-page attr is
used to toggle visible page. Pages 1 and 2 are empty shells —
populated in Tasks 2 and 3.

notes: startRuntimeReplay() is an empty function here. Phase 4
will fill it in.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Populate Page 1 (Config) with template + render function

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Files:**
- Modify: `src/multi_agent_ds/demo_viewer.html` (insert page 1 body and `renderConfig()` JS function)

**Implementation:**
Page 1 layout is the four-card grid from mockup lines 460–514. In the mockup, the card values are hard-coded. In production, the values come from `window.DEMO_LOG.config`. The recorder's `_config_snapshot()` function (Phase 2, Task 7) emits the fields this phase consumes.

**Expected shape of `window.DEMO_LOG.config`** (from Phase 2, Task 6 `_config_snapshot` output):

```jsonc
{
  "source": "data/raw/synthetic_dataset.parquet",
  "source_mode": "synthetic",
  "target": "binary_target",
  "scale": "large",
  "max_trials": 50,
  "cv_folds": 5,
  "timeout": 36000,
  "algorithms": ["lightgbm", "logistic_regression"],
  "primary_metric": "ase",
  "cost_override": null,
  "tracing": "disabled"
}
```

**Note on config shape evolution:** The `config` object only includes keys that exist in `config/settings.yaml` at runtime. Fields like `tiebreaker`, `ml_reviewer`, `business_stakeholder`, `report_writer`, `review_enabled`, and `review_threshold` were removed when the Phase 2 recorder was simplified to drop non-existent config keys. The renderer uses the `?? '—'` operator for missing fields, so future config shapes can gain or lose keys without breaking the viewer.

If any field is missing from the runtime log, render the literal string `—` (em-dash) as the value. Do not silently default to a plausible value — the demo is about honesty.

**Step 1: Copy page 1 body from the mockup**

Use the Read tool to extract mockup lines 460–514 (the full `<div class="page p1">` block). Use the Edit tool to paste it into the scaffold, replacing the `<!-- Page 1: Config — populated in Task 2 -->` comment.

**Two modifications to the pasted block:**

1. Replace the hard-coded values (`data/raw/synthetic_dataset.parquet`, `binary_target`, `500,000 × 17`, `26.8%`, etc.) with data attributes that the render function will fill. Example:

   ```html
   <div class="kv"><span class="k">Source</span><span class="v" data-cfg="source">—</span></div>
   <div class="kv"><span class="k">Target</span><span class="v" data-cfg="target">—</span></div>
   <div class="kv"><span class="k">Rows × cols</span><span class="v" data-cfg="rows_cols">—</span></div>
   <div class="kv"><span class="k">Positive rate</span><span class="v" data-cfg="positive_rate_pct">—</span></div>
   ```

   Keep the same structure for all four cards. For the algorithms card, give the `<div class="chips">` container a `data-cfg-chips="algorithms"` attr so the renderer can rebuild the chip spans.

2. Replace the RUN button with `<button class="btn" data-goto="input">RUN ▶</button>`. The navigation helper from Task 1 wires this up — no per-button listener.

**Step 2: Add `renderConfig()` to the script block**

Insert this function before the `goTo` definition:

```javascript
function fmtPct(value) {
  if (value == null || Number.isNaN(value)) return '—';
  return (value * 100).toFixed(1) + '%';
}

function fmtNum(value) {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toLocaleString('en-US');
}

function renderConfig() {
  const cfg = window.DEMO_LOG.config || {};
  const setText = (sel, text) => {
    const el = document.querySelector(sel);
    if (el) el.textContent = text;
  };

  setText('[data-cfg="source"]',            cfg.source            ?? '—');
  setText('[data-cfg="source_mode"]',       cfg.source_mode       ?? '—');
  setText('[data-cfg="target"]',            cfg.target            ?? '—');
  setText('[data-cfg="scale"]',             cfg.scale             ?? '—');
  setText('[data-cfg="max_trials"]',        cfg.max_trials        ?? '—');
  setText('[data-cfg="cv_folds"]',          cfg.cv_folds          ?? '—');
  setText('[data-cfg="timeout"]',           cfg.timeout           ?? '—');
  setText('[data-cfg="primary_metric"]',    cfg.primary_metric    ?? '—');
  setText('[data-cfg="cost_override"]',     cfg.cost_override     ?? '—');
  setText('[data-cfg="tracing"]',           cfg.tracing           ?? '—');

  const chipBox = document.querySelector('[data-cfg-chips="algorithms"]');
  if (chipBox) {
    chipBox.innerHTML = '';
    const algos = Array.isArray(cfg.algorithms) ? cfg.algorithms : [];
    if (algos.length === 0) {
      chipBox.textContent = '—';
    } else {
      algos.forEach((name) => {
        const s = document.createElement('span');
        s.className = 'chip';
        s.textContent = name;
        chipBox.appendChild(s);
      });
    }
  }
}

// Initial render on load.
renderConfig();
```

Keep the rest of the script block unchanged. The `goTo` handler continues to call `startRuntimeReplay()` only for the `runtime` target — `renderConfig` runs once at load time.

**Step 3: Manual verification**

Since there is no JSON file yet (Phase 2 Task 8 produces it), use a small inline stub for spot-checking. Open a scratch file:

```bash
cat > /tmp/demo_viewer_test.html <<'EOF'
<script>
window.DEMO_LOG = {
  config: {
    source: "data/raw/synthetic_dataset.parquet",
    source_mode: "synthetic",
    target: "binary_target",
    scale: "large",
    max_trials: 50, cv_folds: 5, timeout: 36000,
    algorithms: ["lightgbm", "logistic_regression"],
    primary_metric: "ase",
    tracing: "disabled"
  },
  artifacts: {}, events: []
};
</script>
EOF

# Prepend the stub to the viewer and open in a browser (or inspect with a headless tool):
cat /tmp/demo_viewer_test.html src/multi_agent_ds/demo_viewer.html > /tmp/demo_viewer_with_stub.html
echo "Open /tmp/demo_viewer_with_stub.html in a browser"
```

Verify visually: all four cards show populated values, RUN button is clickable, clicking RUN swaps the visible page to page 2 (which is still an empty shell from Task 1 — that's OK, Task 3 fills it in).

**Step 4: Smoke-test the code path (no browser)**

If a Node REPL or headless HTML parser is available, run the script block through `jsdom` to ensure no syntax errors:

```bash
uv run python -c "
from pathlib import Path
html = Path('src/multi_agent_ds/demo_viewer.html').read_text()
assert 'renderConfig()' in html, 'renderConfig function missing'
assert 'data-goto=\"input\"' in html, 'RUN button wiring missing'
assert 'data-cfg=\"source\"' in html, 'config template markers missing'
print('static checks passed')
"
```

Expected: prints `static checks passed` with exit code 0.

**Step 5: Commit**

```bash
git add src/multi_agent_ds/demo_viewer.html
git commit -m "feat(demo-viewer): render Page 1 (Config) from DEMO_LOG

why: AC3.1 requires Page 1 to show source path, target column,
rows × cols, positive rate, scale, max_trials, cv_folds, timeout,
algorithms, and review settings from config/settings.yaml. These
values come through the recorder's config snapshot on
window.DEMO_LOG.config.

architecture fit: viewer reads injected global; no network calls
from the browser; renderConfig() is a pure DOM function.

validation: static checks confirm renderConfig, RUN button, and
data-cfg markers are present. Visual check with stubbed DEMO_LOG
showed all four cards populate correctly.

notes: missing fields render '—' intentionally. No silent defaults.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_2 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_TASK_3 -->
### Task 3: Populate Page 2 (Input Preview) with dynamic pill strip and table

**Active role:** `implementation_engineer` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/implementation-engineer.md` for load-bearing decisions within this task.

**Files:**
- Modify: `src/multi_agent_ds/demo_viewer.html` (insert page 2 body and `renderInputPreview()` JS function)

**Implementation:**
Page 2 layout is the pill-strip + `df.head(10)` table from mockup lines 517–570. In the mockup, the table rows and pill values are hard-coded. In production:

- Pill values come from `window.DEMO_LOG.artifacts.input_df_stats` (produced by Phase 2, Task 7's `_compute_input_stats`):
  ```jsonc
  {
    "rows": 500000, "cols": 17, "target": "binary_target",
    "positive_rate": 0.268, "numeric_count": 11, "categorical_count": 5,
    "missing_pct": 0.031
  }
  ```
- Table rows come from `window.DEMO_LOG.artifacts.input_df_head` — an array of up to 10 row-dicts. Column headers are taken from `Object.keys(rows[0])` if present.

**Scope note on column headers:** The mockup hard-codes 10 columns with a pretty display. Production accepts a variable column set (synthetic dataset has 17 columns). Render the first 10 columns in the order they appear in `rows[0]`, with the target column pinned last and styled with the `.target` class. If `rows.length === 0`, show the literal string "no input data recorded" in a single centered row.

**Step 1: Copy page 2 body from the mockup**

Extract mockup lines 517–570 and paste them into `src/multi_agent_ds/demo_viewer.html` where the `<!-- Page 2: Input Preview — populated in Task 3 -->` placeholder sits.

**Three modifications to the pasted block:**

1. Replace each `.pill` text content with placeholders the renderer fills:
   ```html
   <div class="pillstrip" data-input-pills>
     <div class="pill"><b data-pill="rows">—</b> rows</div>
     <div class="pill"><b data-pill="cols">—</b> columns</div>
     <div class="pill accent">target = <b data-pill="target">—</b></div>
     <div class="pill">positive rate <b data-pill="positive_rate_pct">—</b></div>
     <div class="pill">numeric <b data-pill="numeric_count">—</b></div>
     <div class="pill">categorical <b data-pill="categorical_count">—</b></div>
     <div class="pill">missing cells <b data-pill="missing_pct">—</b></div>
   </div>
   ```

2. Replace the hard-coded `<thead>` and `<tbody>` with containers the renderer rebuilds:
   ```html
   <div class="tbl">
     <table>
       <thead data-input-head></thead>
       <tbody data-input-body></tbody>
     </table>
   </div>
   ```

3. Replace the CONTINUE button with `<button class="btn" data-goto="runtime">CONTINUE ▶</button>`.

**Step 2: Add `renderInputPreview()` to the script block**

Insert before `renderConfig` (or right after — order within the script doesn't matter, but keep the two render functions adjacent):

```javascript
function renderInputPreview() {
  const stats = (window.DEMO_LOG.artifacts && window.DEMO_LOG.artifacts.input_df_stats) || {};
  const rows  = (window.DEMO_LOG.artifacts && window.DEMO_LOG.artifacts.input_df_head) || [];

  // --- Pill strip ---
  const setPill = (key, text) => {
    const el = document.querySelector(`[data-pill="${key}"]`);
    if (el) el.textContent = text;
  };
  setPill('rows',               fmtNum(stats.rows));
  setPill('cols',               stats.cols ?? '—');
  setPill('target',             stats.target ?? '—');
  setPill('positive_rate_pct',  fmtPct(stats.positive_rate));
  setPill('numeric_count',      stats.numeric_count ?? '—');
  setPill('categorical_count',  stats.categorical_count ?? '—');
  setPill('missing_pct',        fmtPct(stats.missing_pct));

  // --- Table ---
  const thead = document.querySelector('[data-input-head]');
  const tbody = document.querySelector('[data-input-body]');
  if (!thead || !tbody) return;
  thead.innerHTML = '';
  tbody.innerHTML = '';

  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="1" style="text-align:center;color:var(--slate);padding:16px;">no input data recorded</td></tr>';
    return;
  }

  // Determine columns: first 10 from the first row, with target pinned last.
  const targetCol = stats.target;
  let cols = Object.keys(rows[0]).slice(0, 10);
  if (targetCol && cols.includes(targetCol)) {
    cols = cols.filter((c) => c !== targetCol).concat([targetCol]);
  }

  // Header row
  const tr = document.createElement('tr');
  cols.forEach((col) => {
    const th = document.createElement('th');
    th.textContent = col;
    if (col === targetCol) {
      th.classList.add('target');
      th.style.color = '#FFB680';
    }
    tr.appendChild(th);
  });
  thead.appendChild(tr);

  // Body rows
  rows.slice(0, 10).forEach((row) => {
    const rtr = document.createElement('tr');
    cols.forEach((col) => {
      const td = document.createElement('td');
      const v = row[col];
      td.textContent = (v == null) ? '—' : String(v);
      if (col === targetCol) td.classList.add('target');
      rtr.appendChild(td);
    });
    tbody.appendChild(rtr);
  });
}

// Initial render on load.
renderInputPreview();
```

**Step 3: Verify static shape**

```bash
uv run python -c "
from pathlib import Path
html = Path('src/multi_agent_ds/demo_viewer.html').read_text()
assert 'renderInputPreview()' in html, 'renderInputPreview function missing'
assert 'data-goto=\"runtime\"' in html, 'CONTINUE button wiring missing'
assert 'data-input-head' in html and 'data-input-body' in html, 'table template markers missing'
assert 'data-pill=\"rows\"' in html, 'pill strip markers missing'
print('static checks passed')
"
```

Expected: prints `static checks passed`.

**Step 4: Manual visual check with stub**

Extend the Task 2 stub with sample input data:

```bash
cat > /tmp/demo_viewer_test2.html <<'EOF'
<script>
window.DEMO_LOG = {
  config: { source: "data/raw/synthetic_dataset.parquet", target: "binary_target", rows: 500000, cols: 17, positive_rate: 0.268, scale: "small", max_trials: 5, cv_folds: 2, timeout_s: 60, algorithms: ["lightgbm", "xgboost"], primary_metric: "roc_auc", tiebreaker: "pr_auc", ml_reviewer: "enabled", business_stakeholder: "enabled", report_writer: "markdown", tracing: "off (local)" },
  artifacts: {
    input_df_stats: { rows: 500000, cols: 17, target: "binary_target", positive_rate: 0.268, numeric_count: 11, categorical_count: 5, missing_pct: 0.031 },
    input_df_head: [
      { policy_id: "P-000001", age: 42, tenure: 6, income: 12430, score: 712, region: "MIDWEST", claims: 0, plan: "STANDARD", premium_usd: 1284.00, binary_target: 0 },
      { policy_id: "P-000002", age: 28, tenure: 2, income: 18200, score: 668, region: "SOUTH",   claims: 1, plan: "BASIC",    premium_usd: 1612.50, binary_target: 1 }
    ]
  },
  events: []
};
</script>
EOF

cat /tmp/demo_viewer_test2.html src/multi_agent_ds/demo_viewer.html > /tmp/demo_viewer_with_stub2.html
echo "Open /tmp/demo_viewer_with_stub2.html — click RUN, then confirm page 2 renders"
```

Expected visual result: page 1 renders config, RUN button swaps to page 2, pill strip shows `500,000 rows · 17 columns · target = binary_target · positive rate 26.8% · numeric 11 · categorical 5 · missing cells 3.1%`, table shows two rows with `binary_target` column pinned last and styled.

**Step 5: Commit**

```bash
git add src/multi_agent_ds/demo_viewer.html
git commit -m "feat(demo-viewer): render Page 2 (Input Preview) from DEMO_LOG

why: AC4.1 requires Page 2 to show df.head(10) of the raw parquet
plus a seven-field pill strip. Values come from the recorder's
input_df_head and input_df_stats artifacts.

architecture fit: pure DOM render against injected DEMO_LOG;
matches Page 1 pattern from Task 2.

validation: static checks confirm renderInputPreview, CONTINUE
button, table template markers, and pill markers are present.
Visual check with stubbed DEMO_LOG showed pills populate and
table renders with target column pinned last and highlighted.

notes: variable column count handled (first 10 of row 0, target
pinned last). Empty input_df_head renders 'no input data recorded'.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_3 -->

<!-- START_TASK_4 -->
### Task 4: End-to-end verification with real recorded JSON

**Active role:** `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` for load-bearing decisions within this task.

**Files:**
- No files modified. This task only verifies.

**Implementation:**
Phase 2 Task 8 produced `data/interim/demo_run_latest.json` from a real `eda_analyst → data_engineer` run. Wire it into the viewer manually (Phase 6 will do this in Streamlit) to confirm the real payload shape matches what `renderConfig` and `renderInputPreview` expect.

**Step 1: Check the recorded JSON exists**

```bash
ls -la data/interim/demo_run_latest.json
uv run python -c "
import json
log = json.loads(open('data/interim/demo_run_latest.json').read())
print('keys:', sorted(log.keys()))
print('config keys:', sorted(log['config'].keys()))
print('artifacts keys:', sorted(log['artifacts'].keys()))
print('input_df_head rows:', len(log['artifacts'].get('input_df_head', [])))
print('events count:', len(log['events']))
"
```

Expected: file exists (output of Phase 2 AC verification). Top-level keys include `config`, `artifacts`, `events`. `config` has at minimum `source`, `source_mode`, `target`, `scale`, `max_trials`, `cv_folds`, `timeout`, `algorithms`, `primary_metric`, `tracing`. Optional config keys include `cost_override`. `artifacts` has `input_df_head`, `input_df_stats`. `input_df_head` length is between 1 and 10.

If any required config key is missing, return to Phase 2 Task 7 and fix `_config_snapshot()` before continuing — this is the interface Phase 3 codes to.

**Step 2: Combine viewer + real JSON and open in a browser**

```bash
uv run python -c "
import json
from pathlib import Path
log = Path('data/interim/demo_run_latest.json').read_text()
viewer = Path('src/multi_agent_ds/demo_viewer.html').read_text()
# Inject DEMO_LOG just before the viewer's own <script> block.
injected = viewer.replace(
    '<script>',
    f'<script>window.DEMO_LOG = {log};</script>\n  <script>',
    1
)
Path('/tmp/demo_viewer_e2e.html').write_text(injected)
print('wrote /tmp/demo_viewer_e2e.html — open in a browser')
"
```

**Step 3: Visual checklist**

Open `/tmp/demo_viewer_e2e.html` in a browser and verify:

- [ ] Page 1 (Config) shows real source path, real target column, real rows × cols, real positive rate.
- [ ] Page 1 algorithms chips match `config.algorithms` from the JSON.
- [ ] Clicking RUN swaps to Page 2.
- [ ] Page 2 pill strip shows seven pills with real numbers (no `—` values).
- [ ] Page 2 table shows up to 10 rows of real data.
- [ ] Target column is pinned last and highlighted orange.
- [ ] Clicking CONTINUE swaps to Page 3 (still a stub — that's expected; Phase 4 fills it in).
- [ ] Browser dev tools console shows no errors.

**Step 4: Report findings**

Per the `plan_guardian` role in `development_agents/team.md`, present the visual checklist results in the end-of-slice summary. If any item fails, diagnose whether the fix belongs in:

- `renderConfig` / `renderInputPreview` (Phase 3 — fix here)
- `_config_snapshot` / `_compute_input_stats` (Phase 2 — loop back)
- The pasted mockup markup (Phase 3 — fix here)

No commit in this task. If fixes are needed, they commit as amendments to Task 2 or Task 3 code — not a standalone "fix" commit.
<!-- END_TASK_4 -->

## Phase 3 Done-When

- [ ] `src/multi_agent_ds/demo_viewer.html` exists and is self-contained.
- [ ] Opening the viewer with a real recorded JSON renders Page 1 with correct config values.
- [ ] RUN button advances to Page 2.
- [ ] Page 2 renders `df.head(10)` and the seven-pill strip.
- [ ] CONTINUE button advances to Page 3 (placeholder is acceptable).
- [ ] Browser dev tools show no console errors on any page transition.
- [ ] Three commits landed (Tasks 1, 2, 3) on branch `demo-runtime-viewer`. Task 4 is verification only.
