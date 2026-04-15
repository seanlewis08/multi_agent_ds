"""Modeling workflow — orchestrates the full pipeline with MLflow logging.

This workflow runs the non-agentic version: baseline → log → done.
The agentic version (agents/ml_modeler.py) will call skills/modeling.py
functions directly with decision logic between each phase.

Observability:
    - MLflow nested runs: parent run per experiment, child runs per phase/algorithm
    - ExperimentLogger: real-time markdown report at reports/experiment_log_<timestamp>.md
    - tqdm progress bars: handled inside skills/modeling.py functions
    - --algorithms CLI arg: override which models to run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.artifacts import download_artifacts

from multi_agent_ds.core import load_settings, resolve_tracking_uri
from multi_agent_ds.skills.modeling import prepare_data, train_with_defaults
from multi_agent_ds.tools.artifacts import generate_run_artifacts
from multi_agent_ds.tools.io import write_json
from multi_agent_ds.tools.reporting import ExperimentLogger

logger = logging.getLogger(__name__)
_MLFLOW_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "mlruns" / "output"


def _safe_output_name(value: str | None, fallback: str = "run") -> str:
    """Normalize a run name into a stable filesystem directory name."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or fallback


def _format_timestamp(timestamp_ms: int | None = None) -> str:
    """Format a filesystem-safe UTC timestamp."""
    if timestamp_ms is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d_%H%M%S")


