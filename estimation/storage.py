from __future__ import annotations

import os
from urllib.parse import quote

from django.conf import settings

from drawings.storage import get_r2_client, sanitize_part


def build_supplier_quotation_object_key(project, supplier_name: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1] or ".bin"
    safe_inquiry = sanitize_part(project.inquiry_no or project.project_name or "estimate")
    safe_supplier = sanitize_part(supplier_name or "supplier")
    safe_name = sanitize_part(os.path.splitext(filename)[0]) + ext
    return (
        f"estimation/"
        f"{safe_inquiry}/"
        f"supplier_quotations/"
        f"{safe_supplier}/"
        f"{safe_name}"
    )


def upload_supplier_quotation_file(file_obj, object_key: str, content_type: str = "application/octet-stream") -> str:
    client = get_r2_client()
    client.upload_fileobj(
        Fileobj=file_obj,
        Bucket=settings.MEDIA_BUCKET_NAME,
        Key=object_key,
        ExtraArgs={"ContentType": content_type},
    )
    return object_key


def generate_supplier_quotation_download_url(object_key: str, expires_in: int = 300) -> str:
    client = get_r2_client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.MEDIA_BUCKET_NAME,
            "Key": object_key,
            "ResponseContentDisposition": f'attachment; filename="{quote(os.path.basename(object_key))}"',
        },
        ExpiresIn=expires_in,
    )
