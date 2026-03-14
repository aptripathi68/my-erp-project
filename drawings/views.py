from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import DrawingUploadSelectForm
from .models import DrawingSheetRevision
from .services import create_or_update_sheet_revision
from .storage import generate_presigned_preview_url, generate_presigned_download_url
from django.http import JsonResponse
from procurement.models import BOMHeader, BOMMark
from .forms import DrawingUploadSelectForm, BulkDrawingUploadForm
from .models import DrawingSheetRevision, DrawingImportBatch
from .services import create_or_update_sheet_revision, process_drawing_bundle

@login_required
def home(request):
    return render(request, "drawings/home.html")


@login_required
def upload_from_bom(request):
    if request.method == "POST":
        form = DrawingUploadSelectForm(request.POST, request.FILES)
        if form.is_valid():
            bom = form.cleaned_data["bom"]
            drawing_no = form.cleaned_data["drawing_no"]
            title = form.cleaned_data["title"]
            sheet_no = form.cleaned_data["sheet_no"]
            revision_no = form.cleaned_data["revision_no"]
            upload_file = form.cleaned_data["upload_file"]

            revision = create_or_update_sheet_revision(
                drawing_no=drawing_no,
                title=title,
                project=bom,
                sheet_no=sheet_no,
                revision_no=revision_no,
                uploaded_file=upload_file,
                uploaded_by=request.user,
            )

            messages.success(
                request,
                (
                    f"Drawing uploaded successfully for BOM #{bom.id}, "
                    f"Drawing {drawing_no}, Sheet {sheet_no}, Revision {revision_no}. "
                    f"Please preview and confirm before production use."
                ),
            )
            return redirect("drawings:revision_detail", pk=revision.pk)
    else:
        initial = {}
        bom_id = request.GET.get("bom")
        drawing_no = request.GET.get("drawing_no")

        if bom_id:
            try:
                bom = BOMHeader.objects.get(pk=bom_id)
                initial["bom"] = bom
            except BOMHeader.DoesNotExist:
                pass

        if drawing_no:
            initial["drawing_no"] = drawing_no

        form = DrawingUploadSelectForm(initial=initial)

    return render(
        request,
        "drawings/upload_from_bom.html",
        {
            "form": form,
            "page_title": "Drawings Upload from BOM",
        },
    )


@login_required
def revision_detail(request, pk):
    revision = get_object_or_404(DrawingSheetRevision, pk=pk)

    preview_url = None
    download_url = None

    if revision.file_key:
        try:
            preview_url = generate_presigned_preview_url(revision.file_key)
        except Exception:
            preview_url = None

        try:
            download_url = generate_presigned_download_url(revision.file_key)
        except Exception:
            download_url = None

    return render(
        request,
        "drawings/revision_detail.html",
        {
            "revision": revision,
            "preview_url": preview_url,
            "download_url": download_url,
        },
    )


@login_required
def confirm_revision(request, pk):
    revision = get_object_or_404(DrawingSheetRevision, pk=pk)

    revision.verification_status = DrawingSheetRevision.STATUS_VERIFIED
    revision.verified_by = request.user
    revision.verified_at = timezone.now()
    revision.is_current = True
    revision.save()

    messages.success(request, "Drawing verified and activated successfully.")
    return redirect("drawings:revision_detail", pk=revision.pk)


@login_required
def reject_revision(request, pk):
    revision = get_object_or_404(DrawingSheetRevision, pk=pk)

    revision.verification_status = DrawingSheetRevision.STATUS_REJECTED
    revision.verified_by = request.user
    revision.verified_at = timezone.now()
    revision.is_current = False
    revision.save()

    messages.warning(request, "Drawing rejected. Please re-upload the correct file.")
    return redirect("drawings:revision_detail", pk=revision.pk)

@login_required
def bom_drawing_numbers(request):
    bom_id = request.GET.get("bom_id")
    results = []

    if bom_id:
        try:
            bom = BOMHeader.objects.get(pk=bom_id)
            drawing_nos = (
                BOMMark.objects.filter(bom=bom)
                .exclude(drawing_no__isnull=True)
                .exclude(drawing_no__exact="")
                .values_list("drawing_no", flat=True)
                .distinct()
                .order_by("drawing_no")
            )
            results = [{"value": d, "label": d} for d in drawing_nos]
        except BOMHeader.DoesNotExist:
            results = []

    return JsonResponse({"drawing_numbers": results})
@login_required
def bulk_upload(request):
    if request.method == "POST":
        form = BulkDrawingUploadForm(request.POST, request.FILES)
        if form.is_valid():
            bom = form.cleaned_data["bom"]
            upload_file = form.cleaned_data["upload_file"]
            batch_name = form.cleaned_data.get("batch_name") or ""

            batch = DrawingImportBatch.objects.create(
                bom=bom,
                batch_name=batch_name,
                source_filename=upload_file.name,
                uploaded_by=request.user,
            )

            process_drawing_bundle(batch=batch, uploaded_file=upload_file)

            messages.success(
                request,
                "Bulk drawing upload batch created successfully. File analysis records have been generated.",
            )
            return redirect("admin:drawings_drawingimportbatch_change", batch.pk)
    else:
        form = BulkDrawingUploadForm()

    return render(
        request,
        "drawings/bulk_upload.html",
        {
            "form": form,
            "page_title": "Bulk Drawing Upload",
        },
    )