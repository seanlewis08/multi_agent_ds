# Demo Runtime Viewer Design

**Author:** Sean Lewis
**Date:** 2026-04-16
**Status:** Draft — awaiting approval
**Scope constraint:** The live demo pipeline stops immediately after the `data_engineer` node completes. `ml_modeler`, `ml_reviewer`, `business_stakeholder`, and `report_writer` are **not** executed live. Their rail cards in the UI present canned-but-clearly-labeled scripted content so the audience still sees the full pipeline shape.

## Summary

A static HTML + JavaScript viewer, embedded inside the existing Streamlit dashboard (`src/multi_agent_ds/app.py`), replays a recorded JSON event log from a real run of the `eda_analyst → data_engineer` slice. The viewer surfaces four screens — Config, Input Preview, Runtime (animated agent columns), and Output + Summary (click-to-reveal agent drawer) — matching the validated mockup at [`demo_mockup.html`](../../demo_mockup.html).

The run is recorded once via a new `src/multi_agent_ds/orchestration/demo_recorder.py` that builds a two-node sub-graph (`eda_raw → data_engineer → END`), streams `graph.astream_events(version="v2")`, writes events to `data/interim/demo_run_latest.json`, and exits. The viewer never calls the graph at demo time, so OpenAI outages, network flakes, and timing variance cannot break the demo. Canned content for the four un-executed agents is shipped as a static JSON block co-located with the viewer.

## Definition of Done

1. Running `uv run python -m multi_agent_ds.orchestration.demo_recorder` produces `data/interim/demo_run_latest.json` containing the ordered event stream from a real `eda_analyst → data_engineer` run against `data/raw/synthetic_dataset.parquet`.
2. Running `uv run streamlit run src/multi_agent_ds/app.py` and selecting the new "Demo" mode renders the four-screen viewer embedded via `st.components.v1.html(...)`, using the recorded JSON.
3. The Config screen shows values from `config/settings.yaml` and a Run button that advances to the Input Preview screen.
4. The Input Preview screen shows `df.head(10)` of the configured parquet plus the pill-stat strip.
5. The Runtime screen animates orchestrator routing, EDA agent lanes (Input / Action / Output), and Data Engineer lanes, driven by event timestamps from the recording. ML Modeler / Reviewer / Biz Stakeholder columns remain in a dimmed "not scheduled in demo scope" state.
6. The Output & Summary screen shows `df.head(10)` of the processed output and the seven-card agent rail. Clicking any card slides the page 75% left and reveals that agent's summary. For EDA and Data Engineer the summary is populated from the recorded run. For Orchestrator the summary reflects the actual routing that occurred. For ML Modeler, ML Reviewer, Business Stakeholder, and Report Writer the summary pane is clearly labeled `SCRIPTED — not executed in this demo run` and shows the canned content.
7. All new code lives within the existing repo tree (`src/multi_agent_ds/`, `data/interim/`, `project_planning/design_plans/`). No new top-level directories.
8. `pyarrow>=18.0.0` is declared in `pyproject.toml` under `[project].dependencies`. `uv sync` succeeds. `pd.read_parquet("data/raw/synthetic_dataset.parquet")` succeeds.
9. A rehearsed end-to-end run from Config click-through to final summary drawer completes within 90 seconds and produces no console errors in the browser dev tools.

## Acceptance Criteria

### demo-runtime-viewer.AC1: Recording

- **demo-runtime-viewer.AC1.1 Success:** `demo_recorder.py --output data/interim/demo_run_latest.json` writes a JSON file whose top-level `events` array contains at minimum one event with `kind: "node_start", node: "eda_raw"`, one with `kind: "node_end", node: "eda_raw"`, one with `kind: "node_start", node: "data_engineer"`, and one with `kind: "node_end", node: "data_engineer"`.
- **demo-runtime-viewer.AC1.2 Success:** The recorded JSON includes `artifacts.raw_eda_insights` (the EDA agent's structured output) and `artifacts.prep_plan` + `artifacts.processed_df_head` (the Data Engineer's outputs).
- **demo-runtime-viewer.AC1.3 Success:** Every event has `ts` (ISO-8601 timestamp) and `elapsed_ms` (ms since recording started).
- **demo-runtime-viewer.AC1.4 Failure:** If the configured parquet path does not exist, the recorder raises a clear `FileNotFoundError` naming the missing path and does not write a partial JSON.
- **demo-runtime-viewer.AC1.5 Failure:** If `OPENAI_API_KEY` is unset, the recorder raises a clear `EnvironmentError` before invoking the graph.
- **demo-runtime-viewer.AC1.6 Edge:** Re-running the recorder atomically replaces `data/interim/demo_run_latest.json` (writes to `.tmp` sibling, then renames).

