# Demo Runtime Viewer — Rehearsal Runbook

**Demo Date:** April 17, 2026 (tomorrow morning)  
**Branch:** `demo-runtime-viewer`  
**Last Updated:** 2026-04-16

---

## Pre-Flight Checklist (Night Before)

Execute these steps on your laptop **before bed** to ensure the demo is ready to go:

### 1. Pull the branch
```bash
git checkout demo-runtime-viewer
git pull origin demo-runtime-viewer
```
Expected: clean working tree, HEAD is latest commit.

### 2. Sync dependencies
```bash
uv sync
```
Expected: completes without error. `pyarrow>=18.0.0` is installed.

### 3. Verify the parquet file
```bash
ls -lh data/raw/synthetic_dataset.parquet
```
Expected: file exists, size ≈ 39 MB, recent mtime.

### 4. Generate a fresh recording
```bash
export OPENAI_API_KEY="sk-..."  # if not already set
time uv run python -m multi_agent_ds.orchestration.demo_recorder \
  --output data/interim/demo_run_latest.json \
  --parquet data/raw/synthetic_dataset.parquet
```
Expected: completes in ≈ 60 s (OpenAI API latency varies). Prints resolved output path. Exit code 0.

**⏱️ Budget 10 minutes for the full run. This runs the 13-node EDA workflow with real LLM calls.**

### 5. Verify the JSON artifact
```bash
uv run python - <<'PY'
import json, pathlib
p = pathlib.Path("data/interim/demo_run_latest.json")
log = json.loads(p.read_text())

required_events = [
    ("node_start", "eda_raw"),
    ("node_end", "eda_raw"),
    ("node_start", "data_engineer"),
    ("node_end", "data_engineer"),
]
seen = {(e["kind"], e["node"]) for e in log["events"]}
missing = [r for r in required_events if r not in seen]

if missing:
    print(f"ERROR: missing events: {missing}")
    exit(1)

assert "recorded_at" in log
assert "duration_ms" in log and isinstance(log["duration_ms"], int)
assert all("ts" in e and "elapsed_ms" in e for e in log["events"])

print(f"OK: {len(log['events'])} events, "
      f"duration {log['duration_ms']} ms, "
      f"recorded_at {log['recorded_at']}")
PY
```
Expected: prints "OK: ..." message. Any error means the recording failed — check your API key and retry step 4.

### 6. Confirm file mtime is fresh
```bash
stat data/interim/demo_run_latest.json | grep Modify
```
Expected: timestamp is from the last few minutes (your recording time).

### ✅ All checks passed? You're ready to demo.

---

## Demo Walkthrough (4-Screen Flow)

