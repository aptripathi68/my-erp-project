import os
import re
from urllib.parse import quote

import boto3
from django.conf import settings


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, "AWS_S3_REGION_NAME", "auto"),
    )


def sanitize_part(value: str) -> str:
    value = str(value or "").strip()
    value = value.replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value or "NA"


def build_drawing_object_key(project_code, drawing_no, sheet_no, revision_no, filename):
    ext = os.path.splitext(filename)[1] or ".pdf"

    safe_project = sanitize_part(project_code or "COMMON")
    safe_drawing = sanitize_part(drawing_no)
    safe_sheet = sanitize_part(sheet_no)
    safe_revision = sanitize_part(revision_no)

    final_name = f"{safe_drawing}_S{safe_sheet}_REV_{safe_revision}{ext}"

    return (
        f"drawings/"
        f"{safe_project}/"
        f"{safe_drawing}/"
        f"sheet_{safe_sheet}/"
        f"rev_{safe_revision}/"
        f"{final_name}"
    )


def upload_drawing_file(file_obj, object_key, content_type="application/pdf"):
    client = get_r2_client()

    client.upload_fileobj(
        Fileobj=file_obj,
        Bucket=settings.DRAWINGS_BUCKET_NAME,
        Key=object_key,
        ExtraArgs={
            "ContentType": content_type,
        },
    )

    return object_key


def generate_presigned_download_url(object_key, expires_in=300):
    client = get_r2_client()

    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.DRAWINGS_BUCKET_NAME,
            "Key": object_key,
            "ResponseContentDisposition": f'attachment; filename="{quote(os.path.basename(object_key))}"',
        },
        ExpiresIn=expires_in,
    )


def generate_presigned_preview_url(object_key, expires_in=300):
    client = get_r2_client()

    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.DRAWINGS_BUCKET_NAME,
            "Key": object_key,
            "ResponseContentDisposition": "inline",
            "ResponseContentType": "application/pdf",
        },
        ExpiresIn=expires_in,
    )