### demo-runtime-viewer.AC2: Streamlit integration

- **demo-runtime-viewer.AC2.1 Success:** `app.py` exposes a new sidebar mode option "Demo" that, when selected, renders the viewer via `st.components.v1.html(...)` with `height=820` and `scrolling=False`.
- **demo-runtime-viewer.AC2.2 Success:** The Demo mode reads `data/interim/demo_run_latest.json` and injects it as a JSON string literal into the HTML template before rendering.
- **demo-runtime-viewer.AC2.3 Failure:** If the JSON file is missing, Demo mode renders a clear error state with the exact command to re-record.

### demo-runtime-viewer.AC3: Config screen

- **demo-runtime-viewer.AC3.1 Success:** Page 1 shows source path, target column, rows × cols, positive rate, scale, max_trials, cv_folds, timeout, algorithms, and review settings from `config/settings.yaml`.
- **demo-runtime-viewer.AC3.2 Success:** Clicking the RUN button transitions to the Input Preview screen.

### demo-runtime-viewer.AC4: Input Preview screen

- **demo-runtime-viewer.AC4.1 Success:** Page 2 shows `df.head(10)` of the raw parquet plus a pill-strip with row count, column count, target name, positive rate, numeric count, categorical count, and missing-cell percentage.
- **demo-runtime-viewer.AC4.2 Success:** Clicking CONTINUE transitions to the Runtime screen and starts the replay timer.

### demo-runtime-viewer.AC5: Runtime animation

- **demo-runtime-viewer.AC5.1 Success:** Orchestrator band shows current state labels derived from live events ("STARTING", "EDA RUNNING", "HANDOFF", "DATA ENGINEER RUNNING", "COMPLETE").
- **demo-runtime-viewer.AC5.2 Success:** EDA Analyst column highlights orange (active) between its `node_start` and `node_end` events, then locks to green (done). Its Input / Action / Output lanes populate with items in the order the events arrived.
- **demo-runtime-viewer.AC5.3 Success:** Data Engineer column activates only after EDA's `node_end`. Same lane behavior.
- **demo-runtime-viewer.AC5.4 Success:** ML Modeler, ML Reviewer, Business Stakeholder columns display a single footer label "not scheduled in demo scope" in muted text.
- **demo-runtime-viewer.AC5.5 Success:** The replay speed is controllable via a header selector (`0.5x`, `1x`, `1.5x`, `2x`). Default is `1.5x`.
- **demo-runtime-viewer.AC5.6 Failure:** Clicking CONTINUE twice (or pressing it during playback) is a no-op — it does not restart the animation.

### demo-runtime-viewer.AC6: Output & Summary drawer

- **demo-runtime-viewer.AC6.1 Success:** Page 4 shows `df.head(10)` of the processed dataframe from `artifacts.processed_df_head` plus the four delta cards.
- **demo-runtime-viewer.AC6.2 Success:** The seven-card agent rail matches the mockup: Orchestrator, EDA Analyst, Data Engineer, ML Modeler, ML Reviewer, Business Stakeholder, Report Writer.
- **demo-runtime-viewer.AC6.3 Success:** Clicking any card translates the slider by `-960px` over 520ms and displays only that agent's pane.
- **demo-runtime-viewer.AC6.4 Success:** Orchestrator, EDA Analyst, and Data Engineer panes populate from recorded JSON.
- **demo-runtime-viewer.AC6.5 Success:** ML Modeler, ML Reviewer, Business Stakeholder, Report Writer panes display a "SCRIPTED — not executed in this demo run" header badge and render canned content from a static `DEMO_CANNED` block in the HTML.
- **demo-runtime-viewer.AC6.6 Success:** Clicking BACK closes the drawer. Clicking a different card while one is open swaps panes without an intermediate close.

