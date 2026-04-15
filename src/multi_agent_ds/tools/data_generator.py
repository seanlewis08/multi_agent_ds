"""Synthetic data generation using SDV with optional deterministic target."""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sdv.metadata import Metadata
from sdv.single_table import GaussianCopulaSynthesizer

from multi_agent_ds.core import get_active_scale, load_settings

logger = logging.getLogger(__name__)

# ── Ground truth coefficients ──────────────────────────────────────────
# These define the TRUE relationship between features and target.
# A perfect model would recover these weights exactly.
# Aligned to the insurance features defined in config/settings.yaml.
# Coefficients are scaled so the total logit span produces
# true_probability naturally within [~0.02, ~0.82].
COEFFICIENTS = {
    # Numeric continuous
    "age": 0.0086,                    # older → slightly higher risk
    "annual_income": -0.0000035,      # higher income → lower risk
    "credit_score": -0.00213,         # higher credit → lower risk
    "vehicle_value": 0.0000065,       # more expensive vehicle → higher risk
    "annual_premium": 0.000086,       # higher premium (proxy for risk tier)
    "claim_amount_avg": 0.0000128,    # history of larger claims → higher risk
    "miles_driven_annual": 0.0000086, # more miles → more exposure
    "distance_to_work": 0.00341,      # longer commute → more exposure
    # Numeric discrete
    "num_prior_claims": 0.077,        # strong signal — more claims → higher risk
    "policy_tenure_months": -0.0017,  # longer tenure → lower risk
    "num_vehicles": 0.042,            # more vehicles → more exposure
    "num_drivers_on_policy": 0.035,   # more drivers → more risk
}

CATEGORICAL_MAPS = {
    "state": {
        "FL": 0.108, "TX": 0.065, "CA": 0.042, "GA": 0.042, "MI": 0.023,
        "NY": 0.0, "IL": 0.0, "PA": -0.023, "NC": -0.023, "OH": -0.042,
    },
    "vehicle_type": {
        "truck": 0.065, "suv": 0.042, "coupe": 0.023,
        "sedan": 0.0, "hatchback": -0.023, "van": -0.023,
    },
    "coverage_tier": {
        "liability_only": 0.086, "basic": 0.042,
        "standard": 0.0, "premium": -0.065,
    },
    "marital_status": {
        "single": 0.065, "divorced": 0.023,
        "married": -0.042, "widowed": -0.023,
    },
    "education_level": {
        "high_school": 0.042, "associates": 0.023,
        "bachelors": 0.0, "masters": -0.023, "doctorate": -0.042,
    },
}

# ── Interaction terms ──────────────────────────────────────────────────
# These add non-additive signal that a GBM can discover via tree splits.
# Each tuple: (feature_a, feature_b, coefficient).
INTERACTIONS = [
    # Young + many prior claims → compounding risk
    ("age", "num_prior_claims", -0.0012),

    # More prior claims + high claim amounts → compounding risk
    ("num_prior_claims", "claim_amount_avg", 0.0000025),

    # Low credit + high vehicle value → overextended → higher risk
    ("credit_score", "vehicle_value", 0.0000000035),

    # More miles + more vehicles → multiplicative exposure
    ("miles_driven_annual", "num_vehicles", 0.0000004),
]

# Intercept calibrated so that ~27% target rate with widened probability range.
INTERCEPT = -1.97
NOISE_SCALE = 0.5



# ── Ground truth functions ─────────────────────────────────────────────

def sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return np.where(
        x >= 0,
        1 / (1 + np.exp(-x)),
        np.exp(x) / (1 + np.exp(x)),
    )


def true_probability(df: pd.DataFrame) -> np.ndarray:
    """Compute P(target=1) from the known ground truth function.

    This is the Bayes-optimal probability — a perfect model
    would recover these values exactly (minus noise).
    """
    logit = np.full(len(df), INTERCEPT, dtype=np.float64)

    for feature, coef in COEFFICIENTS.items():
        if feature in df.columns:
            logit += coef * df[feature].values.astype(np.float64)

    for feature, mapping in CATEGORICAL_MAPS.items():
        if feature in df.columns:
            encoded = df[feature].map(mapping).fillna(0.0).values
            logit += encoded

    # Interaction terms
    for feat_a, feat_b, coef in INTERACTIONS:
        if feat_a in df.columns and feat_b in df.columns:
            a = df[feat_a].values.astype(np.float64)
            b = df[feat_b].values.astype(np.float64)
            logit += coef * a * b

    return sigmoid(logit)


def apply_ground_truth(
    df: pd.DataFrame, seed: int = 42, target_col: str = "target",
) -> pd.DataFrame:
    """Overwrite target column with deterministic ground truth.

    Args:
        df: DataFrame with features (from SDV).
        seed: Random seed for reproducibility.
        target_col: Name of the target column.

    Returns:
        Same DataFrame with target replaced by ground truth labels
        and '_true_probability' added for evaluation.
    """
    rng = np.random.default_rng(seed=seed)
    true_prob = true_probability(df)

    logit = np.log(true_prob / (1 - true_prob + 1e-10))
    noisy_logit = logit + rng.normal(0, NOISE_SCALE, size=len(df))
    noisy_prob = sigmoid(noisy_logit)

    df = df.copy()
    df[target_col] = (rng.uniform(size=len(df)) < noisy_prob).astype(int)
    df["_true_probability"] = true_prob

    return df


# ── SDV data generation ────────────────────────────────────────────────

