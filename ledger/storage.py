import mimetypes
import os
import uuid
from datetime import datetime

from django.conf import settings

from drawings.storage import get_r2_client, sanitize_part


CONTENT_TYPE_EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def build_inventory_photo_object_key(*, stock_for: str, object_type: str, filename: str) -> str:
    original_name, original_ext = os.path.splitext(filename or "raw-material-photo.jpg")
    content_ext = original_ext.lower() or ".jpg"
    safe_stock_for = sanitize_part(stock_for or "STORE")
    safe_object_type = sanitize_part(object_type or "RAW")
    safe_name = sanitize_part(original_name or "photo")
    date_part = datetime.now().strftime("%Y/%m/%d")
    return (
        f"inventory/raw_material_photos/"
        f"{date_part}/"
        f"{safe_stock_for}/"
        f"{safe_object_type}/"
        f"{safe_name}_{uuid.uuid4().hex}{content_ext}"
    )


def upload_inventory_photo(file_obj, object_key: str, content_type: str = "") -> str:
    provided_content_type = (content_type or getattr(file_obj, "content_type", "") or "").lower()
    if not provided_content_type:
        provided_content_type = mimetypes.guess_type(getattr(file_obj, "name", ""))[0] or "application/octet-stream"

    client = get_r2_client()
    client.upload_fileobj(
        Fileobj=file_obj,
        Bucket=settings.MEDIA_BUCKET_NAME,
        Key=object_key,
        ExtraArgs={"ContentType": provided_content_type},
    )

    public_base_url = getattr(settings, "MEDIA_PUBLIC_BASE_URL", "") or os.getenv("MEDIA_PUBLIC_BASE_URL", "")
    if public_base_url:
        return f"{public_base_url.rstrip('/')}/{object_key}"
    return object_key
