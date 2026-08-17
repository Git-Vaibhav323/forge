from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from services.file_service.config import settings


class ObjectNotFoundError(Exception):
    """Raised when an object key is missing from object storage."""

    def __init__(self, storage_key: str) -> None:
        self.storage_key = storage_key
        super().__init__(storage_key)


def _endpoint_url() -> str:
    """Build an S3 endpoint URL for MinIO or Supabase Storage.

    Accepted forms:
      localhost:9000
      https://<ref>.storage.supabase.co/storage/v1/s3
      <ref>.storage.supabase.co
    """
    raw = settings.object_storage_endpoint.strip().rstrip("/")
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        host = parsed.netloc
        path = parsed.path.rstrip("/")
        if "storage.supabase.co" in host and "/storage/v1/s3" not in path:
            return f"{parsed.scheme}://{host}/storage/v1/s3"
        return raw
    if "storage.supabase.co" in raw:
        host = raw.split("/")[0]
        return f"https://{host}/storage/v1/s3"
    scheme = "https" if settings.object_storage_secure else "http"
    return f"{scheme}://{raw}"


@lru_cache(maxsize=1)
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(),
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
        config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    client = get_s3_client()
    bucket = settings.object_storage_bucket
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError:
        pass
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise


def put_object(storage_key: str, data: bytes, content_type: str) -> None:
    get_s3_client().put_object(
        Bucket=settings.object_storage_bucket,
        Key=storage_key,
        Body=data,
        ContentType=content_type,
    )


def get_object(storage_key: str) -> bytes:
    try:
        response = get_s3_client().get_object(
            Bucket=settings.object_storage_bucket,
            Key=storage_key,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404", "NotFound"}:
            raise ObjectNotFoundError(storage_key) from exc
        raise
    return response["Body"].read()


def remove_object(storage_key: str) -> None:
    try:
        get_s3_client().delete_object(
            Bucket=settings.object_storage_bucket,
            Key=storage_key,
        )
    except ClientError:
        pass