def _build_seed_dataframe(settings: dict) -> pd.DataFrame:
    """Create a small seed DataFrame from config feature definitions."""
    features = settings["data"]["synthetic"]["features"]
    target_cfg = settings["data"]["synthetic"]["target"]
    target_col = target_cfg.get("column_name", "target")
    positive_rate = target_cfg.get("positive_rate", 0.15)

    rng = np.random.default_rng(seed=42)
    n_seed = 200
    data = {}

    for name, spec in features.items():
        ftype = spec.get("type", "numerical")
        if ftype == "categorical":
            values = spec.get("values", ["A", "B"])
            data[name] = rng.choice(values, size=n_seed)
        elif ftype == "numerical":
            lo = spec.get("min", 0)
            hi = spec.get("max", 100)
            subtype = spec.get("subtype", "float")
            data[name] = rng.uniform(lo, hi, size=n_seed)
            if subtype == "integer":
                data[name] = np.round(data[name]).astype(int)

    data[target_col] = rng.choice(
        [0, 1], p=[1 - positive_rate, positive_rate], size=n_seed
    )

    return pd.DataFrame(data)


def _build_metadata(seed_df: pd.DataFrame, settings: dict) -> Metadata:
    """Build SDV metadata from seed DataFrame and config."""
    metadata = Metadata.detect_from_dataframe(seed_df, infer_keys=None)

    features = settings["data"]["synthetic"]["features"]
    for name, spec in features.items():
        sdtype = spec.get("type", "numerical")
        update_kwargs: dict = {"column_name": name, "sdtype": sdtype}

        if sdtype == "numerical":
            subtype = spec.get("subtype", "float")
            update_kwargs["computer_representation"] = (
                "Int64" if subtype == "integer" else "Float"
            )

        metadata.update_column(**update_kwargs)

    target_col = settings["data"]["synthetic"]["target"].get("column_name", "target")
    metadata.update_column(column_name=target_col, sdtype="categorical")

    return metadata


def generate_synthetic_data(settings: dict | None = None) -> pd.DataFrame:
    """Generate synthetic data with SDV, optionally applying deterministic target.

    Reads settings.data.synthetic.target_mode:
        - "learned": SDV generates everything including target (default)
        - "deterministic": SDV generates features, ground truth creates the target

    Returns:
        DataFrame with features, target, and (if deterministic) _true_probability.
    """
    settings = settings or load_settings()
    scale = get_active_scale(settings)
    n_rows = scale["n_rows"]
    target_mode = settings["data"]["synthetic"].get("target_mode", "learned")
    target_col = settings["data"]["synthetic"]["target"].get("column_name", "target")

    logger.info("Generating %d rows | target_mode: %s", n_rows, target_mode)

    # ── SDV pipeline ──
    logger.info("Building seed dataframe ...")
    seed_df = _build_seed_dataframe(settings)

    logger.info("Building metadata ...")
    metadata = _build_metadata(seed_df, settings)

    logger.info("Fitting GaussianCopulaSynthesizer ...")
    synth = GaussianCopulaSynthesizer(metadata)
    synth.fit(seed_df)

    logger.info("Sampling %d rows ...", n_rows)
    df = synth.sample(num_rows=n_rows)

    # Enforce integer types
    features = settings["data"]["synthetic"]["features"]
    for name, spec in features.items():
        if spec.get("subtype") == "integer" and name in df.columns:
            df[name] = df[name].round().astype(int)

    # ── Apply ground truth if deterministic mode ──
    if target_mode == "deterministic":
        df = apply_ground_truth(df, target_col=target_col)
        logger.info(
            "Applied deterministic target | rate: %.1f%% | true_prob range: [%.4f, %.4f]",
            df[target_col].mean() * 100,
            df["_true_probability"].min(),
            df["_true_probability"].max(),
        )
    else:
        logger.info("Using SDV-learned target | rate: %.1f%%", df[target_col].mean() * 100)

    return df


def save_local(df: pd.DataFrame, path: str | Path = "data/raw/synthetic_dataset.parquet") -> Path:
    """Write DataFrame to parquet."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("Saved → %s (%d rows, %d cols)", path, len(df), len(df.columns))
    return path


def _configure_logging() -> None:
    """Set up readable logging and suppress noisy third-party loggers."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress verbose SDV / copulas / rdt internals
    for noisy in (
        "sdv",
        "sdv.metadata",
        "sdv.metadata.single_table",
        "sdv.data_processing",
        "sdv.data_processing.data_processor",
        "SingleTableSynthesizer",
        "copulas",
        "copulas.multivariate",
        "copulas.multivariate.gaussian",
        "rdt",
        "rdt.transformers",
        "rdt.transformers.utils",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Suppress SDV "save_to_json" recommendation
    warnings.filterwarnings("ignore", message=".*save_to_json.*", category=UserWarning)


if __name__ == "__main__":
    _configure_logging()
    settings = load_settings()

    if settings["data"]["source"] != "synthetic":
        logger.info("Data source is '%s', skipping generation.", settings["data"]["source"])
    else:
        df = generate_synthetic_data(settings)
        save_local(df)

        target_col = settings["data"]["synthetic"]["target"].get("column_name", "target")
        print("\n" + "=" * 60)
        print("  Synthetic Dataset Summary")
        print("=" * 60)
        print(f"  Rows      : {df.shape[0]:,}")
        print(f"  Columns   : {df.shape[1]:,}")
        print(f"  Target col : {target_col}")
        print(f"  Target rate: {df[target_col].mean():.3f}")
        if "_true_probability" in df.columns:
            print(
                f"  True prob  : [{df['_true_probability'].min():.4f}, "
                f"{df['_true_probability'].max():.4f}]"
            )
        print("=" * 60)