### demo-runtime-viewer.AC7: Repo hygiene

- **demo-runtime-viewer.AC7.1 Success:** `pyarrow>=18.0.0` is declared in `pyproject.toml`. `uv sync` succeeds.
- **demo-runtime-viewer.AC7.2 Success:** No new top-level directories are created. New files live at:
  - `project_planning/design_plans/2026-04-16-demo-runtime-viewer.md`
  - `src/multi_agent_ds/orchestration/demo_recorder.py`
  - `src/multi_agent_ds/demo_viewer.html`
  - `data/interim/demo_run_latest.json` (runtime output, not checked in)
- **demo-runtime-viewer.AC7.3 Success:** `project_planning/PROJECT_TREE.md` is updated in the same commit as any new path it introduces.
- **demo-runtime-viewer.AC7.4 Success:** No modifications to any existing agent implementation (`src/multi_agent_ds/agents/*.py`) or to the production graph (`src/multi_agent_ds/orchestration/graph.py`). The demo builds its own minimal sub-graph.

## Glossary

- **LangGraph**: State-machine library for orchestrating LLM agents as a graph of nodes. This repo already uses it in `src/multi_agent_ds/orchestration/graph.py`.
- **`astream_events(version="v2")`**: LangGraph API that yields a unified stream of lifecycle events (`on_chain_start`, `on_chain_end`, `on_tool_start`, etc.) while the graph runs. The recorder consumes this and normalizes each event into a single JSON record.
- **sub-graph**: A smaller `StateGraph` compiled from a subset of nodes. The demo recorder builds a two-node sub-graph (`eda_raw → data_engineer`) instead of running the production graph and halting mid-stream.
- **event log**: The ordered array of event records written by the recorder. The viewer's replay engine iterates this list using `elapsed_ms` to schedule `setTimeout`-driven UI updates.
- **replay engine**: The JS inside `demo_viewer.html` that takes the event log, schedules DOM updates against page 3 (runtime), and populates page 4 (summary) once the log is exhausted.
- **canned content**: Hard-coded HTML strings for the four agents that did not run. Clearly labeled "SCRIPTED" in the UI so the demo is honest about what is live vs. illustrative.
- **`st.components.v1.html`**: Streamlit API that renders arbitrary HTML/JS inside an iframe. Our integration point — no new framework needed.
- **record-once-replay-many**: The demo pattern. Record a real run to JSON once, then replay deterministically at demo time. Removes OpenAI, network, and timing dependencies from the live demo.

## Architecture

Three components, one-way data flow:

```
┌─────────────────────────┐      ┌──────────────────────────┐      ┌────────────────────────┐
│ demo_recorder.py        │ ──▶  │ data/interim/            │ ──▶  │ app.py  (Streamlit)    │
│ (orchestration layer)   │      │   demo_run_latest.json   │      │   └─ demo_viewer.html  │
│ builds sub-graph        │      │ (event log + artifacts)  │      │      (embedded iframe) │
│ streams astream_events  │      └──────────────────────────┘      └────────────────────────┘
│ writes JSON             │
└─────────────────────────┘
```

**Recorder (`src/multi_agent_ds/orchestration/demo_recorder.py`)** is a Python module with a `__main__` entrypoint. It imports the existing `eda_analyst` and `data_engineer` agent node functions, composes a two-node `StateGraph`, invokes `graph.compile().astream_events(version="v2")` with the initial state (raw dataframe), and writes each event plus final artifacts to `data/interim/demo_run_latest.json` atomically. It does not touch the production `graph.py`. It reuses `config.load_settings()`, `core.context.build_context()`, and any existing data loader. Adheres to the layer rule: recorder lives in `orchestration/`, imports from `workflows/`, `agents/`, `skills/`, `tools/`.

**Event log (`data/interim/demo_run_latest.json`)** is a single JSON object:

