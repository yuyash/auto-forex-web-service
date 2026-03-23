"""Daily PostgreSQL backup with optional S3 upload.

Runs ``pg_dump`` against the configured database, compresses the output,
and optionally uploads it to S3 using AssumeRole credentials.  Old local
backups beyond the retention window are pruned automatically.

Configuration is via environment variables:

    DB_BACKUP_S3_BUCKET     S3 bucket for backup uploads (optional)
    DB_BACKUP_S3_PREFIX     S3 key prefix (default: db-backups/)
    DB_BACKUP_ROLE_ARN      IAM role ARN to assume for S3 access (optional)
    DB_BACKUP_AWS_PROFILE   AWS profile name (optional)
    DB_BACKUP_RETENTION_DAYS  Local retention in days (default: 7)

If ``DB_BACKUP_S3_BUCKET`` is not set, backups are stored locally only.
"""

from __future__ import annotations

import gzip
import logging
import os
import subprocess  # nosec B404 — pg_dump is a trusted system binary
from datetime import UTC, datetime, timedelta
from pathlib import Path

from celery import shared_task

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("/app/backups")


def _get_s3_client(*, profile: str | None, role_arn: str | None):
    """Create an S3 client, optionally assuming a role first."""
    import boto3

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()

    if not role_arn:
        return session.client("s3")

    sts = session.client("sts")
    response = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="auto-forex-db-backup",
    )
    creds = response["Credentials"]
    assumed_session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=getattr(session, "region_name", None),
    )
    return assumed_session.client("s3")


def _run_pg_dump(output_path: Path) -> None:
    """Run pg_dump and write gzipped output to *output_path*."""
    db_name = os.getenv("DB_NAME", "auto-forex")
    db_user = os.getenv("DB_USER", "postgres")
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_password = os.getenv("DB_PASSWORD", "")

    env = {**os.environ, "PGPASSWORD": db_password}
    cmd = [
        "pg_dump",
        "-h",
        db_host,
        "-p",
        db_port,
        "-U",
        db_user,
        db_name,
    ]

    result = subprocess.run(  # nosec B603 — args are from env vars, not user input
        cmd,
        capture_output=True,
        env=env,
        timeout=600,
        check=False,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"pg_dump failed (exit {result.returncode}): {stderr}")

    with gzip.open(output_path, "wb") as f:
        f.write(result.stdout)


def _upload_to_s3(
    local_path: Path, *, bucket: str, prefix: str, profile: str | None, role_arn: str | None
) -> str:
    """Upload a file to S3 and return the S3 URI."""
    s3 = _get_s3_client(profile=profile, role_arn=role_arn)
    key = f"{prefix}{local_path.name}"
    s3.upload_file(str(local_path), bucket, key)
    return f"s3://{bucket}/{key}"


def _prune_old_backups(retention_days: int) -> int:
    """Delete local backups older than *retention_days*. Returns count deleted."""
    if not BACKUP_DIR.exists():
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    deleted = 0
    for f in BACKUP_DIR.glob("backup_*.sql.gz"):
        if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) < cutoff:
            f.unlink()
            deleted += 1
    return deleted


@shared_task(
    name="config.tasks.backup_database",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def backup_database(self) -> dict[str, str | int]:
    """Dump PostgreSQL, optionally upload to S3, and prune old local backups."""
    s3_bucket = os.getenv("DB_BACKUP_S3_BUCKET", "").strip() or None
    s3_prefix = os.getenv("DB_BACKUP_S3_PREFIX", "db-backups/").strip()
    role_arn = os.getenv("DB_BACKUP_ROLE_ARN", "").strip() or None
    profile = os.getenv("DB_BACKUP_AWS_PROFILE", "").strip() or None
    retention_days = int(os.getenv("DB_BACKUP_RETENTION_DAYS", "7"))

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.sql.gz"
    local_path = BACKUP_DIR / filename

    try:
        logger.info("backup_database: starting pg_dump -> %s", filename)
        _run_pg_dump(local_path)
        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info("backup_database: dump complete (%.1f MB)", size_mb)

        s3_uri = None
        if s3_bucket:
            logger.info("backup_database: uploading to s3://%s/%s", s3_bucket, s3_prefix)
            s3_uri = _upload_to_s3(
                local_path,
                bucket=s3_bucket,
                prefix=s3_prefix,
                profile=profile,
                role_arn=role_arn,
            )
            logger.info("backup_database: uploaded to %s", s3_uri)

        pruned = _prune_old_backups(retention_days)
        if pruned:
            logger.info("backup_database: pruned %d old backup(s)", pruned)

        return {
            "status": "completed",
            "file": filename,
            "size_mb": round(size_mb, 1),
            "s3_uri": s3_uri or "disabled",
            "pruned": pruned,
        }
    except Exception as exc:
        # Clean up partial file on failure
        if local_path.exists():
            local_path.unlink(missing_ok=True)
        logger.exception("backup_database failed: %s", exc)
        raise self.retry(exc=exc) from exc