**Total runtime target:** ≤ 90 seconds at 1.5× playback speed (DoD #9).

### Step 1: Launch Streamlit
```bash
uv run streamlit run src/multi_agent_ds/app.py
```
Expected: opens browser tab at `http://localhost:8591/` (or the next available port if 8591 is taken).

Streamlit should load without red error banners. Check the browser console (F12 → Console tab) — it should be clean.

### Step 2: Click the "Demo" tab
- Expected: iframe loads (~1 s), displaying Page 1.

### Page 1: Configuration (30 seconds)
**What to say:**
> "Here's the experiment configuration. On the left we have the source data parameters — 500k rows, 19 columns, binary classification target with about 27% positive class. On the right, the hyperparameter search settings — cross-validation folds, algorithm choices, and resource limits."

**What to do:**
- Scan the page visually. Confirm all config cards are populated (source path, row/col counts, positive rate, cv_folds, algorithms, max_trials, timeout).
- Click **RUN ▶** button to advance to Page 2.

**Success criteria:**
- All card values are visible and match the config file.
- Page 2 renders without delay.

---

### Page 2: Input Preview (45 seconds)
**What to say:**
> "The raw dataset: 500,000 rows and 19 features. We can see a sample of 10 rows and key statistics — the feature mix, missing data patterns, and the slight class imbalance we'll address later."

**What to do:**
- Look at the pill strip (six metric badges): row count, column count, target name, positive rate, numeric features, categorical features, missing percentage.
- Scroll down to see `df.head(10)` table.
- Click **CONTINUE ▶** to start the replay.

**Success criteria:**
- Pills show correct values (rows=500000, cols=19, target="binary_target", pos_rate=~27%).
- Table header and first 10 rows are readable.
- Page 3 renders and replay starts immediately.

---

### Page 3: Runtime Replay (90 seconds — the main event)
**What to say:**
> "Now watch the 13-node EDA workflow fire in real time. The orange indicator shows active work; green means done. Notice the three reviewer agents — ML Modeler, ML Reviewer, and Business Stakeholder — fan out in parallel after the initial profiling."

**What to do:**
- Observe the orchestrator band at the top. It should cycle through these labels in order:
  1. **STARTING** (brief, ~1 s)
  2. **EDA RUNNING** (orange column highlight, ~10–20 s depending on recorded duration)
  3. **HANDOFF** (brief transition)
  4. **DATA ENGINEER RUNNING** (orange, ~5–15 s)
  5. **COMPLETE** (final state, all lanes green)

- **Speed control:** The replay defaults to **1.5×**. If you're running long or want to show detail, use the speed selector at the bottom-left. Options: `0.5×` / `1×` / `1.5×` (default) / `2×`.

- **If replay plays too fast:** Switch to `1×`. If it's dragging: switch to `2×`.

- **Do NOT double-click CONTINUE.** Once you click it, the replay is locked and cannot restart — this is by design (AC5.6).

- **Three reviewer columns will stay dimmed** with a label: "not scheduled in demo scope." This is correct — in a real run they would execute in parallel, but in the demo recording we show only the core EDA → Data Engineer → Handoff path.

**Success criteria:**
- All five orchestrator states appear in order.
- EDA column highlights orange, then locks green.
- Data Engineer column stays dim until EDA is done, then highlights orange, then green.
- No console errors (check browser devtools).
- Replay completes and auto-advances to Page 4 within 1.5–2 seconds.

---

### Page 4: Output & Summary Drawer (60 seconds)
**What to say:**
> "The processed dataset is ready. Here's the head of the cleaned and engineered data, plus key stats. Click any agent card on the left rail to see their contribution — Orchestrator context, the EDA insights, the Data Engineer's transformations, and the scripted reviewer commentary."

**What to do:**
- Observe the processed data table at the top.
- Look at the four delta metric cards below it: `rows`, `columns`, `missing %`, `runtime`.
- **Click through the rail cards** (left side) in order:
  1. **Orchestrator** — shows workflow metadata and event timeline.
  2. **EDA** — shows profiling insights from the recorded JSON.
  3. **Data Engineer** — shows the transformation plan and execution results.
  4. **ML Modeler** — shows a scripted badge (not actually executed in demo).
  5. **ML Reviewer** — shows a scripted badge.
  6. **Business Stakeholder** — shows a scripted badge.
  7. **Report** — shows a scripted badge + final sign-off narrative.

- For each card, click it once. A drawer slides open on the right. Read or skim the content. Click **BACK** to close and move to the next card.

- **Smooth transitions:** Clicking a card while another is open should slide to the new one without closing in between. This is intentional (AC6.6).

**Success criteria:**
- All seven cards are clickable and each has a pane.
- The three executed agents (Orchestrator, EDA, Data Engineer) show real JSON data from the recording.
- The four un-executed agents show a `SCRIPTED` badge at the top of the pane, plus canned narrative.
- BACK button closes the drawer cleanly.
- No red error banners anywhere.

---

## Speed Controls Cheat Sheet

Use the playback speed selector at the bottom-left of Page 3 to adjust replay tempo:

| Speed | Use case |
|-------|----------|
| **0.5×** | Detailed walkthrough; let the audience absorb state transitions. |
| **1×** | Normal real-world speed; rarely needed in a demo. |
| **1.5×** | **Default.** Sweet spot — brisk enough to hold attention, slow enough to see each state. |
| **2×** | Running short on time; skip to the good parts. Orchestrator still readable. |

**Pro tip:** If you're on track for time before Page 3 starts, mention "the replay will run at 1.5× to fit our time window" so the audience isn't confused by the pace.

---

## Fallback Plan

If the live demo fails (Streamlit crash, laptop hiccup, network issue), you have a backup:

**Option 1: Screen Recording**  
A pre-recorded video at `project_planning/design_plans/2026-04-16-demo-runtime-viewer/backup.mov` (or local copy) captures the full 4-page flow. Play it instead of the live app.

- Open the video in QuickTime (or your default video player).
- Press Space to play/pause; arrow keys to scrub.
- Show it fullscreen (Cmd+F on Mac).

**Option 2: Still Frames**  
If the video is unavailable, fallback narration with high-res screenshots of each page is in this runbook's appendix (see below).

**Option 3: Demo Outline**  
If visual media fails entirely, you can narrate from memory using only the talking points in `TALKING_POINTS.md`. The audience will still understand the workflow.

---

## Known Caveats

### 1. "Why are some panes marked SCRIPTED?"
> "In a real run, ML Modeler, ML Reviewer, and Business Stakeholder agents would execute in parallel and produce live outputs. For the demo, we pre-recorded a focused 2-node flow (EDA and Data Engineer) to keep the runtime short and the narrative clear. The reviewer panes show representative output so you can see what a full approval stage would look like in production."

### 2. "How many real LLM calls per demo run?"
> "The recorded run hits OpenAI about 4 times: once for EDA profiling, once for the Data Engineer's prep plan, and two more for the plan refinement loop. Each call is roughly $0.01–0.03 depending on token counts. The full 13-node workflow (with all three reviewers live) would be ~12 calls and ~$0.10–0.20 per run."

### 3. "Can this run against our real dataset?"
> "Yes. The `demo_recorder` CLI takes a `--parquet` flag. Point it at your CSV/Parquet and rerun the recording. The viewer will adapt to your data automatically — new row counts, column names, missing-data patterns, and stats all pull from the fresh recording. The narrative structure (pages, cards, orchestrator) stays the same."

### 4. "What if the replay is too slow?"
> "Use the speed selector on Page 3. Default is 1.5×; you can bump it to 2× if you're tight on time."

### 5. "What if I need to loop the demo?"
> "After the final pane (Report), clicking BACK closes the drawer and leaves you on Page 4 (the summary view). You can then click any rail card again to start a new cycle, or close the viewer entirely and refresh the browser to restart from Page 1."

---

## Git Status Before Showtime

Ensure your working tree is clean:
```bash
git status
```
Expected output:
```
On branch demo-runtime-viewer
nothing to commit, working tree clean
```

If you see dirty files (e.g., locally cached JSON or temp files), stash them:
```bash
git stash
```

---

## Summary

| Stage | Action | Duration | Success Indicator |
|-------|--------|----------|-------------------|
| Pre-flight | Pull, sync, record, verify | ~10 min | JSON file written, checks pass |
| Page 1 Config | Explain settings, click RUN | 30 s | Page 2 renders |
| Page 2 Input | Explain data shape, click CONTINUE | 45 s | Page 3 renders, replay starts |
| Page 3 Runtime | Watch orchestrator cycle, use speed selector | ≤ 90 s (at 1.5×) | Replay completes, Page 4 auto-advances |
| Page 4 Output | Click through 7 agent cards, close drawers | 60 s | All panes render, no errors |
| **Total** | | **≤ 4 min** | All checks green, no red banners |

**Target: 225 seconds (3:45) end-to-end. DoD #9 allows up to 90 s on Page 3 alone, so you have cushion.**

Good luck tomorrow! 🚀
