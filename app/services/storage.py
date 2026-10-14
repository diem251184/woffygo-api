import os
import uuid
import boto3
from botocore.config import Config

R2_BUCKET = os.getenv("R2_BUCKET_NAME", "woffygo-storage")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT = os.getenv("R2_ENDPOINT_URL")

# Cliente S3 para Cloudflare R2
s3_client = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT or f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)


def upload_image_to_r2(file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """Sube un archivo a Cloudflare R2 y retorna la URL pública."""
    ext = filename.split(".")[-1] if "." in filename else "jpg"
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    s3_client.put_object(
        Bucket=R2_BUCKET,
        Key=unique_name,
        Body=file_bytes,
        ContentType=content_type,
    )

    # Si se configuró un subdominio r2.dev o dominio propio
    r2_public_base = os.getenv("R2_PUBLIC_URL")
    if r2_public_base:
        return f"{r2_public_base.rstrip('/')}/{unique_name}"

    return f"https://{R2_BUCKET}.{R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{unique_name}"
