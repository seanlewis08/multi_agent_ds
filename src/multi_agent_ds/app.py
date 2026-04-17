"""Streamlit UI for the multi-agent DS modeling pipeline.

Run with:
    uv run streamlit run src/multi_agent_ds/app.py

Provides:
    - Sidebar: data path, algorithm selection, all model/tuning config
    - MLflow UI server launcher (auto-starts; banner always visible)
    - Run button that triggers the baseline workflow
    - Progress bar and cleaned live logs during experiment execution
    - Real-time results display with metrics cards and tables
    - Link to the markdown experiment log
"""

from __future__ import annotations

import io
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from multi_agent_ds.core import resolve_tracking_uri

# Read the optional cost-tier override once at module load. The resolver
# downstream reads settings["llm"]["cost_override"]; stashing it in the
# in-memory dict from _build_settings() is sufficient for Streamlit-triggered
# runs. CLI / test runs that use `load_settings()` directly do NOT pick this
# up — that would require touching core.load_settings, which is intentionally
# kept pure (no env side-effects).
_LLM_COST_OVERRIDE = os.getenv("LLM_COST_OVERRIDE")  # None | "cheap" | "moderate" | "expensive"

# ── Page config (must be first Streamlit call) ────────────────────────
st.set_page_config(
    page_title="ML Pipeline Dashboard",
    page_icon="🔬",
    layout="wide",
)

# ── Lazy imports (heavy libs loaded only when needed) ─────────────────

def _import_pipeline():
    """Import pipeline modules. Called only when the user clicks Run."""
    import pandas as pd
    from multi_agent_ds.skills.modeling import ALGORITHM_REGISTRY, prepare_data, train_with_defaults
    from multi_agent_ds.workflows.modeling import run_modeling_workflow
    return pd, ALGORITHM_REGISTRY, prepare_data, train_with_defaults, run_modeling_workflow


# ── Session state defaults ────────────────────────────────────────────

if "mlflow_process" not in st.session_state:
    st.session_state.mlflow_process = None
if "mlflow_port" not in st.session_state:
    st.session_state.mlflow_port = 5000
if "mlflow_tracking_uri" not in st.session_state:
    st.session_state.mlflow_tracking_uri = None
if "mlflow_start_error" not in st.session_state:
    st.session_state.mlflow_start_error = None
if "mlflow_auto_opened_for" not in st.session_state:
    st.session_state.mlflow_auto_opened_for = None
if "results" not in st.session_state:
    st.session_state.results = None
if "data_summary" not in st.session_state:
    st.session_state.data_summary = None
if "run_logs" not in st.session_state:
    st.session_state.run_logs = []


_DEFAULT_TRACKING_URI = resolve_tracking_uri("sqlite:///mlruns.db")


# ── MLflow server management ─────────────────────────────────────────

def _is_mlflow_running() -> bool:
    """Check if our managed MLflow process is still alive."""
    proc = st.session_state.mlflow_process
    if proc is None:
        return False
    return proc.poll() is None


