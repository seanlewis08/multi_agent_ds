"""Discovery workflow for non-agentic dataset profiling."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from multi_agent_ds.core import load_settings
from multi_agent_ds.skills.profiling import profile_dataset
from multi_agent_ds.tools.data_generator import generate_synthetic_data
from multi_agent_ds.tools.io import get_s3_client


def _resolve_target_column(settings: dict[str, Any]) -> str:
    """Resolve the configured target column from settings."""
    data_cfg = settings.get("data", {})
    if data_cfg.get("source") == "existing":
        target_col = data_cfg.get("existing", {}).get("target_column")
        if not target_col:
            raise ValueError(
                "Existing-data discovery requires data.existing.target_column to be set in settings."
            )
        return target_col

    return data_cfg.get("synthetic", {}).get("target", {}).get("column_name", "target")


def resolve_data_path(data_path: str | None, settings: dict[str, Any]) -> str | None:
    """Resolve the input dataset location from explicit path or settings.

    If data_path is provided, use it directly. Otherwise, resolve based on the
    data.source mode:
      - "existing": use data.existing.uri (user's S3/remote path)
      - "synthetic": use data/raw/synthetic_dataset.parquet if it exists, else None

    Used by discovery workflow and demo_recorder CLI.
    """
    if data_path is not None:
        return data_path

    data_cfg = settings.get("data", {})
    if data_cfg.get("source") == "existing":
        return data_cfg.get("existing", {}).get("uri")

    default_local = Path("data/raw/synthetic_dataset.parquet")
    if default_local.exists():
        return str(default_local)

    return None


# Backward-compat alias for internal callers (will be removed once they migrate)
_resolve_data_path = resolve_data_path


def _load_parquet_from_s3(uri: str, settings: dict[str, Any]) -> pd.DataFrame:
    """Download an explicit S3 parquet URI to a temp file and load it."""
    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    client = get_s3_client(settings)
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = Path(tmp_dir) / Path(key).name
        client.download_file(bucket, key, str(local_path))
        return pd.read_parquet(local_path)


def load_dataframe(data_path: str | None, settings: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    """Load the discovery dataset from local parquet, S3, or synthetic generation."""
    if data_path is None:
        df = generate_synthetic_data(settings)
        return df, "generated://synthetic"

    if data_path.startswith("s3://"):
        return _load_parquet_from_s3(data_path, settings), data_path

    local_path = Path(data_path)
    return pd.read_parquet(local_path), str(local_path)


def run_discovery_workflow(
    data_path: str | None = None,
    settings: dict[str, Any] | None = None,
    target_col: str | None = None,
) -> dict[str, Any]:
    """Load data and return a structured EDA profile payload."""
    settings = settings or load_settings()
    resolved_target_col = target_col or _resolve_target_column(settings)
    resolved_data_path = _resolve_data_path(data_path, settings)
    df, source_path = load_dataframe(resolved_data_path, settings)

    if resolved_target_col not in df.columns:
        raise KeyError(
            f"Target column '{resolved_target_col}' not found in discovery dataset. "
            f"Available columns: {df.columns.tolist()}"
        )

    profile = profile_dataset(df, resolved_target_col)
    dataset_summary = profile.get("dataset_summary", {})
    n_features = int(dataset_summary.get("n_features", df.shape[1] - 1))

    return {
        "data_path": source_path,
        "target_column": resolved_target_col,
        "n_rows": int(len(df)),
        "n_features": n_features,
        "profile": profile,
    }