```jsonc
{
  "recorded_at": "2026-04-16T14:03:22Z",
  "duration_ms": 42180,
  "config": { "source": "...", "target": "...", "scale": "small", "max_trials": 5, ... },
  "artifacts": {
    "raw_eda_insights": { /* from eda_analyst */ },
    "prep_plan":        { /* from data_engineer */ },
    "processed_df_head": [ /* array of 10 row-dicts */ ],
    "input_df_head":     [ /* array of 10 row-dicts */ ],
    "input_df_stats":    { "rows": 500000, "cols": 17, "positive_rate": 0.268, ... }
  },
  "events": [
    { "ts": "...", "elapsed_ms": 12,    "kind": "node_start", "node": "orchestrator", "data": {...} },
    { "ts": "...", "elapsed_ms": 87,    "kind": "node_start", "node": "eda_raw",      "data": {...} },
    { "ts": "...", "elapsed_ms": 8420,  "kind": "node_end",   "node": "eda_raw",      "data": {...} },
    { "ts": "...", "elapsed_ms": 8612,  "kind": "node_start", "node": "data_engineer", "data": {...} },
    { "ts": "...", "elapsed_ms": 40110, "kind": "node_end",   "node": "data_engineer", "data": {...} }
  ]
}
```

**Viewer (`src/multi_agent_ds/demo_viewer.html`)** is a single self-contained HTML file derived from [`demo_mockup.html`](../../demo_mockup.html). The Streamlit app reads it at render time, injects the JSON log via a `<script>window.DEMO_LOG = {...};</script>` block, and hands the resulting string to `st.components.v1.html()`. The HTML contains:
- Static CSS (copied from the mockup)
- Four `<div class="page">` sections with identical styling to the mockup
- A replay engine (~100 lines of JS) that walks `window.DEMO_LOG.events`, schedules DOM updates via `setTimeout(fn, evt.elapsed_ms * speedMultiplier)`, and flips state classes on agent columns
- A `DEMO_CANNED` const holding mocked content for the four un-executed agents (clearly labeled in the drawer header)

**Streamlit integration (`src/multi_agent_ds/app.py`, existing file)** adds a sidebar mode option "Demo". When selected, Streamlit reads the HTML template and the JSON log from disk, concatenates them, and passes the result to `st.components.v1.html(html, height=820, scrolling=False)`. No new pages, no new routing — just an additional `if mode == "Demo":` branch in the existing mode dispatcher.

## Existing Patterns

Investigation of the repo surfaced these patterns the design follows:

- **Layer architecture** (`project_planning/ARCHITECTURE.md`): `orchestration/ → workflows/ → agents/ → skills/ → tools/`. The recorder sits at the `orchestration/` layer and composes existing agent node functions without reaching into lower layers directly.
- **Config-driven** (`config/settings.yaml`): Algorithms, metrics, budgets live in YAML. The demo recorder reads from the same settings file — no duplicate config.
- **Streamlit as front-end** (`src/multi_agent_ds/app.py`, 693 lines, Step 5b in progress per `BUILD_PLAN.md`): The existing dashboard is where demo rendering belongs. Adding a mode is additive; no new app framework.
- **Pure skills, side effects in workflows** (`project_planning/ARCHITECTURE.md`): The recorder performs all I/O (file write, event capture). Skills are not touched.
- **LangGraph compile + stream** (`src/multi_agent_ds/orchestration/graph.py`): The production graph uses the same compile + event pattern. The recorder's sub-graph uses the same APIs — no new LangGraph usage patterns.

No existing pattern exists for "record-once-replay-many" or for embedding static HTML in Streamlit. Both are introduced here. The HTML embedding is a one-line Streamlit API, not a new architectural layer.

## Implementation Phases

<!-- START_PHASE_1 -->
### Phase 1: Approval & dependency setup

**Goal:** Unblock parquet reads and confirm scope with the user before any new code.

**Components:**
- `pyproject.toml` — add `pyarrow>=18.0.0` under `[project].dependencies`
- `uv.lock` — regenerated via `uv sync`
- `project_planning/PROJECT_TREE.md` — update to include the four new paths introduced by this plan

**Dependencies:** User approval for: (a) adding `pyarrow`, (b) scope cut at `data_engineer`, (c) the four new file paths listed in AC7.2.

