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


def _source_stem(source_path: str) -> str:
    parsed = urlparse(source_path)
    path = parsed.path if parsed.scheme == "s3" else source_path
    return Path(path).stem or "dataset"


def build_processed_filename(source_path: str, timestamp: datetime | None = None) -> str:
    """Build a timestamped processed parquet filename."""
    timestamp = timestamp or datetime.utcnow()
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    return f"{_source_stem(source_path)}_processed_{stamp}.parquet"


def run_preparation_workflow(
    data_path: str,
    prep_plan: dict[str, Any],
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute an approved preparation plan and persist the processed parquet artifact."""
    settings = settings or load_settings()
    df, source_path = load_dataframe(data_path, settings)
    target_col = settings.get("data", {}).get("existing", {}).get("target_column") or settings.get(
        "data", {}
    ).get("synthetic", {}).get("target", {}).get("column_name", "target")

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
        "processed_data_path": build_s3_uri(settings, "processed", filename),
        "n_rows": int(len(engineered_df)),
        "n_features": int(engineered_df.shape[1] - 1),
        "cleaning_summary": cleaning_summary,
        "feature_summary": feature_summary,
    }
