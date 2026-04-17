# Demo Runtime Viewer Implementation Plan — Phase 7

**Goal:** Rehearse the full four-screen flow end-to-end against a real recording, measure total elapsed time, capture a browser-side screen recording as a same-day fallback, and land a final AC-coverage report. No new production code is written in this phase.

**Architecture:** Operational only. Runs the recorder once to refresh `demo_run_latest.json`, starts Streamlit, walks the tab sequence with a stopwatch, records the viewport via the OS-level screen recorder, and files the resulting assets next to the design plan for easy retrieval the next morning.

**Tech Stack:** Existing stack from Phases 1–6. One new asset is produced — a screen recording at `project_planning/design_plans/2026-04-16-demo-runtime-viewer/backup.mov` (or `.webm` / `.mp4` depending on the recorder on the Mac). This directory does not yet exist but is inside `project_planning/design_plans/` which is already registered in `PROJECT_TREE.md` by Phase 1.

**Scope:** Phase 7 of 7 from `2026-04-16-demo-runtime-viewer.md`.

**Codebase verified:** 2026-04-16. Phases 1–6 produce: `pyproject.toml` with pyarrow, `demo_recorder.py`, `demo_viewer.html`, `demo_viewer_loader.py`, `tests/unit/test_demo_tab_inject.py`, and the Demo tab in `app.py`. No further code edits in this phase. `data/interim/` is a runtime-only directory (Phase 1 registered it in `PROJECT_TREE.md`; gitignored). Backup recording asset dir must be added to `PROJECT_TREE.md` *if* we decide to check the video in — see Task 3 for the decision point.

---

## Acceptance Criteria Coverage

This phase re-verifies the full chain against real artifacts:

### demo-runtime-viewer.AC1: Recording (end-to-end)
- **demo-runtime-viewer.AC1.1 Success:** `demo_recorder.py --output data/interim/demo_run_latest.json` produces a JSON with the four required events.

### demo-runtime-viewer.AC5 / AC6: Runtime + Summary
- Full run-through, 1.5× replay, no console errors, all seven drawer panes functional.

