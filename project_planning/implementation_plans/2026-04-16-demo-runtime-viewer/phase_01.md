# Demo Runtime Viewer Implementation Plan — Phase 1

**Goal:** Unblock parquet reads and PROJECT_TREE hygiene before any new code is written.

**Architecture:** Infrastructure-only phase. No functional code. One new runtime dependency (`pyarrow>=18.0.0`) and three planning-doc updates (`PROJECT_TREE.md`, `BUILD_PLAN.md` note for step 5d, no change to `FUTURE_WORK.md`).

**Tech Stack:** `uv` (PEP 621 `pyproject.toml`), `pandas<3`, `pyarrow>=18.0.0`.

**Scope:** Phase 1 of 7 from `2026-04-16-demo-runtime-viewer.md`.

**Codebase verified:** 2026-04-16. `pyarrow` is not currently declared in `pyproject.toml:8-34`. `uv.lock` exists (1.3 MB, revision 3). Python is pinned to `>=3.11`. `project_planning/PROJECT_TREE.md` does not yet list `design_plans/` or `implementation_plans/` subdirs. `project_planning/BUILD_PLAN.md` does not mention the demo viewer. `data/raw/synthetic_dataset.parquet` exists at 39 MB.

---

## Acceptance Criteria Coverage

This phase implements and verifies:

### demo-runtime-viewer.AC7: Repo hygiene
- **demo-runtime-viewer.AC7.1 Success:** `pyarrow>=18.0.0` is declared in `pyproject.toml`. `uv sync` succeeds.
- **demo-runtime-viewer.AC7.3 Success:** `project_planning/PROJECT_TREE.md` is updated in the same commit as any new path it introduces.

**Verifies: None of the functional ACs** (infrastructure phase — no functional behavior). AC coverage for AC7.1 / AC7.3 is operational, not test-backed.

---

<!-- START_TASK_1 -->
### Task 1: Add pyarrow to pyproject.toml

**Active role:** `plan_guardian` — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan_guardian.md` for load-bearing decisions within this task.

**Files:**
- Modify: `pyproject.toml` at the `[project].dependencies` list (insertion point is alphabetically after `pandas<3`, currently line 22)

**Implementation:**
Open `pyproject.toml` and add a single line to the `dependencies` array. The existing format is PEP 508 specifiers inside a TOML list, one per line, with a trailing comma. Insert after the line containing `"pandas<3",`:

```toml
    "pyarrow>=18.0.0",
```

Do not reorder any other entries. Do not add a comment.

**Step 1: Apply the edit**

Use the `Edit` tool with:
- `old_string` = `    "pandas<3",\n`
- `new_string` = `    "pandas<3",\n    "pyarrow>=18.0.0",\n`

If the `pandas<3` line has different surrounding whitespace, re-read `pyproject.toml:18-34` first and match the exact indentation.

**Step 2: Verify the edit visually**

```bash
grep -n "pyarrow\|pandas" pyproject.toml
```

Expected output includes both `"pandas<3",` and `"pyarrow>=18.0.0",`, each on its own line inside the dependencies array.

**Step 3: Run uv sync**

```bash
uv sync
```

Expected: completes without error. `uv.lock` is updated. New wheel for `pyarrow` is resolved and installed. Exit code 0.

**Step 4: Smoke-test parquet read**

```bash
uv run python -c "import pandas as pd; df = pd.read_parquet('data/raw/synthetic_dataset.parquet'); print(df.shape, list(df.columns)[:5])"
```

Expected: prints the dataframe shape `(500000, 19)` and the first five column names with no `ImportError: Unable to find a usable engine` message.

**Step 5: Commit**

Per the `commit_chronicler` role in `development_agents/team.md`, stage only the intentional changes and ask before committing:

```bash
git status
git diff pyproject.toml uv.lock
```

Confirm `git status` shows only `pyproject.toml` and `uv.lock` changed (no stray files). Ask the user: "Should I commit and push these changes?" Only on explicit yes:

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add pyarrow>=18.0.0 for parquet reads

why: demo_recorder reads data/raw/synthetic_dataset.parquet via
pandas.read_parquet; pandas 2.2.x requires a parquet engine and
pyarrow is the canonical one. pyarrow floor set to 18.0.0 as a
conservative pin.

architecture fit: no layer impact; runtime dep only.

validation: uv sync succeeds; pd.read_parquet smoke test prints
shape (500000, 17).

notes: no .toml format changes besides the single new line.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

Report each git command that was run, in order, per the end-of-slice summary protocol.
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Update PROJECT_TREE.md

**Active role:** `plan_guardian` and `commit_chronicler` on commit steps — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` and `.claude/agents/commit-chronicler.md` for load-bearing decisions within this task.

