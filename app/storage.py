"""Cloudflare R2 (S3-compatible) storage helpers.

All functions are thin wrappers around boto3 so the rest of the codebase never
imports boto3 directly — tests can monkeypatch at this boundary without touching
the underlying AWS SDK.

Each function increments an r2_operations_total counter so Prometheus can track
call volume and catch billing surprises early.
"""
from functools import lru_cache

import boto3
from botocore.config import Config

from app.config import get_settings
from app.metrics import r2_operations_total


def _make_client(endpoint_url: str):
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="auto",
    )


@lru_cache(maxsize=1)
def _r2_client():
    """Internal client — uses the Docker-network endpoint for server-side calls."""
    return _make_client(get_settings().r2_endpoint_url)


@lru_cache(maxsize=1)
def _presign_client():
    """Presign client — uses the public URL so the signature matches what browsers hit.

    When r2_public_url is unset (production R2) the same endpoint is used for both.
    """
    s = get_settings()
    return _make_client(s.r2_public_url or s.r2_endpoint_url)


def presigned_get(key: str, ttl: int) -> str:
    """Return a short-lived presigned GET URL for delivery."""
    s = get_settings()
    r2_operations_total.labels("presigned_get").inc()
    return _presign_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": s.r2_bucket, "Key": key},
        ExpiresIn=ttl,
    )


def download_bytes(key: str) -> bytes:
    """Download an R2 object and return its raw bytes."""
    s = get_settings()
    r2_operations_total.labels("get_object").inc()
    resp = _r2_client().get_object(Bucket=s.r2_bucket, Key=key)
    return resp["Body"].read()


def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    """Upload raw bytes to an R2 key."""
    s = get_settings()
    r2_operations_total.labels("put_object").inc()
    _r2_client().put_object(
        Bucket=s.r2_bucket, Key=key, Body=data, ContentType=content_type
    )


def delete_object(key: str) -> None:
    """Delete a single R2 object."""
    s = get_settings()
    r2_operations_total.labels("delete_object").inc()
    _r2_client().delete_object(Bucket=s.r2_bucket, Key=key)


def delete_objects(keys: list[str]) -> int:
    """Batch-delete R2 objects (up to 1000 per request). Returns the count submitted.

    Uses S3 DeleteObjects with Quiet=True so only errors are returned.
    Errors are logged but do not raise — a missing object is not a failure.
    """
    if not keys:
        return 0
    import logging
    log = logging.getLogger("app.storage")
    s = get_settings()
    total = 0
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        r2_operations_total.labels("delete_objects").inc()
        resp = _r2_client().delete_objects(
            Bucket=s.r2_bucket,
            Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
        )
        for err in resp.get("Errors", []):
            log.warning(
                "R2 delete_objects error",
                extra={"extra_fields": {"key": err.get("Key"), "code": err.get("Code")}},
            )
        total += len(batch)
    return total
