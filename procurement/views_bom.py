from __future__ import annotations

import tempfile
from io import BytesIO

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

import openpyxl
from openpyxl.utils import get_column_letter

from .models import BOMHeader, BOMMark, BOMComponent
from .services.bom_importer import validate_and_extract_workbook


@staff_member_required
def bom_upload(request):
    """
    Simple online page:
    - Upload Excel
    - Validate
    - If ok: import
    """
    context = {}

    if request.method == "POST" and request.FILES.get("file"):
        f = request.FILES["file"]
        bom_name = request.POST.get("bom_name") or f.name

        # Save to a temp file for openpyxl
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            for chunk in f.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        result = validate_and_extract_workbook(tmp_path)

        # Store validation errors in session so they can be downloaded in Excel
        request.session["bom_validation_errors"] = result.get("errors", [])

        context["result"] = result
        context["bom_name"] = bom_name
        context["tmp_path"] = tmp_path  # used only for import in same request flow

        # If user clicked "Import" and validation ok
        if request.POST.get("action") == "import" and result["ok"]:
            with transaction.atomic():
                header = BOMHeader.objects.create(
                    bom_name=bom_name,
                    uploaded_by=request.user,
                    uploaded_at=timezone.now(),
                )

                # create marks
                mark_map = {}  # (sheet, mark_no) -> BOMMark
                for row in result["extracted"]:
                    key = (row.sheet_name, row.mark_no or "")
                    if key not in mark_map:
                        mark_map[key] = BOMMark.objects.create(
                            bom=header,
                            sheet_name=row.sheet_name,
                            mark_no=row.mark_no or "",
                            drawing_no=row.drawing_no or "",
                        )

                comps = []
                for row in result["extracted"]:
                    m = mark_map[(row.sheet_name, row.mark_no or "")]
                    comps.append(
                        BOMComponent(
                            mark=m,
                            item_no=row.item_no or "",
                            item_id=row.item_id,
                            item_description_raw=row.item_description_raw,
                            qty_all=row.qty_all,
                            length_mm=row.length_mm,
                            line_weight_kg=row.line_weight_kg,
                            excel_row=row.excel_row,
                        )
                    )

                BOMComponent.objects.bulk_create(comps, batch_size=2000)

            context["imported_bom_id"] = header.id

    return render(request, "procurement/bom_upload.html", context)


@staff_member_required
def download_bom_validation_errors(request):
    """
    Download latest BOM validation errors from session as Excel.
    """
    errors = request.session.get("bom_validation_errors", [])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOM Validation Errors"

    headers = [
        "Error Type",
        "Sheet Name",
        "Excel Row",
        "Mark No",
        "Item No",
        "BOM Item Description",
        "BOM Grade",
        "Message",
        "Normalized Section",
        "Normalized Grade",
        "Possible Grades For Section",
        "Suggestions",
    ]
    ws.append(headers)

    for err in errors:
        possible_grades = err.get("possible_grades_for_section", [])
        suggestions = err.get("suggestions", [])

        ws.append([
            err.get("type", ""),
            err.get("sheet_name", ""),
            err.get("excel_row", ""),
            err.get("mark_no", ""),
            err.get("item_no", ""),
            err.get("item_description_in_bom", ""),
            err.get("grade_in_bom", ""),
            err.get("message", ""),
            err.get("normalized_section", ""),
            err.get("normalized_grade", ""),
            ", ".join(possible_grades) if isinstance(possible_grades, list) else str(possible_grades or ""),
            ", ".join(suggestions) if isinstance(suggestions, list) else str(suggestions or ""),
        ])

    for col_idx, column_cells in enumerate(ws.columns, start=1):
        max_len = 0
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            if len(value) > max_len:
                max_len = len(value)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="bom_validation_errors.xlsx"'
    return response


@staff_member_required
def bom_export_master(request, bom_id: int):
    """
    Download master BOM as Excel for monitoring.
    """
    header = get_object_or_404(BOMHeader, id=bom_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOM_MASTER"

    ws.append([
        "bom_name", "sheet_name", "mark_no", "drawing_no",
        "item_no", "item_description_raw", "item_description_master",
        "qty_all", "length_mm", "line_weight_kg", "excel_row"
    ])

    marks = header.marks.select_related().prefetch_related("components", "components__item").all()
    for m in marks:
        for c in m.components.all():
            ws.append([
                header.bom_name,
                m.sheet_name,
                m.mark_no,
                m.drawing_no or "",
                c.item_no,
                c.item_description_raw,
                c.item.item_description,
                float(c.qty_all),
                float(c.length_mm) if c.length_mm is not None else "",
                float(c.line_weight_kg) if c.line_weight_kg is not None else "",
                c.excel_row,
            ])

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="BOM_MASTER_{header.id}.xlsx"'
    wb.save(resp)
    return resp