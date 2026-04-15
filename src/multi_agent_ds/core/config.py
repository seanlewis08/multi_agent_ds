"""Central Configuration Loader

Reads any YAML file from the config/directory. Every module in the project
imports from here.
"""

from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _PROJECT_ROOT / "config"

def load_config(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    """Load a YAML config file by name.

    Parameters
    ----------
    name: str
        File name without extension: 'settings', 'agents', 'prompts', or 'workflows'
    config_dir: Path, optional
        Override the default config/ directory (useful for tests).

    Returns
    -------
    dict
        Parsed YAML contents

    Raises
    ------
    FileNotFoundError
        If the config file does not exist
    """
    directory = config_dir or _CONFIG_DIR
    config_path = directory / f"{name}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f'Config file {config_path} does not exist')

    with open(config_path) as f:
        return yaml.safe_load(f)


# ---- Convenience wrappers ----
# These exist so callers never pass raw strings.
# Usage: from multi_agent_ds.core import load_settings

def load_settings() -> dict[str, Any]:
    """Load settings from a YAML file."""
    return load_config("settings")

def load_agents_config() -> dict[str, Any]:
    """Load agent definitions from a YAML file."""
    return load_config("agents")

def load_prompts_config() -> dict[str, Any]:
    """Load prompt templates from a YAML file."""
    return load_config("prompts")

def load_workflows_config() -> dict[str, Any]:
    """Load workflow definitions from a YAML file."""
    return load_config("workflows")


def resolve_tracking_uri(tracking_uri: str) -> str:
    """Resolve sqlite tracking URIs relative to the repository root."""
    if not tracking_uri.startswith("sqlite:///"):
        return tracking_uri

    sqlite_path = tracking_uri[len("sqlite:///") :]
    if not sqlite_path:
        return tracking_uri

    # Already absolute: sqlite:////Users/... or sqlite:///C:/...
    if sqlite_path.startswith("/") or (len(sqlite_path) >= 2 and sqlite_path[1] == ":"):
        return tracking_uri

    return f"sqlite:///{(_PROJECT_ROOT / sqlite_path).resolve().as_posix()}"

# ---- Settings helpers ---
# These avoid repeating dict-key lookups across modules

def get_active_scale(settings: dict[str, Any]) -> dict[str, Any]:
    """Return the active scale config (e.g., {'n_rows': 5000}).

    Reads settings['data']['synthetic']['scale'] and looks it up
    in settings['data']['synthetic']['scales'].
    """
    synth = settings["data"]["synthetic"]
    scale_name = synth["scale"]
    scales = synth["scales"]

    if scale_name not in scales:
        raise ValueError(
            f"Unknown scale '{scale_name}' specified in settings. Available scales: {list(scales.keys())}"
        )
    return scales[scale_name]

def build_s3_uri(settings: dict[str, Any], path_key: str, filename: str) -> str:
    """Build a full s3 URI from settings.
    
    Parameters
    ----------
    settings: dict
        Full settings dictionary
    path_key: str
        Key from settings['s3']['paths'] - e.g. 'raw', 'processed', 'models', 'artifacts', 'reports'
    filename: str   
        File name to append 
        
    Returns 
    --------
    str 
        e.g., 's3://bucket/path/to/file'
    """
    s3 = settings["s3"]
    sub_path = s3["paths"][path_key]
    return f"s3://{s3['bucket']}/{s3['prefix']}/{sub_path}/{filename}"
