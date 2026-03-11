from django.db import transaction

from .models import Drawing, DrawingSheet, DrawingSheetRevision
from .storage import build_drawing_object_key, upload_drawing_file


@transaction.atomic
def create_or_update_sheet_revision(
    *,
    drawing_no,
    title="",
    project=None,
    sheet_no="1",
    revision_no="R0",
    uploaded_file=None,
    uploaded_by=None,
):
    drawing, _ = Drawing.objects.get_or_create(
        project=project,
        drawing_no=drawing_no,
        defaults={
            "title": title or "",
            "created_by": uploaded_by,
        },
    )

    if title and drawing.title != title:
        drawing.title = title
        drawing.save(update_fields=["title"])

    sheet, _ = DrawingSheet.objects.get_or_create(
        drawing=drawing,
        sheet_no=str(sheet_no),
    )

    original_filename = getattr(uploaded_file, "name", "") or f"{drawing_no}.pdf"
    content_type = getattr(uploaded_file, "content_type", "application/pdf") or "application/pdf"
    file_size = getattr(uploaded_file, "size", None)

    project_code = drawing.project_id if drawing.project_id else "COMMON"

    object_key = build_drawing_object_key(
        project_code=project_code,
        drawing_no=drawing.drawing_no,
        sheet_no=sheet.sheet_no,
        revision_no=revision_no,
        filename=original_filename,
    )

    upload_drawing_file(
        file_obj=uploaded_file,
        object_key=object_key,
        content_type=content_type,
    )

    revision = DrawingSheetRevision.objects.create(
        drawing_sheet=sheet,
        revision_no=revision_no,
        file_key=object_key,
        original_filename=original_filename,
        content_type=content_type,
        file_size=file_size,
        is_current=False,
        verification_status=DrawingSheetRevision.STATUS_PENDING,
        uploaded_by=uploaded_by,
    )

    return revision