"""Preparation workflow for approved cleaning and feature-engineering plans."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from multi_agent_ds.core import build_s3_uri, load_settings
from multi_agent_ds.skills.cleaning import apply_cleaning_actions
from multi_agent_ds.skills.feature_engineering import apply_feature_actions
from multi_agent_ds.workflows.discovery import load_dataframe
from multi_agent_ds.tools.io import upload_to_s3
from multi_agent_ds.tools.skill_recorder import record_workflow_call


def _source_stem(source_path: str) -> str:
    parsed = urlparse(source_path)
    path = parsed.path if parsed.scheme == "s3" else source_path
    return Path(path).stem or "dataset"


def build_processed_filename(source_path: str, timestamp: datetime | None = None) -> str:
    """Build a timestamped processed parquet filename."""
    timestamp = timestamp or datetime.utcnow()
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    return f"{_source_stem(source_path)}_processed_{stamp}.parquet"


def _resolve_target_column(settings: dict[str, Any]) -> str:
    """Resolve the configured target column for preparation."""
    data_cfg = settings.get("data", {})
    if data_cfg.get("source") == "existing":
        target_col = data_cfg.get("existing", {}).get("target_column")
        if not target_col:
            raise ValueError(
                "Existing-data preparation requires data.existing.target_column to be set in settings."
            )
        return target_col

    return data_cfg.get("synthetic", {}).get("target", {}).get("column_name", "target")


@record_workflow_call
def run_preparation_workflow(
    data_path: str,
    prep_plan: dict[str, Any],
    settings: dict[str, Any] | None = None,
    local_only: bool = False,
) -> dict[str, Any]:
    """Execute an approved preparation plan and persist the processed parquet artifact.

    Parameters
    ----------
    data_path : str
        Path to the input dataset
    prep_plan : dict
        Preparation plan with cleaning and feature-engineering actions
    settings : dict, optional
        Settings dictionary; if None, loads from config
    local_only : bool, default False
        If True, write processed parquet to local data/processed/ directory
        and skip S3 upload. Use only for offline demo rehearsal.
    """
    settings = settings or load_settings()
    df, source_path = load_dataframe(data_path, settings)
    target_col = _resolve_target_column(settings)

    if target_col not in df.columns:
        raise KeyError(
            f"Target column '{target_col}' not found in preparation dataset. "
            f"Available columns: {df.columns.tolist()}"
        )

    source_n_rows = int(len(df))
    source_n_features = int(max(df.shape[1] - 1, 0))

    cleaned_df, cleaning_summary = apply_cleaning_actions(
        df=df,
        actions=prep_plan.get("cleaning_actions"),
        target_col=target_col,
    )
    engineered_df, feature_summary = apply_feature_actions(
        df=cleaned_df,
        actions=prep_plan.get("feature_actions"),
        target_col=target_col,
    )

    filename = build_processed_filename(source_path)
    processed_n_rows = int(len(engineered_df))
    processed_n_features = int(max(engineered_df.shape[1] - 1, 0))

    if local_only:
        # Write directly to local data/processed/ directory
        processed_dir = Path(settings.get("data", {}).get("processed_dir", "data/processed"))
        processed_dir.mkdir(parents=True, exist_ok=True)
        local_path = processed_dir / filename
        engineered_df.to_parquet(local_path)
        processed_path = str(local_path.resolve())
    else:
        # Upload to S3 as usual
        processed_path = build_s3_uri(settings, "processed", filename)
        with TemporaryDirectory() as tmp_dir:
            local_path = Path(tmp_dir) / filename
            engineered_df.to_parquet(local_path)
            upload_to_s3(
                local_path=local_path,
                path_key="processed",
                filename=filename,
                settings=settings,
            )

    return {
        "source_data_path": source_path,
        "target_column": target_col,
        "artifact_filename": filename,
        "processed_data_path": processed_path,
        "source_n_rows": source_n_rows,
        "source_n_features": source_n_features,
        "n_rows": processed_n_rows,
        "n_features": processed_n_features,
        "processed_n_rows": processed_n_rows,
        "processed_n_features": processed_n_features,
        "cleaning_summary": cleaning_summary,
        "feature_summary": feature_summary,
    }
