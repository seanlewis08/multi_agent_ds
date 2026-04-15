<p align="center">
  <h1 align="center">🔬 Multi-Agent DS Pipeline</h1>
  <p align="center">
    A multi-agent data science framework for automated ML experimentation — with deterministic synthetic data generation, phased hyperparameter tuning, and full MLflow observability.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
  <img src="https://img.shields.io/badge/package_manager-uv-blueviolet" alt="uv">
  <img src="https://img.shields.io/badge/tracking-MLflow-0194E2" alt="MLflow">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Codex Skills](#codex-skills)
- [Plans And Agent Workflow](#plans-and-agent-workflow)
- [Command Reference](#command-reference)
  - [Streamlit Dashboard](#streamlit-dashboard)
  - [Generate Synthetic Data](#generate-synthetic-data)
  - [Run Modeling Workflow](#run-modeling-workflow)
  - [MLflow UI](#mlflow-ui)
  - [S3 Upload / Download](#s3-upload--download)
  - [Tests & Linting](#tests--linting)
- [Configuration](#configuration)
- [Architecture](#architecture)

---

## Overview

This project implements a **multi-agent ML pipeline** for binary classification on insurance data. It includes:

- **Deterministic synthetic data generation** with known ground-truth coefficients
- **Phased model training** — baseline → n_estimators search → Optuna tuning → learning rate adjustment → feature selection
- **Dual-output artifacts** — structured JSON for LLM agents + PNG visuals for human review
- **MLflow tracking** with SQLite backend, nested runs, and auto-generated diagnostic artifacts
- **Streamlit dashboard** for interactive experimentation

---

## Project Structure

```
multi_agent_ds/
├── config/
│   ├── settings.yaml          # Central pipeline configuration
│   ├── agents.yaml            # Agent definitions
│   ├── prompts.yaml           # Agent prompts
│   └── workflows.yaml         # Workflow definitions
├── data/
│   └── raw/                   # Generated / input datasets
├── notebooks/
│   └── EDA.ipynb              # Exploratory data analysis
├── reports/                   # Auto-generated experiment logs (markdown)
├── src/multi_agent_ds/
│   ├── app.py                 # Streamlit dashboard
│   ├── agents/                # Agent implementations
│   ├── adapters/              # LLM & framework adapters
│   ├── core/                  # Config loading, context, contracts
│   ├── orchestration/         # LangGraph state & routing
│   ├── skills/                # ML skills (modeling, cleaning, etc.)
│   ├── tools/                 # Deterministic utilities
│   │   ├── artifacts.py       # Artifact generation (JSON + PNG)
│   │   ├── data_generator.py  # Synthetic data generation
│   │   ├── evaluation.py      # Scoring & test-set evaluation
│   │   ├── io.py              # S3 upload / download
│   │   └── reporting.py       # Markdown experiment logger
│   └── workflows/             # End-to-end workflow orchestration
│       └── modeling.py        # Baseline modeling workflow
├── tests/                     # Unit & integration tests
├── pyproject.toml
└── uv.lock
```

---

## Setup

### Prerequisites

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** package manager

### Install

```bash
# Clone the repository
git clone <repo-url>
cd multi_agent_ds

# Install all dependencies (including dev)
uv sync
```

### Environment Variables

Create a `.env` file in the project root for any API keys or credentials:

```env
OPENAI_API_KEY=sk-...
AWS_PROFILE=your-profile    # optional, for S3 access
```

---

## Codex Skills

This repo includes Codex skill definitions under [`development_agents/codex_skills`](development_agents/codex_skills). These are repo-specific working rules for architecture placement, planning alignment, commit hygiene, and script approval.

### Install For A User

Copy the generated skill folders into the user's Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R development_agents/codex_skills/* ~/.codex/skills/
```

### Pick Up New Skills

Restart Codex after copying the folders. New sessions will then load the installed skills and they can appear in the session skill list when relevant.

### Update Workflow

If the local source files in [`development_agents/skills`](development_agents/skills) change:

1. update the corresponding Codex skill folder in [`development_agents/codex_skills`](development_agents/codex_skills)
2. copy the updated folder into `~/.codex/skills`
3. restart Codex

---

## Plans And Agent Workflow

Use the planning docs in `project_planning/` before making changes:

- `project_planning/Sean_Plan.md` for Sean-owned work on shared infrastructure, orchestration, upstream pipeline steps, and Sean's agent path.
- `project_planning/Jonathan_Plan.md` for Jonathan-owned work on evaluation, orchestrator/reviewer flows, git or PR tooling, and Jonathan's agent path.
- `project_planning/BUILD_PLAN.md` for the full sequence and current build step.
- `project_planning/PROJECT_TREE.md` and `project_planning/ARCHITECTURE.md` for where code should live before adding files or helpers.

When coding with agent teams, use the development-agent docs in `development_agents/` as the operating contract:

1. Start with `development_agents/checklist.md`.
2. Use `development_agents/team.md` to route the work through `plan_guardian`, `architecture_guard`, `implementation_engineer`, `efficiency_reviewer`, and `commit_chronicler`.
3. Load only the skills that match the task, especially plan alignment, architecture fit, efficiency review, safe staging, and commit confirmation.

General expectations while coding:

- Prefer extending an existing module before adding a new file, helper, script, or entrypoint.
- Keep import direction aligned with the repo architecture: `orchestration -> workflows -> agents -> skills -> tools`.
- Watch for code bloat: remove duplicate logic, avoid one-off wrappers, and do not create sidecar scripts when the behavior belongs in an existing workflow or module.
- Keep `skills/` pure and push side effects into workflows, tools, or adapters where the architecture expects them.
- Use effective unit-level commits: one coherent implementation slice per commit, with relevant verification for that slice.
- Before each commit, review `git status`, stage only the intended files, and avoid bundling unrelated local changes.
- At the end of implementation work, explicitly decide whether to commit and push the completed unit instead of letting edits accumulate.

Example prompts for using Codex with the repo's plan and development-agent team:

```text
Use agent teams for this task and follow Sean's plan.
```

```text
Use agent teams for this task and follow Jonathan's plan.
```

```text
Use agent teams for this coding task and keep the implementation tight.
```

```text
Use agent teams to inspect this area for code bloat and condense it before adding new code.
```

---

## Command Reference

All commands use `uv run` to execute within the project's virtual environment.

### Streamlit Dashboard

The interactive UI for running experiments, viewing results, and managing MLflow.

```bash
uv run streamlit run src/multi_agent_ds/app.py
```

Opens at **http://localhost:8501**. Features:
- Configure algorithms, metrics, CV folds, and tuning parameters
- Run baseline workflows with one click
- Auto-starts MLflow UI after each run
- View results, score comparisons, and experiment logs

---

### Generate Synthetic Data

Generate a synthetic insurance dataset with deterministic ground-truth probabilities.

```bash
uv run python -c "from multi_agent_ds.core import load_settings; from multi_agent_ds.tools.data_generator import generate_synthetic_data, save_local; df = generate_synthetic_data(load_settings()); save_local(df)"
```

- Reads configuration from `config/settings.yaml` (data section)
- Outputs `data/raw/synthetic_dataset.parquet`
- Only runs when `data.source: synthetic` is set in settings
- Keeps generation as a library tool instead of a separate CLI entrypoint

---

### Run Modeling Workflow

Run the baseline modeling pipeline from the command line with MLflow logging.

```bash
# Run with all defaults (all algorithms from settings.yaml)
uv run python -m multi_agent_ds.workflows.modeling

# Specify the data file
uv run python -m multi_agent_ds.workflows.modeling --data-path data/raw/my_dataset.parquet

# Run only specific algorithms
uv run python -m multi_agent_ds.workflows.modeling --algorithms lightgbm

# Run both with a named MLflow run
uv run python -m multi_agent_ds.workflows.modeling --algorithms lightgbm logistic_regression --run-name baseline_v2

# Full example
uv run python -m multi_agent_ds.workflows.modeling \
  --data-path data/raw/synthetic_dataset.parquet \
  --algorithms lightgbm \
  --run-name "lgbm_only_test"
```

**Arguments:**

| Flag | Default | Description |
|------|---------|-------------|
| `--data-path` | `data/raw/synthetic_dataset.parquet` | Path to the input parquet file |
| `--algorithms` | All from `settings.yaml` | Space-separated list of algorithms to train |
| `--run-name` | `experiment` | Name for the parent MLflow run |

**Output:**
- Logs metrics, params, model artifacts, and diagnostic visuals to MLflow
- Writes a markdown experiment report to `reports/`
- Prints a results summary to the terminal

---

### MLflow UI

View experiment tracking data in the MLflow web interface.

```bash
# Start the MLflow UI (SQLite backend)
uv run mlflow ui --backend-store-uri sqlite:///mlruns.db --port 5000
```

Opens at **http://localhost:5000**. The MLflow UI also starts automatically from the Streamlit dashboard after each run.

---

### S3 Upload / Download

Transfer data files to and from S3. Requires AWS credentials (via `AWS_PROFILE` in settings or environment).

```bash
# Upload a local file to S3
uv run python -c "from multi_agent_ds.tools.io import upload_to_s3; print(upload_to_s3('<local_path>', '<path_key>', '<filename>'))"

# Download a file from S3
uv run python -c "from multi_agent_ds.tools.io import download_from_s3; print(download_from_s3('<path_key>', '<filename>', '<local_dir>'))"
```

**Examples:**

```bash
# Upload the synthetic dataset
uv run python -c "from multi_agent_ds.tools.io import upload_to_s3; print(upload_to_s3('data/raw/synthetic_dataset.parquet', 'raw', 'synthetic_dataset.parquet'))"

# Download a dataset to a custom directory
uv run python -c "from multi_agent_ds.tools.io import download_from_s3; print(download_from_s3('raw', 'real_dataset.parquet', 'data/raw'))"
```

The `path_key` maps to paths configured in `config/settings.yaml` under `s3.paths`.

---

### Tests & Linting

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=multi_agent_ds

# Lint
uv run ruff check src/

# Format
uv run ruff format src/

# Type check
uv run mypy src/
```

---

## Configuration

All pipeline settings live in **`config/settings.yaml`**. Key sections:

| Section | Controls |
|---------|----------|
| `data` | Data source (synthetic vs. existing), generation parameters, feature definitions |
| `model` | Algorithms, CV folds, test size, scoring metrics, tuning budget |
| `mlflow` | Experiment name, tracking URI (`sqlite:///mlruns.db`), artifact location |
| `s3` | Bucket, prefix, paths, AWS profile |
| `llm` | LLM provider and model configuration for agents |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit App                         │
│               (app.py — interactive UI)                  │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │    Workflows    │     ← orchestration + MLflow logging
              │  (modeling.py)  │
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼────┐  ┌─────▼─────┐  ┌───▼────┐
    │  Skills │  │   Tools   │  │ Agents │
    │modeling │  │evaluation │  │ml_model│
    │cleaning │  │artifacts  │  │eda_anal│
    │ profil. │  │reporting  │  │data_eng│
    └─────────┘  │data_gen   │  └────────┘
                 │   io      │
                 └───────────┘
                       │
              ┌────────▼────────┐
              │   Core Layer    │     ← config, context, contracts
              │  (settings.yaml)│
              └─────────────────┘
```

- **Workflows** orchestrate the full pipeline and handle MLflow logging
- **Skills** execute ML operations (training, tuning, feature selection)
- **Tools** are stateless utilities (scoring, artifact generation, data I/O)
- **Agents** wrap skills with LLM-driven decision logic
- **Core** provides configuration loading and shared contracts

---

## License

MIT — see [LICENSE](LICENSE).