### Operational verification (phase 7 only, implicit in DoD #9):
Rehearsal-level verification of timing target <90s (DoD #9) and the 'backup video' paragraph in Additional Considerations (design plan line 276). No new AC identifiers.

**Note:** This phase does not add new automated tests. Verification is operational — a stopwatch, a browser, and a screen recorder.

---

<!-- START_TASK_1 -->
### Task 1: Fresh recording and artifact sanity check

**Active role:** `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` for load-bearing decisions within this task.

**Files:**
- Writes (runtime, not tracked): `data/interim/demo_run_latest.json`
- No source-code changes.

**Implementation:**
Before rehearsing, re-record so the backup JSON has the most recent settings snapshot. Confirm the recorder's output matches every AC1 case one more time.

**Step 1: Confirm environment**

```bash
# OPENAI_API_KEY must be set (AC1.5 guard will fire otherwise).
test -n "$OPENAI_API_KEY" && echo "OPENAI_API_KEY is set" || echo "MISSING: export OPENAI_API_KEY before recording"

# Parquet must exist (AC1.4 guard).
ls -l data/raw/synthetic_dataset.parquet
```

Both must be OK before proceeding.

**Step 2: Record**

```bash
time uv run python -m multi_agent_ds.orchestration.demo_recorder \
  --output data/interim/demo_run_latest.json \
  --parquet data/raw/synthetic_dataset.parquet
```

Expected: completes in under ~60 s on the demo laptop (depends on OpenAI latency). Exit code 0. Prints the resolved output path.

**Step 3: Sanity-check the JSON**

```bash
uv run python - <<'PY'
import json, pathlib
p = pathlib.Path("data/interim/demo_run_latest.json")
log = json.loads(p.read_text())

assert "recorded_at" in log, "recorded_at missing"
assert "duration_ms" in log and isinstance(log["duration_ms"], int), "duration_ms missing or wrong type"
assert "config" in log and "events" in log and "artifacts" in log
events = log["events"]

# AC1.1: all four canonical events present.
required = [
    ("node_start", "eda_raw"),
    ("node_end",   "eda_raw"),
    ("node_start", "data_engineer"),
    ("node_end",   "data_engineer"),
]
seen = {(e["kind"], e["node"]) for e in events}
missing = [r for r in required if r not in seen]
assert not missing, f"missing required events: {missing}"

# AC1.2: required artifacts.
arts = log["artifacts"]
for key in ("raw_eda_insights", "prep_plan", "processed_df_head",
            "input_df_head", "input_df_stats"):
    assert key in arts, f"artifacts.{key} missing"

# AC1.3: every event has ts and elapsed_ms.
for i, e in enumerate(events):
    assert "ts" in e and isinstance(e["ts"], str), f"event[{i}].ts missing"
    assert "elapsed_ms" in e and isinstance(e["elapsed_ms"], int), f"event[{i}].elapsed_ms missing"

print(f"ok — {len(events)} events, duration {log['duration_ms']} ms, recorded_at {log['recorded_at']}")
PY
```

Expected: prints the `ok — ...` line. Any `AssertionError` here is a regression in Phase 2 — loop back and fix before the rehearsal.

**Step 4: Report**

No commit. Report the JSON file size, event count, and duration as the slice-summary validation line.
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: End-to-end rehearsal with stopwatch

**Active role:** `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` for load-bearing decisions within this task.

**Files:**
- No files changed.

**Implementation:**
Walk the full flow once, timing it. Target is <90 seconds per DoD #9. The replay engine defaults to 1.5×; honor that.

**Step 1: Start Streamlit**

```bash
uv run streamlit run src/multi_agent_ds/app.py --server.headless false --server.port 8591
```

Expected: Streamlit opens a browser tab at `http://localhost:8591/`.

**Step 2: Click through the flow with a stopwatch running**

Start the clock when clicking the **Demo** tab. Expected navigation:

1. Demo tab → iframe loads (~1 s).
2. Page 1 (Config) renders. Click **RUN ▶** → Page 2.
3. Page 2 (Input Preview) renders with pill strip + `df.head(10)`. Click **CONTINUE ▶** → Page 3.
4. Page 3 (Runtime) animates for ~`duration_ms / 1.5` ≈ 20–40 s depending on the recorded run length. Orchestrator cycles STARTING → EDA RUNNING → HANDOFF → DATA ENGINEER RUNNING → COMPLETE.
5. Auto-advance to Page 4 after the final event (+ 600 ms grace).
6. Click through all seven rail cards. Confirm each pane renders correctly (recorded vs. scripted). Click BACK after each.

Stop the clock when the final card's pane is visible. Note the total elapsed time.

**Step 3: Record observations**

For each of the following, note `PASS` / `FAIL`:

- [ ] Total elapsed ≤ 90 s.
- [ ] No red error banner anywhere in Streamlit.
- [ ] Browser devtools console shows zero errors across all pages.
- [ ] All five orchestrator state labels appeared in order (Phase 4 AC5.1).
- [ ] EDA column highlighted orange then green (AC5.2).
- [ ] Data Engineer column gated behind EDA end (AC5.3).
- [ ] ML Modeler / ML Reviewer / Business Stakeholder columns stayed dimmed with scope label (AC5.4).
- [ ] Speed selector defaulted to 1.5× (AC5.5).
- [ ] Clicking CONTINUE twice did not restart playback (AC5.6).
- [ ] All seven rail cards opened their respective panes (AC6.2, AC6.3).
- [ ] Recorded panes showed real JSON; scripted panes showed SCRIPTED badge (AC6.4, AC6.5).
- [ ] BACK closed the drawer; card-to-card swap was smooth (AC6.6).

**Step 4: If anything failed**

Loop back to the phase that owns that AC (Phase 4 for AC5, Phase 5 for AC6). Do not file the failure as a new phase — it's a defect in an existing one.

**Step 5: No commit in this task**

Report the stopwatch total and the pass/fail table in the end-of-slice summary.
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: Capture backup screen recording

**Active role:** `commit_chronicler` and `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/commit-chronicler.md` and `.claude/agents/plan-guardian.md` for load-bearing decisions within this task.

**Files:**
- May create: `project_planning/design_plans/2026-04-16-demo-runtime-viewer/backup.mov` (OR an equivalent, depending on OS recorder)
- May modify: `project_planning/PROJECT_TREE.md` (only if the recording is checked in)

**Implementation:**
A screen recording is the **fallback** for demo day — if Streamlit, the laptop, or the network misbehaves, the presenter plays the video instead of the live app. The recording should cover the same end-to-end flow from Task 2.

**Two options for where the file lives:**

1. **Checked in** (max reliability; costs repo size). Put the file under `project_planning/design_plans/2026-04-16-demo-runtime-viewer/` (new subdir) and register it in `PROJECT_TREE.md`. A ~30 MB .mov is tolerable for a one-off demo asset.
2. **Local-only** (cleaner repo). Put the file under `data/interim/` (already runtime-only per `.gitignore`) or the user's Desktop. No `PROJECT_TREE.md` edit.

Ask the user which before writing the file:

> "Demo backup recording: check into `project_planning/design_plans/2026-04-16-demo-runtime-viewer/` (survives laptop wipe, adds ~30 MB to repo) or keep local-only at `data/interim/` (cleaner repo, less safety net)?"

**Step 1: Capture the video**

On macOS:

```bash
# Built-in screen recorder: Cmd+Shift+5 → "Record Selected Portion" → draw a rectangle
# around the Streamlit window → start → click through the flow → stop → save.
# Resulting file is a .mov, usually ~15–30 MB for a 90 s recording at 1080p.
```

Rename the saved file to `demo_backup_2026-04-16.mov`.

**Step 2: Route to the chosen location**

If option 1 (checked in):

```bash
mkdir -p project_planning/design_plans/2026-04-16-demo-runtime-viewer
mv ~/Desktop/demo_backup_2026-04-16.mov project_planning/design_plans/2026-04-16-demo-runtime-viewer/demo_backup_2026-04-16.mov
ls -lh project_planning/design_plans/2026-04-16-demo-runtime-viewer/
```

Update `PROJECT_TREE.md` to include the new subdir and the video file. One `Edit` call.

If option 2 (local-only):

```bash
mkdir -p data/interim
mv ~/Desktop/demo_backup_2026-04-16.mov data/interim/demo_backup_2026-04-16.mov
# data/interim/ is already gitignored per repo convention; no PROJECT_TREE edit needed.
```

**Step 3: Verify the file plays**

```bash
# Open the file with the default app (macOS):
open <path-to-mov>
# Or check the duration/size with ffprobe if available:
which ffprobe && ffprobe -v error -show_entries format=duration,size -of default=nw=1 <path-to-mov> || true
```

Expected: video opens in QuickTime and plays the full flow.

**Step 4: Commit (option 1 only)**

If the recording is checked in:

```bash
git status
git add project_planning/design_plans/2026-04-16-demo-runtime-viewer/demo_backup_2026-04-16.mov project_planning/PROJECT_TREE.md
git commit -m "chore(demo): add demo backup screen recording

why: DoD #9 — a rehearsed end-to-end run must complete and we
keep a backup recording alongside demo materials in case the
live flow fails the morning of.

architecture fit: stored next to the design plan; PROJECT_TREE
updated per AC7.3.

validation: recording plays back the full four-screen flow in
QuickTime. No Streamlit errors during capture.

notes: ~XX MB .mov. Swap to option 2 (local-only) if repo size
becomes a concern.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

If option 2 (local-only), no commit. Note the file path in the slice summary so future Sean knows where to find it.
<!-- END_TASK_3 -->

<!-- START_TASK_4 -->
### Task 4: Final AC-coverage report

**Active role:** `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` for load-bearing decisions within this task.

**Files:**
- No files changed.

**Implementation:**
Produce the final traceability matrix: every AC in the design plan → which phase implemented it → pass/fail at the rehearsal. Present this as the closing output of the whole branch.

**Step 1: Fill the matrix**

| AC | Text (abbrev.) | Implementing Phase | Verification | Status |
|----|----------------|--------------------|--------------|--------|
| AC1.1 | Four canonical events recorded | 2 | Task 1 script | |
| AC1.2 | Required artifacts present | 2 | Task 1 script | |
| AC1.3 | Every event has ts + elapsed_ms | 2 | Task 1 script | |
| AC1.4 | FileNotFoundError on bad parquet | 2 | Phase 2 Task 8 | |
| AC1.5 | EnvironmentError on missing key | 2 | Phase 2 Task 8 | |
| AC1.6 | Atomic replace on re-record | 2 | Phase 2 Task 8 | |
| AC2.1 | Demo entry in app.py | 6 | Task 2 rehearsal | |
| AC2.2 | JSON injected as window.DEMO_LOG | 6 | Task 2 rehearsal | |
| AC2.3 | Missing-JSON error path | 6 | Phase 6 Task 3 Step 3 | |
| AC3.1 | Page 1 shows config values | 3 | Task 2 rehearsal | |
| AC3.2 | RUN advances to Page 2 | 3 | Task 2 rehearsal | |
| AC4.1 | Page 2 shows head + pills | 3 | Task 2 rehearsal | |
| AC4.2 | CONTINUE advances to Page 3 | 3 | Task 2 rehearsal | |
| AC5.1 | Orchestrator state labels | 4 | Task 2 rehearsal | |
| AC5.2 | EDA column orange → green | 4 | Task 2 rehearsal | |
| AC5.3 | DE gated behind EDA end | 4 | Task 2 rehearsal | |
| AC5.4 | Un-executed agents dimmed | 4 | Task 2 rehearsal | |
| AC5.5 | Speed selector default 1.5× | 4 | Task 2 rehearsal | |
| AC5.6 | Double-CONTINUE no-op | 4 | Task 2 rehearsal | |
| AC6.1 | Processed df + delta cards | 5 | Task 2 rehearsal | |
| AC6.2 | Seven-card rail | 5 | Task 2 rehearsal | |
| AC6.3 | Slider transform on click | 5 | Task 2 rehearsal | |
| AC6.4 | Recorded panes from JSON | 5 | Task 2 rehearsal | |
| AC6.5 | SCRIPTED badge on four panes | 5 | Task 2 rehearsal | |
| AC6.6 | BACK + card swap | 5 | Task 2 rehearsal | |
| AC7.1 | pyarrow declared | 1 | Phase 1 Task 1 | |
| AC7.2 | No new top-level dirs | 1/2/3/6 | `uv run python -c "import pathlib; p=pathlib.Path('.'); expected={'data','docs','config','src','tests','notebooks','project_planning','development_agents','scripts','.claude','.git','.github'}; actual={d.name for d in p.iterdir() if d.is_dir()}; extra=actual-expected; assert not extra, f'Unexpected top-level dirs: {extra}'"` | |
| AC7.3 | PROJECT_TREE.md updated | 1 | Phase 1 Task 2 | |
| AC7.4 | No agents/graph.py edits | 2 | `git diff main -- src/multi_agent_ds/agents src/multi_agent_ds/orchestration/graph.py` is empty | |

Fill the **Status** column as the final walkthrough happens. Expected end state: every row is `PASS`.

**Step 2: Present the matrix in the final slice summary**

The summary for this phase must include the matrix above in full. Any `FAIL` row triggers a fix loop in the relevant earlier phase — not a new phase.

**Step 3: Announce demo readiness (or not)**

If all rows pass: "Demo is ready. Recorded JSON at `data/interim/demo_run_latest.json`, backup recording at `<path>`."

If anything fails: "Demo needs fixes in Phase N before rehearsal. Failures: AC…, AC…"

No commit in this task.
<!-- END_TASK_4 -->

## Phase 7 Done-When

- [ ] A fresh recording exists and passes the Task 1 sanity script.
- [ ] End-to-end rehearsal completes in ≤ 90 s with no console errors.
- [ ] Backup screen recording saved at the chosen location.
- [ ] AC traceability matrix shows all rows as `PASS`.
- [ ] At most one commit landed (Task 3, only if the video is checked in). Tasks 1, 2, 4 are operational and produce no commits.
