"""Object storage: private S3 in production, a local folder in development (same interface)."""

import asyncio
import os
from pathlib import Path

from app.config import settings
from app.errors import ServiceUnavailable
from app.services.auth import tokens


class Storage:
    async def presign_put(self, key: str, mime: str, size: int) -> dict: ...
    async def presign_get(self, key: str) -> str: ...
    async def get(self, key: str, max_bytes: int) -> bytes: ...
    async def put(self, key: str, data: bytes, mime: str) -> None: ...
    async def exists(self, key: str) -> int | None: ...
    async def delete(self, key: str) -> None: ...


class S3Storage(Storage):
    def __init__(self, bucket: str):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        # The regional endpoint, not s3.amazonaws.com: browsers PUT straight to presigned URLs, and S3 answers the
        # global name for a non-us-east-1 bucket with a redirect that a CORS request cannot follow.
        endpoint = settings.aws_endpoint_url_s3 or f"https://s3.{settings.aws_region}.amazonaws.com"
        self.client = boto3.client(
            "s3", region_name=settings.aws_region, endpoint_url=endpoint,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=20,
                          s3={"addressing_style": "auto" if settings.aws_endpoint_url_s3 else "virtual"}),
        )

    async def presign_put(self, key: str, mime: str, size: int) -> dict:
        url = await asyncio.to_thread(self.client.generate_presigned_url, "put_object",
                                      Params={"Bucket": self.bucket, "Key": key, "ContentType": mime,
                                              "ContentLength": size}, ExpiresIn=300)
        return {"url": url, "method": "PUT", "headers": {"Content-Type": mime}}

    async def presign_get(self, key: str) -> str:
        return await asyncio.to_thread(self.client.generate_presigned_url, "get_object",
                                       Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=600)

    async def get(self, key: str, max_bytes: int) -> bytes:
        def _get() -> bytes:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
            if obj["ContentLength"] > max_bytes:
                raise ValueError("object too large")
            return obj["Body"].read(max_bytes + 1)

        return await asyncio.to_thread(_get)

    async def put(self, key: str, data: bytes, mime: str) -> None:
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=mime,
                                CacheControl="private, max-age=31536000, immutable")

    async def exists(self, key: str) -> int | None:
        def _head():
            try:
                return self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
            except self.client.exceptions.ClientError:
                return None

        return await asyncio.to_thread(_head)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)


class LocalStorage(Storage):
    """Development only. Signed URLs point at /api/v1/_local_storage/{token}."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("bad key")
        return path

    def _url(self, payload: dict) -> str:
        return f"{settings.app_url}/api/v1/_local_storage/{tokens.sign_state(payload, 10, 'storage')}"

    async def presign_put(self, key: str, mime: str, size: int) -> dict:
        return {"url": self._url({"key": key, "op": "put", "mime": mime, "size": size}), "method": "PUT",
                "headers": {"Content-Type": mime}}

    async def presign_get(self, key: str) -> str:
        return self._url({"key": key, "op": "get"})

    async def get(self, key: str, max_bytes: int) -> bytes:
        data = await asyncio.to_thread(self.path(key).read_bytes)
        if len(data) > max_bytes:
            raise ValueError("object too large")
        return data

    async def put(self, key: str, data: bytes, mime: str) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def exists(self, key: str) -> int | None:
        path = self.path(key)
        return path.stat().st_size if path.exists() else None

    async def delete(self, key: str) -> None:
        path = self.path(key)
        if path.exists():
            os.remove(path)


_storage: Storage | None = None


def storage() -> Storage:
    global _storage
    if _storage is None:
        if settings.s3_bucket:
            _storage = S3Storage(settings.s3_bucket)
        elif not settings.is_production:
            _storage = LocalStorage(settings.local_upload_dir)
        else:
            raise ServiceUnavailable("Uploads are not configured", code="uploads_unavailable")
    return _storage
