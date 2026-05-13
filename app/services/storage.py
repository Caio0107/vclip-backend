"""Upload pra S3/R2 ou serve local."""
import os
import shutil
from pathlib import Path

import boto3
from botocore.client import Config

from app.config import settings


def _s3_client():
    if not settings.s3_bucket:
        return None
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def upload_clip(local_path: str, key: str) -> str:
    """Upload retorna URL pública."""
    client = _s3_client()
    if client is None:
        # fallback local: copia pra /data/public/<key>
        public_dir = Path(settings.data_dir) / "public" / os.path.dirname(key)
        public_dir.mkdir(parents=True, exist_ok=True)
        dest = Path(settings.data_dir) / "public" / key
        shutil.copy(local_path, dest)
        return f"{settings.public_base_url}/{key}"

    client.upload_file(
        local_path,
        settings.s3_bucket,
        key,
        ExtraArgs={"ContentType": "video/mp4", "CacheControl": "public, max-age=31536000"},
    )
    base = settings.public_base_url.rstrip("/")
    return f"{base}/{key}"
