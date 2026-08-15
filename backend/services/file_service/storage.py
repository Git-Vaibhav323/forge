from __future__ import annotations

from minio import Minio
from minio.error import S3Error

from services.file_service.config import settings

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            secure=settings.object_storage_secure,
        )
    return _client


def ensure_bucket() -> None:
    client = get_minio_client()
    bucket = settings.object_storage_bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def put_object(storage_key: str, data: bytes, content_type: str) -> None:
    client = get_minio_client()
    from io import BytesIO

    client.put_object(
        settings.object_storage_bucket,
        storage_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def remove_object(storage_key: str) -> None:
    client = get_minio_client()
    try:
        client.remove_object(settings.object_storage_bucket, storage_key)
    except S3Error:
        pass
