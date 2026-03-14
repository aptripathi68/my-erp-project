import zipfile
import tempfile
import os


from django.db import transaction

from .models import Drawing, DrawingSheet, DrawingSheetRevision
from .storage import build_drawing_object_key, upload_drawing_file
from .models import DrawingImportBatch, DrawingImportFile


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

    revision = DrawingSheetRevision.objects.filter(
        drawing_sheet=sheet,
        revision_no=revision_no,
    ).first()

    if revision and revision.verification_status == DrawingSheetRevision.STATUS_REJECTED:
        revision.file_key = object_key
        revision.original_filename = original_filename
        revision.content_type = content_type
        revision.file_size = file_size
        revision.is_current = False
        revision.verification_status = DrawingSheetRevision.STATUS_PENDING
        revision.uploaded_by = uploaded_by
        revision.verified_by = None
        revision.verified_at = None
        revision.save()
    else:
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
    
    def process_drawing_bundle(batch: DrawingImportBatch, uploaded_file):
        """
        Process uploaded drawing bundle (ZIP or PDF).
        Extract files and create DrawingImportFile records.
        """

        temp_dir = tempfile.mkdtemp()

        file_path = os.path.join(temp_dir, uploaded_file.name)

        with open(file_path, "wb+") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # ZIP case
        if uploaded_file.name.lower().endswith(".zip"):

            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            page_counter = 1

            for root, dirs, files in os.walk(temp_dir):
                for f in files:

                    if not f.lower().endswith(".pdf"):
                        continue

                    DrawingImportFile.objects.create(
                        batch=batch,
                        original_filename=f,
                        page_number=page_counter,
                        status="UPLOADED"
                    )

                    page_counter += 1

        # Single PDF bundle case
        elif uploaded_file.name.lower().endswith(".pdf"):

            DrawingImportFile.objects.create(
                batch=batch,
                original_filename=uploaded_file.name,
                page_number=1,
                status="UPLOADED"
            )

    return revision