**Done when:** `uv sync` succeeds. `python -c "import pandas; pandas.read_parquet('data/raw/synthetic_dataset.parquet').head()"` succeeds. `PROJECT_TREE.md` matches the planned final state.
<!-- END_PHASE_1 -->

<!-- START_PHASE_2 -->
### Phase 2: Demo recorder

**Goal:** Produce a deterministic JSON event log from a real `eda_analyst → data_engineer` run.

**Components:**
- `src/multi_agent_ds/orchestration/demo_recorder.py` — new module with a `__main__` entrypoint. Builds a two-node `StateGraph` using existing `eda_analyst` and `data_engineer` node callables. Streams `astream_events(version="v2")`. Normalizes each event into `{ ts, elapsed_ms, kind, node, data }`. Writes the complete JSON (config + artifacts + events) atomically to `data/interim/demo_run_latest.json`.
- Unit tests at `tests/unit/orchestration/test_demo_recorder.py` covering: (i) event normalization shape, (ii) atomic write behavior, (iii) env-var guard, (iv) missing-parquet guard.

**Dependencies:** Phase 1 complete (pyarrow installed, approval granted).

**Done when:** `uv run python -m multi_agent_ds.orchestration.demo_recorder --output data/interim/demo_run_latest.json` produces a file satisfying AC1.1–AC1.6. Unit tests pass.

**ACs covered:** demo-runtime-viewer.AC1.1, demo-runtime-viewer.AC1.2, demo-runtime-viewer.AC1.3, demo-runtime-viewer.AC1.4, demo-runtime-viewer.AC1.5, demo-runtime-viewer.AC1.6.
<!-- END_PHASE_2 -->

<!-- START_PHASE_3 -->
### Phase 3: Viewer HTML — Config + Input Preview screens

**Goal:** Port pages 1 and 2 of `demo_mockup.html` into the production `demo_viewer.html`, parameterized from the event log JSON.

**Components:**
- `src/multi_agent_ds/demo_viewer.html` — new self-contained HTML file. Copies the mockup's CSS verbatim. Page 1 and Page 2 read from `window.DEMO_LOG.config`, `window.DEMO_LOG.artifacts.input_df_head`, and `window.DEMO_LOG.artifacts.input_df_stats`. Navigation via Run / Continue buttons implemented as simple class toggles on a root `<div>`.
- Manual verification script: open the file locally with a sample JSON and click through.

**Dependencies:** Phase 2 (need a JSON to wire into).

**Done when:** Opening the HTML with a recorded JSON shows correct config values and correct `df.head(10)`. RUN advances to page 2, CONTINUE advances to page 3 (which can be a placeholder for now). No console errors.

**ACs covered:** demo-runtime-viewer.AC3.1, demo-runtime-viewer.AC3.2, demo-runtime-viewer.AC4.1, demo-runtime-viewer.AC4.2.
<!-- END_PHASE_3 -->

<!-- START_PHASE_4 -->
### Phase 4: Viewer HTML — Runtime replay engine

**Goal:** Animate page 3 driven by the event log timestamps.

**Components:**
- Extend `src/multi_agent_ds/demo_viewer.html` with a replay engine (~100 lines of JS): walks `window.DEMO_LOG.events`, schedules DOM class toggles on agent columns using `elapsed_ms * speedMultiplier`, populates lane items from event `data` payloads.
- Add the speed selector UI (0.5x / 1x / 1.5x / 2x).
- Dim the ML Modeler, ML Reviewer, Business Stakeholder columns and add the "not scheduled in demo scope" footer label.

**Dependencies:** Phase 3.

**Done when:** Loading the page with a real recording visually matches the mockup's page 3 animation. Speed selector works. Clicking CONTINUE twice does not restart playback.

**ACs covered:** demo-runtime-viewer.AC5.1, demo-runtime-viewer.AC5.2, demo-runtime-viewer.AC5.3, demo-runtime-viewer.AC5.4, demo-runtime-viewer.AC5.5, demo-runtime-viewer.AC5.6.
<!-- END_PHASE_4 -->

<!-- START_PHASE_5 -->
### Phase 5: Viewer HTML — Output & Summary drawer