**Files:**
- Modify: `project_planning/PROJECT_TREE.md` (add entries for `project_planning/design_plans/` and `project_planning/implementation_plans/`, and for the new runtime paths introduced by the design plan)

**Implementation:**
`PROJECT_TREE.md` uses a `├──` / `└──` ASCII tree inside a fenced markdown code block. Read the existing file to see the exact layout. The `project_planning/` entry currently lists only two `.docx` files. We need to add:

1. Under `project_planning/`: two subdirectories — `design_plans/` (contains `2026-04-16-demo-runtime-viewer.md`) and `implementation_plans/` (contains `2026-04-16-demo-runtime-viewer/`).
2. Under `src/multi_agent_ds/`: a new sibling file `demo_viewer.html` (planned).
3. Under `src/multi_agent_ds/orchestration/`: a new sibling file `demo_recorder.py` (planned).
4. Under `src/multi_agent_ds/orchestration/`: a new sibling file `demo_viewer_loader.py` (planned) — pure FCIS helper introduced by Phase 6 that injects the recorded JSON into the viewer HTML. Register it here so Phase 6's new file does not trip the CLAUDE.md approval gate.

Use the suffix `(planned)` consistently for any file not yet created.

Also add a single one-line note at the top of `project_planning/PROJECT_TREE.md`:

```markdown
_Last updated: 2026-04-16 (added demo_viewer.html, demo_recorder.py, demo_viewer_loader.py, design_plans/, implementation_plans/)_
```

Place this note immediately after the file's heading.

**Step 1: Read the current file**

```bash
cat project_planning/PROJECT_TREE.md
```

Observe the existing tree's indentation style (spaces per level) and the `├──` / `└──` / `│  ` glyphs. Match them exactly.

**Note:** Subdirectories under `design_plans/` and `implementation_plans/` are permitted without separate registration; only top-level paths are enumerated in PROJECT_TREE.md.

**Step 2: Apply the edits**

Use a single `Edit` call to insert the new `project_planning/design_plans/` and `project_planning/implementation_plans/` entries in the tree. Use a second `Edit` call to insert `demo_viewer.html` and `demo_recorder.py` entries under `src/multi_agent_ds/` and `src/multi_agent_ds/orchestration/` respectively. Use a third `Edit` call to add the "Last updated" note under the heading.

Preserve alphabetical / structural ordering within each subtree.

**Step 3: Verify the tree renders cleanly**

```bash
head -60 project_planning/PROJECT_TREE.md
```

Expected: markdown renders as a tidy tree. No broken `├──` chains. The "Last updated" line appears directly under the heading.

**Step 4: Commit**

```bash
git status
git diff project_planning/PROJECT_TREE.md
```

Confirm only `PROJECT_TREE.md` is changed. Ask the user: "Should I commit and push these changes?" On yes:

```bash
git add project_planning/PROJECT_TREE.md
git commit -m "docs(project-tree): register demo viewer paths and plan dirs

why: CLAUDE.md approval gate requires PROJECT_TREE.md to list every
path before new files land. Registers demo_viewer.html (planned),
demo_recorder.py (planned), demo_viewer_loader.py (planned),
design_plans/ (present), and implementation_plans/ (present).

architecture fit: documentation only.

validation: head -60 project_planning/PROJECT_TREE.md renders a
clean tree with no broken ├── chains.

notes: (planned) marker used for not-yet-created files.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: Note demo viewer in BUILD_PLAN.md

**Active role:** `plan_guardian` and `commit_chronicler` on commit steps — state aloud at slice start per CLAUDE.md Pre-Edit Checklist.
**Subagent spawn:** use the Agent tool to dispatch `.claude/agents/plan-guardian.md` and `.claude/agents/commit-chronicler.md` for load-bearing decisions within this task.

**Files:**
- Modify: `project_planning/BUILD_PLAN.md` (add a short Step 5d entry noting the demo viewer; do NOT claim completion)

**Implementation:**
`BUILD_PLAN.md` is a step-ordered document. Step 5b is in progress (Streamlit app). Add **Step 5d: Demo runtime viewer** immediately after Step 5c (if it exists) or after Step 5b. The entry should:
- Reference the design plan at `project_planning/design_plans/2026-04-16-demo-runtime-viewer.md`.
- State scope clearly: records `eda_analyst → data_engineer` only; other agents are scripted.
- List the three new files: `demo_recorder.py`, `demo_viewer.html`, `demo_run_latest.json`.
- Mark status as "In progress (Phase 1 of 7)".

**Step 1: Read the current BUILD_PLAN.md**

```bash
grep -n "^### Step" project_planning/BUILD_PLAN.md
```

Identify the step immediately before Step 6 so the new Step 5d lands in the right spot.

**Step 2: Insert Step 5d**

Use `Edit` to insert a new step section above the line beginning `### Step 6`. Content:

```markdown
### Step 5d: Demo runtime viewer

**Status:** In progress (Phase 1 of 7 from `project_planning/design_plans/2026-04-16-demo-runtime-viewer.md`)

**What:** A record-once-replay-many demo viewer. A new `demo_recorder.py` builds a two-node `StateGraph` (`eda_raw → data_engineer → END`), streams `astream_events(version="v2")`, and writes `data/interim/demo_run_latest.json`. A new `demo_viewer.html` replays the recording as four screens (Config → Input → Runtime → Output+Summary) inside the existing `app.py` via `st.components.v1.html`.

**Scope excluded:** `ml_modeler`, `ml_reviewer`, `business_stakeholder`, `report_writer` are NOT executed live in this demo. Their drawer panes show clearly-labeled `SCRIPTED` canned content.

**Files introduced:**
- `src/multi_agent_ds/orchestration/demo_recorder.py`
- `src/multi_agent_ds/demo_viewer.html`
- `data/interim/demo_run_latest.json` (runtime output, not checked in)
```

**Step 3: Verify**

```bash
grep -A 2 "^### Step 5d" project_planning/BUILD_PLAN.md
```

Expected: the new step header and the first two lines print. No duplicate step sections.

**Step 4: Commit**

```bash
git add project_planning/BUILD_PLAN.md
git commit -m "docs(build-plan): add Step 5d for demo runtime viewer

why: BUILD_PLAN is the canonical step tracker. Demo viewer is new
scope that must be registered before implementation begins.

architecture fit: documentation only; no code impact.

validation: grep confirms single '### Step 5d' heading present.

notes: status marked 'In progress (Phase 1 of 7)' — later phases
will flip this as they land.
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
<!-- END_TASK_3 -->

## Phase 1 Done-When

- [ ] `uv sync` succeeds with `pyarrow>=18.0.0` resolved.
- [ ] `pd.read_parquet('data/raw/synthetic_dataset.parquet')` succeeds from a fresh `uv run python -c`.
- [ ] `project_planning/PROJECT_TREE.md` shows `design_plans/`, `implementation_plans/`, `demo_viewer.html` (planned), `demo_recorder.py` (planned), and `demo_viewer_loader.py` (planned) entries.
- [ ] `project_planning/BUILD_PLAN.md` has a Step 5d entry for the demo viewer.
- [ ] Three commits landed (one per task) on branch `demo-runtime-viewer`. No unrelated edits bundled in.