def _ensure_unique_directory(path: Path) -> Path:
    """Create a directory, appending a numeric suffix when the target already exists."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return path

    index = 2
    while True:
        candidate = path.with_name(f"{path.name}__{index}")
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        index += 1


def _resolve_output_dir(run_name: str | None, run_id: str) -> Path:
    """Return a unique human-readable export directory for one parent MLflow run."""
    _MLFLOW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return _ensure_unique_directory(_MLFLOW_OUTPUT_DIR / _safe_output_name(run_name, fallback=run_id))


def _is_generated_parent_run_name(parent_run_name: str | None) -> bool:
    """Detect auto-generated parent names from earlier workflow versions."""
    normalized_parent = _safe_output_name(parent_run_name, fallback="")
    return bool(re.fullmatch(r"baseline_.+_\d{4}-\d{2}-\d{2}_\d{6}", normalized_parent))


def _export_folder_name(parent_run_name: str | None, start_time_ms: int | None) -> str:
    """Name export folders as `experiment_<timestamp>` unless the user named the parent run."""
    normalized_parent = _safe_output_name(parent_run_name, fallback="experiment")
    if normalized_parent in {"", "experiment", "run"} or _is_generated_parent_run_name(normalized_parent):
        normalized_parent = "experiment"
    return f"{normalized_parent}_{_format_timestamp(start_time_ms)}"


def _run_info_dict(run_info: object) -> dict[str, object]:
    """Convert MLflow RunInfo into a JSON-serializable dictionary."""
    if hasattr(run_info, "to_dictionary"):
        return dict(run_info.to_dictionary())

    fields = (
        "run_id",
        "experiment_id",
        "run_name",
        "status",
        "start_time",
        "end_time",
        "artifact_uri",
        "lifecycle_stage",
        "user_id",
    )
    return {
        field: getattr(run_info, field)
        for field in fields
        if hasattr(run_info, field)
    }


def _metric_history_dict(
    client: MlflowClient,
    run_id: str,
    metric_names: set[str],
) -> dict[str, list[dict[str, object]]]:
    """Fetch the full metric history for each metric tracked on a run."""
    history: dict[str, list[dict[str, object]]] = {}
    for metric in sorted(metric_names):
        entries = client.get_metric_history(run_id, metric)
        history[metric] = [
            {"value": entry.value, "timestamp": entry.timestamp, "step": entry.step}
            for entry in entries
        ]
    return history


def _copy_run_artifacts(run_id: str, destination: Path) -> bool:
    """Copy all artifacts for a run into the export bundle."""
    try:
        local_artifacts = Path(download_artifacts(run_id=run_id, artifact_path=""))
    except Exception:
        return False

    if not local_artifacts.exists():
        return False

    if local_artifacts.is_dir():
        if any(local_artifacts.iterdir()):
            shutil.copytree(local_artifacts, destination, dirs_exist_ok=True)
            return True
        return False

    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local_artifacts, destination / local_artifacts.name)
    return True


def _write_run_export(
    client: MlflowClient,
    experiment: mlflow.entities.Experiment,
    tracking_uri: str,
    run: mlflow.entities.Run,
    output_dir: Path,
) -> dict[str, object]:
    """Write one run export bundle into a dedicated directory."""
    run_name = run.data.tags.get("mlflow.runName", run.info.run_id)
    artifacts_dir = output_dir / "artifacts"
    copied_artifacts = _copy_run_artifacts(run.info.run_id, artifacts_dir)

    write_json(
        output_dir / "run_metadata.json",
        {
            "experiment_name": experiment.name,
            "experiment_id": experiment.experiment_id,
            "artifact_location": experiment.artifact_location,
            "tracking_uri": tracking_uri,
            "run_name": run_name,
            "info": _run_info_dict(run.info),
        },
    )
    write_json(output_dir / "params.json", dict(run.data.params))
    write_json(output_dir / "metrics.json", dict(run.data.metrics))
    write_json(output_dir / "tags.json", dict(run.data.tags))
    write_json(
        output_dir / "metrics_history.json",
        _metric_history_dict(client, run.info.run_id, set(run.data.metrics.keys())),
    )

    summary = {
        "experiment_name": experiment.name,
        "run_id": run.info.run_id,
        "run_name": run_name,
        "parent_run_id": run.data.tags.get("mlflow.parentRunId"),
        "artifacts": str(artifacts_dir.resolve()) if copied_artifacts else None,
    }
    write_json(output_dir / "summary.json", summary)

    if copied_artifacts and artifacts_dir.exists():
        shutil.make_archive(str(output_dir / "artifacts"), "zip", root_dir=artifacts_dir)

    return {
        "run_id": run.info.run_id,
        "run_name": run_name,
        "directory": output_dir.name,
    }


def _export_mlflow_run_bundle(
    experiment_name: str,
    tracking_uri: str,
    parent_run_id: str,
    child_run_ids: list[str],
) -> None:
    """Export one human-readable MLflow bundle like `mlflow_output/<run_name>/`."""
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        logger.warning("Could not export MLflow bundle: experiment '%s' not found", experiment_name)
        return

    client = MlflowClient(tracking_uri=tracking_uri)
    parent_run = client.get_run(parent_run_id)
    parent_run_name = parent_run.data.tags.get("mlflow.runName", parent_run.info.run_id)
    child_runs = [client.get_run(run_id) for run_id in child_run_ids]
    export_name = _export_folder_name(parent_run_name, parent_run.info.start_time)
    output_dir = _resolve_output_dir(export_name, parent_run.info.run_id)
    parent_dir = output_dir / "experiment"
    parent_export = _write_run_export(
        client=client,
        experiment=experiment,
        tracking_uri=tracking_uri,
        run=parent_run,
        output_dir=parent_dir,
    )

    child_exports: list[dict[str, object]] = []
    for run in child_runs:
        run_name = run.data.tags.get("mlflow.runName", run.info.run_id)
        child_dir = _ensure_unique_directory(
            output_dir / _safe_output_name(run_name, fallback=run.info.run_id)
        )
        child_exports.append(
            _write_run_export(
                client=client,
                experiment=experiment,
                tracking_uri=tracking_uri,
                run=run,
                output_dir=child_dir,
            )
        )

    write_json(
        output_dir / "summary.json",
        {
            "experiment_name": experiment.name,
            "experiment_id": experiment.experiment_id,
            "tracking_uri": tracking_uri,
            "export_dir": str(output_dir.resolve()),
            "parent_run": parent_export,
            "child_runs": child_exports,
        },
    )


def run_modeling_workflow(
    data_path: str = "data/raw/synthetic_dataset.parquet",
    settings: dict | None = None,
    algorithms: list[str] | None = None,
    run_name: str | None = None,
) -> dict:
    """End-to-end modeling workflow (non-agentic baseline version).

    1. Load data from parquet
    2. Prepare and split
    3. Train algorithms with defaults (all or selected subset)
    4. Log everything to MLflow (nested runs under one parent)
    5. Write real-time experiment log to reports/
    6. Return results summary

    Args:
        data_path: Path to the parquet file with features + target.
        settings: Config dict. Loaded from disk if None.
        algorithms: Override list of algorithm names. When provided, only
                    these algorithms are trained instead of the full list
                    from settings["model"]["algorithms"]. Pass ["lightgbm"]
                    to test a single model.
        run_name: Name for the parent MLflow run. Defaults to "experiment".
    """
    settings = settings or load_settings()
    model_cfg = settings["model"]
    mlflow_cfg = settings.get("mlflow", {})

    # ── Experiment logger (markdown report) ──
    exp_log = ExperimentLogger()
    exp_log.start_experiment()

    # ── Resolve target column name ──
    # The Streamlit app builds its own settings dict (no data.synthetic key),
    # so we auto-detect the target column from the DataFrame when not configured.
    target_col = (
        settings.get("data", {})
        .get("synthetic", {})
        .get("target", {})
        .get("column_name", None)
    )
    if target_col is None:
        # Also check existing data config
        target_col = (
            settings.get("data", {})
            .get("existing", {})
            .get("target_column", None)
        )
    if target_col is None:
        # Fallback: auto-detect from the DataFrame
        target_col = "target"

    # ── Load and prepare data ──
    df = pd.read_parquet(data_path)
    logger.info("Loaded %d rows, %d cols from %s", len(df), len(df.columns), data_path)

    # Validate that the target column exists in the data
    if target_col not in df.columns:
        # Try common target column names as fallback
        for candidate in ("target", "binary_target", "label"):
            if candidate in df.columns:
                logger.warning(
                    "Configured target '%s' not found; using '%s' instead",
                    target_col, candidate,
                )
                target_col = candidate
                break
        else:
            raise KeyError(
                f"Target column '{target_col}' not found in data. "
                f"Available columns: {df.columns.tolist()}"
            )

    data = prepare_data(
        df,
        target_col=target_col,
        test_size=model_cfg.get("test_size", 0.2),
        validation_size=model_cfg.get("validation_size"),
    )
    logger.info("Data summary: %s", data["data_summary"])

    exp_log.log_data_summary(data["data_summary"])

    # ── Train baselines ──
    results = train_with_defaults(data, settings, algorithms=algorithms)

    # ── MLflow: nested runs ──
    experiment_name = mlflow_cfg.get("experiment_name", "multi_agent_ds")
    tracking_uri = resolve_tracking_uri(mlflow_cfg.get("tracking_uri", "sqlite:///mlruns.db"))
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise RuntimeError(f"MLflow experiment '{experiment_name}' could not be created")

    algo_list = list(results.keys())
    parent_run_name = run_name or "experiment"
    run_description = f"Baseline: {', '.join(algo_list)}"
    child_run_ids: list[str] = []
    parent_run_id: str | None = None

    with mlflow.start_run(run_name=parent_run_name, description=run_description) as parent_run:
        parent_run_id = parent_run.info.run_id
        # Log experiment-level metadata on the parent
        mlflow.set_tag("workflow", "baseline")
        mlflow.set_tag("algorithms", ", ".join(algo_list))
        mlflow.set_tag("n_train", data["data_summary"]["n_train"])
        mlflow.set_tag("n_validation", data["data_summary"]["n_validation"])
        mlflow.set_tag("n_test", data["data_summary"]["n_test"])
        mlflow.set_tag("n_features", data["data_summary"]["n_features"])
        mlflow.set_tag("has_ground_truth", data["data_summary"]["has_ground_truth"])

        # Log pipeline configuration as params on the parent run
        mlflow.log_params({
            "cv_folds": model_cfg["cv_folds"],
            "test_size": model_cfg.get("test_size", 0.2),
            "validation_size": model_cfg.get("validation_size", model_cfg.get("test_size", 0.2)),
            "primary_metric": model_cfg["primary_metric"],
            "scoring_metrics": ", ".join(model_cfg["scoring_metrics"]),
            "target_column": target_col,
        })

        for algo_name, res in results.items():
            # ── Child run per algorithm ──
            with mlflow.start_run(
                run_name=f"{algo_name}_baseline",
                nested=True,
            ) as child_run:
                child_run_ids.append(child_run.info.run_id)
                mlflow.set_tag("algorithm", algo_name)
                mlflow.set_tag("phase", "baseline")
                mlflow.set_tag("encoding", res.get("encoding", "unknown"))
                mlflow.set_tag("cv_folds", model_cfg["cv_folds"])

                # CV scores
                for metric, score in res["cv_scores"].items():
                    mlflow.log_metric(f"cv_mean_{metric}", score)
                for metric, score in res["cv_std"].items():
                    mlflow.log_metric(f"cv_std_{metric}", score)

                # Test scores
                for metric, score in res["validation_scores"].items():
                    mlflow.log_metric(f"validation_{metric}", score)
                for metric, score in res["test_scores"].items():
                    mlflow.log_metric(f"test_{metric}", score)

                # Per-fold CV scores (for variance analysis in MLflow UI)
                cv_raw = res["cv_results_raw"]
                for metric in model_cfg["scoring_metrics"]:
                    key = f"test_{metric}"
                    if key in cv_raw:
                        for i, fold_score in enumerate(cv_raw[key]):
                            mlflow.log_metric(f"cv_fold_{metric}", float(fold_score), step=i)

                # Params and model artifact
                mlflow.log_params(res["params_used"])
                mlflow.sklearn.log_model(res["model"], artifact_path="model")

                # Generate and log diagnostic artifacts (JSON + PNG)
                try:
                    artifacts = generate_run_artifacts(
                        model=res["model"],
                        y_test=data["y_test"],
                        y_pred=res["y_pred"],
                        y_prob=res["y_prob"],
                        feature_names=res["feature_names"],
                        algo_name=algo_name,
                        true_prob_test=data.get("true_prob_test"),
                        training_history=res.get("training_history"),
                    )
                    with tempfile.TemporaryDirectory() as tmpdir:
                        for filename, content in artifacts.items():
                            filepath = Path(tmpdir) / filename
                            if filename.endswith(".json"):
                                filepath.write_text(json.dumps(content, indent=2))
                            else:
                                filepath.write_bytes(content)
                            mlflow.log_artifact(str(filepath))
                    logger.info("Logged %d artifacts for %s", len(artifacts), algo_name)
                except Exception as e:
                    logger.warning("Artifact generation failed for %s: %s", algo_name, e)

            logger.info("Logged %s baseline to MLflow (nested)", algo_name)

            # ── Experiment log (markdown) ──
            exp_log.log_baseline(algo_name, res)

    # ── Finalize experiment log ──
    exp_log.finalize()

    _export_mlflow_run_bundle(
        experiment_name=experiment_name,
        tracking_uri=tracking_uri,
        parent_run_id=parent_run_id or parent_run.info.run_id,
        child_run_ids=child_run_ids,
    )

    return results


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the modeling workflow."""
    parser = argparse.ArgumentParser(
        description="Run the baseline modeling workflow with MLflow logging.",
    )
    parser.add_argument(
        "--data-path",
        default="data/raw/synthetic_dataset.parquet",
        help="Path to the input parquet file (default: data/raw/synthetic_dataset.parquet)",
    )
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=None,
        help=(
            "Override which algorithms to train. Space-separated list. "
            "Example: --algorithms lightgbm logistic_regression. "
            "When omitted, all algorithms from settings.yaml are used."
        ),
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Name for the parent MLflow run. Defaults to 'experiment'.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    args = _parse_args()
    results = run_modeling_workflow(
        data_path=args.data_path,
        algorithms=args.algorithms,
        run_name=args.run_name,
    )

    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")

    for algo, res in results.items():
        print(f"\n── {algo} (baseline) ──")
        print(f"Params: {res['params_used']}")
        print(f"Encoding: {res['encoding']}")
        print(f"Time: {res['elapsed_seconds']:.1f}s")
        print("CV scores:")
        for metric, score in res["cv_scores"].items():
            print(f"  {metric}: {score:.4f} (+/- {res['cv_std'][metric]:.4f})")
        print("Test scores:")
        for metric, score in res["test_scores"].items():
            print(f"  {metric}: {score:.4f}")