**Goal:** Port page 4 with the seven-agent rail and the click-to-slide drawer.

**Components:**
- Extend `demo_viewer.html` with the seven-card rail and the slider mechanics from the mockup.
- Populate Orchestrator / EDA / DE panes from `window.DEMO_LOG.artifacts.*`.
- Add a `DEMO_CANNED` constant with scripted content for ML Modeler, ML Reviewer, Business Stakeholder, Report Writer. Each scripted pane has a "SCRIPTED — not executed in this demo run" badge in the header.
- Wire delta cards (ROC-AUC, feature counts, missing %, runtime) from the available artifacts; any unavailable metric shows `n/a`.

**Dependencies:** Phase 4.

**Done when:** All seven rail cards open their respective panes. Recorded panes show real data. Scripted panes show the badge and canned content. BACK closes. Swapping cards is smooth.

**ACs covered:** demo-runtime-viewer.AC6.1, demo-runtime-viewer.AC6.2, demo-runtime-viewer.AC6.3, demo-runtime-viewer.AC6.4, demo-runtime-viewer.AC6.5, demo-runtime-viewer.AC6.6.
<!-- END_PHASE_5 -->

<!-- START_PHASE_6 -->
### Phase 6: Streamlit integration

**Goal:** Make the viewer accessible via `streamlit run app.py`.

**Components:**
- Modify `src/multi_agent_ds/app.py` — add a sidebar mode option "Demo". In the Demo branch: read `src/multi_agent_ds/demo_viewer.html` from disk, read `data/interim/demo_run_latest.json`, inject the JSON as a `<script>window.DEMO_LOG = {...};</script>` block before the closing `</head>`, and pass the result to `st.components.v1.html(html, height=820, scrolling=False)`.
- Error state: if the JSON is missing, render a clear message with the exact re-record command.
- Unit test at `tests/unit/test_app_demo_mode.py` for the template-injection helper (pure function — no Streamlit dependency in the test).

**Dependencies:** Phase 5 (viewer must be functional).

**Done when:** `uv run streamlit run src/multi_agent_ds/app.py` → select Demo → the viewer renders and the full four-screen flow works end-to-end. Missing-JSON error path renders correctly. Unit test passes.

**ACs covered:** demo-runtime-viewer.AC2.1, demo-runtime-viewer.AC2.2, demo-runtime-viewer.AC2.3.
<!-- END_PHASE_6 -->

<!-- START_PHASE_7 -->
### Phase 7: End-to-end rehearsal + recording

**Goal:** Verify the full loop works and capture a backup video.

**Components:**
- Run the recorder → inspect the JSON → run Streamlit → click through all four pages.
- Time the end-to-end flow. Target <90 seconds at 1.5x replay speed.
- Capture a screen recording (via OS-level screen recorder — no new code).
- Save backup recording alongside demo materials.

**Dependencies:** Phases 1–6 complete.

**Done when:** One clean click-through completes with no console errors and no visual glitches. Backup video saved.

**ACs covered:** demo-runtime-viewer.AC1.1 (end-to-end verification), AC5.*, AC6.*. This phase is operational validation, not new functionality.
<!-- END_PHASE_7 -->

## Additional Considerations

**Honesty about what is live:** The demo tells the audience "this is a recorded playback of a real EDA + Data Engineer run; the remaining four agents are scripted for illustration." This is surfaced in two places: a small "recorded" badge in the top bar during runtime, and the "SCRIPTED" badge in scripted drawer panes.

**What happens if the recorder fails the day of:** The last good `demo_run_latest.json` is kept in the repo's local filesystem (not checked in). As long as the file exists, the viewer works regardless of API or network state. The backup video from Phase 7 is the last line of defense.

**Scope excluded:** No changes to `src/multi_agent_ds/agents/*.py`. No changes to the production `graph.py`. No new tests beyond the recorder unit tests and the Streamlit template-injection helper test — the viewer is visually verified, not unit-tested.

**Future work deferred:** Live-streaming the graph's events directly into the viewer (without pre-recording) is a future enhancement, not shipped here. Same for recording the full pipeline through `report_writer` once the downstream nodes are wired into the production graph.