def _port_listener_pids(port: int) -> list[int]:
    """Return PIDs listening on the requested local TCP port."""
    result = subprocess.run(
        ["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return []
    return [int(pid) for pid in result.stdout.splitlines() if pid.strip().isdigit()]


def _stop_port_listeners(port: int) -> None:
    """Terminate listener processes on the configured MLflow UI port."""
    for pid in _port_listener_pids(port):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    time.sleep(1.0)
    for pid in _port_listener_pids(port):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue


def _start_mlflow(port: int, tracking_uri: str, retry_on_conflict: bool = True) -> None:
    """Start a local MLflow UI server as a background subprocess."""
    resolved_tracking_uri = resolve_tracking_uri(tracking_uri)
    env = os.environ.copy()
    # Keep the UI backend explicit instead of inheriting a stale tracking URI.
    env.pop("MLFLOW_TRACKING_URI", None)
    cmd = [
        "uv", "run", "mlflow", "ui",
        "--port", str(port),
        "--backend-store-uri", resolved_tracking_uri,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        preexec_fn=os.setsid,  # own process group for clean shutdown
    )
    st.session_state.mlflow_process = proc
    st.session_state.mlflow_port = port
    st.session_state.mlflow_tracking_uri = resolved_tracking_uri
    st.session_state.mlflow_start_error = None
    # Give the server a moment to bind the port
    time.sleep(1.5)
    if proc.poll() is not None:
        stderr = (proc.stderr.read() if proc.stderr else "")[:4000]
        stdout = (proc.stdout.read() if proc.stdout else "")[:4000]
        combined_output = "\n".join(part for part in (stderr.strip(), stdout.strip()) if part)
        if retry_on_conflict and (
            "Address already in use" in combined_output
            or "Errno 48" in combined_output
        ):
            _stop_port_listeners(port)
            _start_mlflow(port, tracking_uri, retry_on_conflict=False)
            return
        st.session_state.mlflow_start_error = (
            f"MLflow UI exited immediately with code {proc.returncode} "
            f"for backend {resolved_tracking_uri}. {combined_output or 'No startup output.'}"
        )
        st.session_state.mlflow_process = None
        st.session_state.mlflow_tracking_uri = None
        return


def _ensure_mlflow(port: int, tracking_uri: str) -> None:
    """Ensure the managed MLflow UI is running with the requested backend."""
    resolved_tracking_uri = resolve_tracking_uri(tracking_uri)
    listener_pids = _port_listener_pids(port)
    if _is_mlflow_running():
        if (
            st.session_state.mlflow_port == port
            and st.session_state.mlflow_tracking_uri == resolved_tracking_uri
        ):
            return
        _stop_mlflow()
    elif listener_pids:
        # Reclaim the port from any stale MLflow UI started outside this session.
        _stop_port_listeners(port)

    _start_mlflow(port, tracking_uri)


def _stop_mlflow() -> None:
    """Stop the managed MLflow UI server."""
    proc = st.session_state.mlflow_process
    if proc is not None and proc.poll() is None:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    st.session_state.mlflow_process = None
    st.session_state.mlflow_tracking_uri = None
    st.session_state.mlflow_start_error = None
    st.session_state.mlflow_auto_opened_for = None


def _maybe_auto_open_mlflow() -> None:
    """Open the MLflow UI once per active backend/port combination."""
    if not _is_mlflow_running():
        return

    mlflow_url = f"http://localhost:{st.session_state.mlflow_port}"
    open_key = f"{st.session_state.mlflow_tracking_uri}|{st.session_state.mlflow_port}"
    if st.session_state.mlflow_auto_opened_for == open_key:
        return

    components.html(
        f"""
        <script>
        window.open("{mlflow_url}", "_blank");
        </script>
        """,
        height=0,
        width=0,
    )
    st.session_state.mlflow_auto_opened_for = open_key


# ── Log cleaning helpers ──────────────────────────────────────────────

# Patterns that indicate noisy/unwanted log lines
_NOISE_PATTERNS = [
    re.compile(r"FutureWarning:"),
    re.compile(r"ConvergenceWarning:"),
    re.compile(r"warnings\.warn\("),
    re.compile(r"n_iter_i\s*="),
    re.compile(r"https?://scikit-learn\.org"),
    re.compile(r"Increase the number of iterations"),
    re.compile(r"You might also want to scale"),
    re.compile(r"Please also refer to the documentation"),
    re.compile(r"STOP: TOTAL NO\. OF"),
    re.compile(r"^\s*$"),  # blank lines
    re.compile(r"'penalty' was deprecated"),
    re.compile(r"\.venv/lib/python"),  # virtualenv file paths
    re.compile(r"site-packages/"),
    re.compile(r"Use l1_ratio="),
    re.compile(r"`use_container_width`"),
    re.compile(r"Please replace"),
    re.compile(r"will be removed after"),
    re.compile(r"use `width="),
]

# Patterns for lines we DO want to keep
_KEEP_PATTERNS = [
    re.compile(r"^\[[\d:]+\]"),           # timestamped lines like [07:07:04]
    re.compile(r"Phase \d+:"),            # phase headers
    re.compile(r"Baseline training:"),     # tqdm progress
    re.compile(r"═══"),                    # experiment start/end
    re.compile(r"Configured target"),      # target column fallback info
    re.compile(r"✓"),                      # success markers
    re.compile(r"✗"),                      # failure markers
    re.compile(r"Exported \d+ dependencies"),  # mlflow useful info (compact)
]

# MLflow info lines to condense
_MLFLOW_NOISE = [
    re.compile(r"INFO mlflow"),
    re.compile(r"WARNING mlflow"),
    re.compile(r"Detected uv project"),
    re.compile(r"Exported \d+ dependencies via uv"),
    re.compile(r"Successfully exported \d+ requirements"),
    re.compile(r"Skipping package capture"),
    re.compile(r"Attempting to export requirements"),
    re.compile(r"Failed to resolve installed pip"),
    re.compile(r"artifact_path.*is deprecated"),
    re.compile(r"Saving scikit-learn models"),
    re.compile(r"pickle or cloudpickle"),
    re.compile(r"recommended safe alternative"),
    re.compile(r"object serialization mechanism"),
]


def _clean_log_line(line: str) -> str | None:
    """Return a cleaned log line, or None if it should be dropped."""
    stripped = line.strip()
    if not stripped:
        return None

    # Drop known noise
    for pat in _NOISE_PATTERNS:
        if pat.search(stripped):
            return None

    # Drop verbose mlflow lines
    for pat in _MLFLOW_NOISE:
        if pat.search(stripped):
            return None

    # Keep lines that match our keep patterns
    for pat in _KEEP_PATTERNS:
        if pat.search(stripped):
            return stripped

    # Drop tqdm partial updates (contain \r or cursor codes)
    if "\r" in line and "100%" not in line:
        return None

    # Keep anything that survived the filters
    return stripped


def _clean_logs(raw_output: str) -> list[str]:
    """Clean raw captured output into a list of displayable log lines."""
    lines = raw_output.split("\n")
    cleaned = []
    seen = set()
    for line in lines:
        result = _clean_log_line(line)
        if result and result not in seen:
            cleaned.append(result)
            seen.add(result)
    return cleaned


# ═════════════════════════════════════════════════════════════════════
# SIDEBAR — Configuration
# ═════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("Pipeline Configuration")

    # ── Data ──
    st.subheader("Data")
    data_path = st.text_input(
        "Data path (parquet)",
        value="data/raw/synthetic_dataset.parquet",
        help="Path to the input parquet file with features + target column.",
    )

    # ── Algorithms ──
    st.subheader("Algorithms")
    available_algos = ["lightgbm", "logistic_regression"]
    selected_algos = st.multiselect(
        "Select algorithms to run",
        options=available_algos,
        default=available_algos,
        help="Choose which models to train. At least one required.",
    )

    # ── Model settings ──
    st.subheader("Model Settings")
    cv_folds = st.slider("CV folds", min_value=2, max_value=10, value=5)
    test_size = st.slider("Test size", min_value=0.1, max_value=0.4, value=0.2, step=0.05)
    primary_metric = st.selectbox(
        "Primary metric",
        options=["gini", "roc_auc", "f1", "precision", "recall", "accuracy", "ase"],
        index=0,
    )
    scoring_metrics = st.multiselect(
        "Scoring metrics",
        options=["gini", "ase", "roc_auc", "f1", "precision", "recall", "accuracy"],
        default=["gini", "ase", "roc_auc", "f1"],
    )

    # ── Tuning settings ──
    st.subheader("Tuning")
    max_trials = st.number_input("Max Optuna trials", min_value=5, max_value=500, value=50)
    timeout = st.number_input("Timeout (seconds)", min_value=30, max_value=3600, value=300)
    min_improvement = st.number_input(
        "Min improvement threshold",
        min_value=0.001, max_value=0.1, value=0.01, step=0.005, format="%.3f",
    )

    # ── MLflow settings ──
    st.subheader("MLflow")
    run_name = st.text_input(
        "Run name",
        value="",
        help="Name for the parent MLflow run. Leave blank for auto-generated name.",
        placeholder="e.g. baseline_v1",
    )
    experiment_name = st.text_input("Experiment name", value="multi_agent_ds")
    tracking_uri = st.text_input("Tracking URI", value=_DEFAULT_TRACKING_URI)
    mlflow_port = st.number_input("MLflow UI port", min_value=1024, max_value=65535, value=5000)

    _ensure_mlflow(int(mlflow_port), str(tracking_uri))
    _maybe_auto_open_mlflow()

    st.divider()

    # ── MLflow server control in sidebar ──
    mlflow_running = _is_mlflow_running()

    if mlflow_running:
        st.success(f"MLflow UI running on port {st.session_state.mlflow_port}")
        st.caption(f"Tracking URI: `{st.session_state.mlflow_tracking_uri}`")
    else:
        st.info("MLflow UI is starting automatically.")


# ═════════════════════════════════════════════════════════════════════
# AUTO-RECONCILE MLflow on app load
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# BUILD SETTINGS DICT (from sidebar inputs)
# ═════════════════════════════════════════════════════════════════════

def _build_settings() -> dict:
    """Assemble a settings dict from sidebar widget values."""
    return {
        "model": {
            "problem_type": "binary_classification",
            "algorithms": selected_algos,
            "cv_folds": cv_folds,
            "test_size": test_size,
            "primary_metric": primary_metric,
            "scoring_metrics": scoring_metrics,
            "tuning": {
                "max_trials": max_trials,
                "timeout": timeout,
                "min_improvement": min_improvement,
            },
        },
        "mlflow": {
            "experiment_name": experiment_name,
            "tracking_uri": tracking_uri,
        },
        # Forwarded to resolve_model_config via build_adapter. The rest of the
        # llm block (routes, model_matrix, capability_settings) comes from
        # the YAML-loaded settings the pipeline uses internally.
        "llm": {"cost_override": _LLM_COST_OVERRIDE},
    }


# ═════════════════════════════════════════════════════════════════════
# MAIN PANEL
# ═════════════════════════════════════════════════════════════════════

st.title("ML Pipeline Dashboard")

# ── Persistent MLflow banner (always visible in main window) ──────────
if _is_mlflow_running():
    col_status, col_open, col_stop = st.columns([4, 1, 1])
    with col_status:
        st.success(
            (
                f"MLflow UI running on port {st.session_state.mlflow_port} "
                f"for `{st.session_state.mlflow_tracking_uri}`"
            ),
            icon="📊",
        )
    with col_open:
        st.link_button(
            "Open MLflow",
            f"http://localhost:{st.session_state.mlflow_port}",
            use_container_width=True,
        )
    with col_stop:
        if st.button("Stop MLflow", use_container_width=True):
            _stop_mlflow()
            st.rerun()
if st.session_state.mlflow_start_error:
    st.error(st.session_state.mlflow_start_error)

tab_run, tab_results, tab_log = st.tabs(["Run Experiment", "Results", "Experiment Log"])


# ── Tab 1: Run Experiment ─────────────────────────────────────────────

with tab_run:
    st.subheader("Baseline Training")

    if not selected_algos:
        st.warning("Select at least one algorithm in the sidebar.")
    else:
        st.markdown(
            f"**Algorithms:** {', '.join(selected_algos)} · "
            f"**CV folds:** {cv_folds} · "
            f"**Primary metric:** {primary_metric}"
        )

        if st.button("Run Baseline Workflow", type="primary", use_container_width=True):
            settings = _build_settings()

            # Placeholders for progress bar and live logs
            progress_bar = st.progress(0, text="Initializing pipeline...")
            log_container = st.container()

            try:
                progress_bar.progress(5, text="Loading pipeline modules...")
                try:
                    pd, ALGORITHM_REGISTRY, prepare_data, train_with_defaults, run_modeling_workflow = _import_pipeline()
                except ImportError as e:
                    st.error(f"Import error: {e}. Make sure all dependencies are installed.")
                    st.stop()

                progress_bar.progress(10, text=f"Loading data from `{data_path}`...")

                # ── Capture stdout/stderr while running the workflow ──
                captured_stdout = io.StringIO()
                captured_stderr = io.StringIO()

                progress_bar.progress(15, text=f"Training {len(selected_algos)} algorithm(s)...")

                # We run the workflow and capture all output
                original_stdout = sys.stdout
                original_stderr = sys.stderr

                class TeeWriter:
                    """Write to both the original stream and a capture buffer."""
                    def __init__(self, original, capture):
                        self.original = original
                        self.capture = capture
                    def write(self, text):
                        self.original.write(text)
                        self.capture.write(text)
                    def flush(self):
                        self.original.flush()
                        self.capture.flush()

                sys.stdout = TeeWriter(original_stdout, captured_stdout)
                sys.stderr = TeeWriter(original_stderr, captured_stderr)

                try:
                    results = run_modeling_workflow(
                        data_path=data_path,
                        settings=settings,
                        algorithms=selected_algos,
                        run_name=run_name.strip() or None,
                    )
                except FileNotFoundError:
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                    st.error(f"Data file not found: `{data_path}`. Generate data first.")
                    st.stop()
                except Exception as e:
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                    st.error(f"Workflow failed: {e}")
                    st.stop()
                finally:
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr

                progress_bar.progress(90, text="Logging to MLflow...")

                st.session_state.results = results

                # ── Clean and store logs ──
                raw_out = captured_stdout.getvalue() + "\n" + captured_stderr.getvalue()
                cleaned = _clean_logs(raw_out)
                st.session_state.run_logs = cleaned

                # Reconcile the UI backend after each run so the browser sees the same store we logged to.
                progress_bar.progress(95, text="Starting MLflow UI...")
                _ensure_mlflow(int(mlflow_port), str(tracking_uri))

                progress_bar.progress(100, text="✅ Baseline complete!")

            except Exception as e:
                st.error(f"Unexpected error: {e}")
                st.stop()

            st.success(f"Trained {len(results)} algorithm(s). Check the Results tab.")

            # ── Display cleaned logs ──
            if st.session_state.run_logs:
                with log_container:
                    st.subheader("📋 Experiment Log Output")
                    log_text = "\n".join(st.session_state.run_logs)
                    st.code(log_text, language="text")

    # ── Show previous run logs if available ──
    if st.session_state.run_logs and not st.session_state.get("_just_ran"):
        st.divider()
        st.subheader("📋 Last Experiment Log Output")
        log_text = "\n".join(st.session_state.run_logs)
        st.code(log_text, language="text")

    # ── Quick status section ──
    st.divider()
    col_mlflow, col_reports = st.columns(2)

    with col_mlflow:
        if _is_mlflow_running():
            st.caption("Use the main MLflow banner above to open the live tracking UI.")
        else:
            st.info("MLflow UI will start automatically when you run an experiment.")

    with col_reports:
        reports_dir = Path("reports")
        if reports_dir.exists():
            logs = sorted(reports_dir.glob("experiment_log_*.md"), reverse=True)
            if logs:
                st.markdown(f"Latest log: `{logs[0].name}`")
            else:
                st.info("No experiment logs yet.")
        else:
            st.info("No reports directory yet. Run an experiment first.")


# ── Tab 2: Results ────────────────────────────────────────────────────

with tab_results:
    results = st.session_state.results

    if results is None:
        st.info("No results yet. Run an experiment from the first tab.")
    else:
        # ── Pipeline config summary ──
        st.subheader("Pipeline Configuration")
        config_col1, config_col2, config_col3, config_col4 = st.columns(4)
        with config_col1:
            st.metric("CV Folds", cv_folds)
        with config_col2:
            st.metric("Test Size", f"{test_size:.0%}")
        with config_col3:
            st.metric("Primary Metric", primary_metric)
        with config_col4:
            st.metric("Algorithms", len(results))

        # ── Metric cards ──
        st.subheader("Test Scores")
        metric_cols = st.columns(len(results))
        for col, (algo_name, res) in zip(metric_cols, results.items()):
            with col:
                primary_score = res["test_scores"].get(primary_metric, 0)
                st.metric(
                    label=f"{algo_name}",
                    value=f"{primary_score:.4f}",
                    help=f"Test {primary_metric}",
                )

        # ── Detailed comparison table ──
        st.subheader("Score Comparison")

        import pandas as pd

        rows = []
        for algo_name, res in results.items():
            row = {"algorithm": algo_name, "encoding": res.get("encoding", "?"), "time_s": res["elapsed_seconds"]}
            for metric, score in res["test_scores"].items():
                row[f"test_{metric}"] = score
            for metric, score in res["cv_scores"].items():
                row[f"cv_{metric}"] = score
                row[f"cv_std_{metric}"] = res["cv_std"].get(metric, 0)
            rows.append(row)

        df_results = pd.DataFrame(rows)
        st.dataframe(df_results, width="stretch", hide_index=True)

        # ── Per-algorithm details ──
        st.subheader("Details")
        for algo_name, res in results.items():
            with st.expander(f"{algo_name} — params & scores", expanded=False):
                detail_col1, detail_col2, detail_col3 = st.columns(3)
                with detail_col1:
                    st.markdown("**Parameters**")
                    for param, value in res["params_used"].items():
                        st.write(f"- `{param}`: **{value}**")
                with detail_col2:
                    st.markdown("**Test Scores**")
                    for metric, score in res["test_scores"].items():
                        st.write(f"- {metric}: **{score:.4f}**")
                with detail_col3:
                    st.markdown("**CV Scores (mean ± std)**")
                    for metric, score in res["cv_scores"].items():
                        std = res["cv_std"].get(metric, 0)
                        st.write(f"- {metric}: **{score:.4f}** ± {std:.4f}")
                st.caption(
                    f"Encoding: {res.get('encoding', '?')} · "
                    f"Time: {res['elapsed_seconds']:.1f}s · "
                    f"Phase: {res.get('phase', 'baseline')}"
                )


# ── Tab 3: Experiment Log ─────────────────────────────────────────────

with tab_log:
    st.subheader("Experiment Log (Markdown)")

    reports_dir = Path("reports")
    if reports_dir.exists():
        logs = sorted(reports_dir.glob("experiment_log_*.md"), reverse=True)
        if logs:
            selected_log = st.selectbox(
                "Select log file",
                options=logs,
                format_func=lambda p: p.name,
            )
            if selected_log:
                log_content = selected_log.read_text()
                st.markdown(log_content)
        else:
            st.info("No experiment logs found. Run an experiment first.")
    else:
        st.info("No reports directory yet.")


# ── Footer ────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "Multi-Agent DS Pipeline · "
    "Run with: `uv run streamlit run src/multi_agent_ds/app.py`"
)
