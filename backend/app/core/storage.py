import uuid
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, filename: str, content: bytes, content_type: str) -> str:
        """Persist a file and return its public URL."""


class LocalStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self.base_path = Path(settings.local_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, content: bytes, content_type: str) -> str:
        ext = Path(filename).suffix
        key = f"{uuid.uuid4().hex}{ext}"
        (self.base_path / key).write_bytes(content)
        return f"{settings.local_storage_public_url}/{key}"


class S3StorageBackend(StorageBackend):
    def __init__(self) -> None:
        import boto3

        client_kwargs: dict = {"region_name": settings.s3_region}
        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        # Only pass static credentials when they were configured explicitly, so
        # that leaving them blank falls back to boto3's own resolution chain
        # rather than authenticating as nobody - see the note on s3_access_key_id
        # in app/core/config.py.
        if settings.s3_access_key_id:
            client_kwargs["aws_access_key_id"] = settings.s3_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.s3_secret_access_key
        self.client = boto3.client("s3", **client_kwargs)
        self.bucket = settings.s3_bucket

    async def save(self, filename: str, content: bytes, content_type: str) -> str:
        ext = Path(filename).suffix
        key = f"uploads/{uuid.uuid4().hex}{ext}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)
        if settings.s3_endpoint_url:
            return f"{settings.s3_endpoint_url}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.{settings.s3_region}.amazonaws.com/{key}"


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Cached: building a boto3 client costs ~100-300ms (it parses botocore's
    service JSON), which would otherwise be paid on every upload request."""
    if settings.storage_backend == "s3":
        return S3StorageBackend()
    return LocalStorageBackend()
