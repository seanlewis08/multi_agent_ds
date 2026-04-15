"""S3 upload and download utilities."""

from __future__ import annotations

import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from multi_agent_ds.core import build_s3_uri, load_settings

logger = logging.getLogger(__name__)


def get_s3_client(settings: dict | None = None):
    """Create an S3 client with auth fallback.

    Tries AWS_PROFILE from settings first (your SSO setup).
    Falls back to default credential chain (instance profiles, env vars).
    """
    settings = settings or load_settings()
    profile = settings["s3"].get("profile")

    if profile:
        try:
            session = boto3.Session(profile_name=profile)
            client = session.client("s3")
            # Quick check that creds are valid
            client.list_buckets()
            logger.info("Authenticated via profile: %s", profile)
            return client
        except (NoCredentialsError, ClientError) as exc:
            logger.warning("Profile '%s' failed (%s), falling back to default chain", profile, exc)

    client = boto3.client("s3")
    logger.info("Authenticated via default credential chain")
    return client


def upload_to_s3(
    local_path: str | Path,
    path_key: str,
    filename: str,
    settings: dict | None = None,
) -> str:
    """Upload a local file to S3.

    Args:
        local_path: Path to the file on disk.
        path_key: Key in settings.s3.paths (e.g. "raw", "processed").
        filename: Name for the file in S3.
        settings: Optional pre-loaded settings dict.

    Returns:
        The full S3 URI of the uploaded file.
    """
    settings = settings or load_settings()
    local_path = Path(local_path)

    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    s3_uri = build_s3_uri(settings, path_key, filename)
    bucket = settings["s3"]["bucket"]
    prefix = settings["s3"]["prefix"]
    sub_path = settings["s3"]["paths"][path_key]
    key = f"{prefix}/{sub_path}/{filename}"

    client = get_s3_client(settings)
    logger.info("Uploading %s → %s", local_path, s3_uri)
    client.upload_file(str(local_path), bucket, key)
    logger.info("Upload complete")

    return s3_uri


def download_from_s3(
    path_key: str,
    filename: str,
    local_dir: str | Path = "data/raw",
    settings: dict | None = None,
) -> Path:
    """Download a file from S3 to a local directory.

    Args:
        path_key: Key in settings.s3.paths (e.g. "raw", "processed").
        filename: Name of the file in S3.
        local_dir: Local directory to save to.
        settings: Optional pre-loaded settings dict.

    Returns:
        Path to the downloaded local file.
    """
    settings = settings or load_settings()
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / filename

    bucket = settings["s3"]["bucket"]
    prefix = settings["s3"]["prefix"]
    sub_path = settings["s3"]["paths"][path_key]
    key = f"{prefix}/{sub_path}/{filename}"
    s3_uri = build_s3_uri(settings, path_key, filename)

    client = get_s3_client(settings)
    logger.info("Downloading %s → %s", s3_uri, local_path)
    client.download_file(bucket, key, str(local_path))
    logger.info("Download complete")

    return local_path


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    settings = load_settings()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  uv run python -m multi_agent_ds.tools.io upload <local_path> <path_key> <filename>")
        print("  uv run python -m multi_agent_ds.tools.io download <path_key> <filename> [local_dir]")
        sys.exit(1)

    action = sys.argv[1]

    if action == "upload":
        local_path, path_key, filename = sys.argv[2], sys.argv[3], sys.argv[4]
        uri = upload_to_s3(local_path, path_key, filename, settings)
        print(f"Uploaded → {uri}")

    elif action == "download":
        path_key, filename = sys.argv[2], sys.argv[3]
        local_dir = sys.argv[4] if len(sys.argv) > 4 else "data/raw"
        path = download_from_s3(path_key, filename, local_dir, settings)
        print(f"Downloaded → {path}")