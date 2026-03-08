from __future__ import annotations

import tempfile
from io import BytesIO
from datetime import date

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

import openpyxl
from openpyxl.utils import get_column_letter

from .models import BOMHeader, BOMMark, BOMComponent
from .services.bom_importer import validate_and_extract_workbook, workbook_sheet_headers


@staff_member_required
def bom_upload(request):
    context = {}

    # Step 1: upload file and detect headers
    if request.method == "POST" and request.FILES.get("file"):
        f = request.FILES["file"]

        bom_name = (request.POST.get("bom_name") or f.name).strip()
        project_name = (request.POST.get("project_name") or "").strip()
        client_name = (request.POST.get("client_name") or "").strip()
        purchase_order_no = (request.POST.get("purchase_order_no") or "").strip()
        purchase_order_date = (request.POST.get("purchase_order_date") or "").strip()

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            for chunk in f.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        headers_info = workbook_sheet_headers(tmp_path)

        request.session["bom_tmp_path"] = tmp_path
        request.session["bom_name"] = bom_name
        request.session["project_name"] = project_name
        request.session["client_name"] = client_name
        request.session["purchase_order_no"] = purchase_order_no
        request.session["purchase_order_date"] = purchase_order_date

        context["bom_name"] = bom_name
        context["project_name"] = project_name
        context["client_name"] = client_name
        context["purchase_order_no"] = purchase_order_no
        context["purchase_order_date"] = purchase_order_date
        context["headers_info"] = headers_info
        context["mapping_step"] = True
        context["result"] = None

        return render(request, "procurement/bom_upload.html", context)

    # Step 2: validate or import using user mapping
    if request.method == "POST" and request.POST.get("action") in ["validate", "import"]:
        tmp_path = request.session.get("bom_tmp_path")
        bom_name = request.session.get("bom_name", "Uploaded BOM")
        project_name = request.session.get("project_name", "")
        client_name = request.session.get("client_name", "")
        purchase_order_no = request.session.get("purchase_order_no", "")
        purchase_order_date_raw = request.session.get("purchase_order_date", "")

        if not tmp_path:
            context["error"] = "Please upload the BOM file first."
            return render(request, "procurement/bom_upload.html", context)

        headers_info = workbook_sheet_headers(tmp_path)

        user_sheet_mappings = {}

        for sheet_name, info in headers_info.items():
            if not info.get("detected"):
                continue

            user_sheet_mappings[sheet_name] = {
                "item_description": request.POST.get(f"{sheet_name}__item_description", ""),
                "grade": request.POST.get(f"{sheet_name}__grade", ""),
                "mark_no": request.POST.get(f"{sheet_name}__mark_no", ""),
                "drawing_no": request.POST.get(f"{sheet_name}__drawing_no", ""),
                "item_no": request.POST.get(f"{sheet_name}__item_no", ""),
                "qty_all": request.POST.get(f"{sheet_name}__qty_all", ""),
                "length": request.POST.get(f"{sheet_name}__length", ""),
                "width": request.POST.get(f"{sheet_name}__width", ""),
                "thk": request.POST.get(f"{sheet_name}__thk", ""),
                "unit_wt": request.POST.get(f"{sheet_name}__unit_wt", ""),
                "revision_no": request.POST.get(f"{sheet_name}__revision_no", ""),
                "area_of_supply": request.POST.get(f"{sheet_name}__area_of_supply", ""),
            }

        result = validate_and_extract_workbook(
            tmp_path,
            user_sheet_mappings=user_sheet_mappings,
        )

        request.session["bom_validation_errors"] = result.get("errors", [])

        context["result"] = result
        context["bom_name"] = bom_name
        context["project_name"] = project_name
        context["client_name"] = client_name
        context["purchase_order_no"] = purchase_order_no
        context["purchase_order_date"] = purchase_order_date_raw
        context["headers_info"] = headers_info
        context["mapping_step"] = True

        if request.POST.get("action") == "import" and result["ok"]:
            # Convert purchase order date string to python date
            purchase_order_date = None
            if purchase_order_date_raw:
                try:
                    purchase_order_date = date.fromisoformat(purchase_order_date_raw)
                except ValueError:
                    purchase_order_date = None

            with transaction.atomic():
                header = BOMHeader.objects.create(
                    bom_name=bom_name,
                    project_name=project_name,
                    client_name=client_name,
                    purchase_order_no=purchase_order_no,
                    purchase_order_date=purchase_order_date,
                    uploaded_by=request.user,
                    uploaded_at=timezone.now(),
                )

                # create marks
                mark_map = {}
                for row in result["extracted"]:
                    key = (
                        row.sheet_name,
                        row.mark_no or "",
                        getattr(row, "drawing_no", "") or "",
                        getattr(row, "revision_no", "") or "",
                        getattr(row, "area_of_supply", "") or "",
                    )

                    if key not in mark_map:
                        mark_map[key] = BOMMark.objects.create(
                            bom=header,
                            sheet_name=row.sheet_name,
                            mark_no=row.mark_no or "",
                            drawing_no=row.drawing_no or "",
                            revision_no=getattr(row, "revision_no", "") or "",
                            area_of_supply=getattr(row, "area_of_supply", "") or "",
                        )

                comps = []
                for row in result["extracted"]:
                    key = (
                        row.sheet_name,
                        row.mark_no or "",
                        getattr(row, "drawing_no", "") or "",
                        getattr(row, "revision_no", "") or "",
                        getattr(row, "area_of_supply", "") or "",
                    )

                    m = mark_map[key]

                    comps.append(
                        BOMComponent(
                            mark=m,
                            item_no=row.item_no or "",
                            item_id=row.item_id,
                            item_description_raw=row.item_description_raw,
                            grade_raw=getattr(row, "grade_raw", "") or "",
                            item_part_quantity=row.qty_all,
                            length_mm=row.length_mm,
                            width_mm=row.width_mm,
                            line_weight_kg=row.line_weight_kg,
                            excel_row=row.excel_row,
                        )
                    )

                BOMComponent.objects.bulk_create(comps, batch_size=2000)

            context["imported_bom_id"] = header.id

        return render(request, "procurement/bom_upload.html", context)

    return render(request, "procurement/bom_upload.html", context)


@staff_member_required
def download_bom_validation_errors(request):
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
        "BOM Unit Weight",
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
            err.get("unit_weight_in_bom", ""),
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
    header = get_object_or_404(BOMHeader, id=bom_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOM_MASTER"

    ws.append([
        "bom_name",
        "project_name",
        "client_name",
        "purchase_order_no",
        "purchase_order_date",
        "sheet_name",
        "mark_no",
        "drawing_no",
        "revision_no",
        "area_of_supply",
        "item_no",
        "item_description_raw",
        "grade_raw",
        "item_description_master",
        "item_part_quantity",
        "length_mm",
        "width_mm",
        "line_weight_kg",
        "excel_row",
    ])

    marks = header.marks.select_related().prefetch_related("components", "components__item").all()

    for m in marks:
        for c in m.components.all():
            ws.append([
                header.bom_name,
                getattr(header, "project_name", "") or "",
                getattr(header, "client_name", "") or "",
                getattr(header, "purchase_order_no", "") or "",
                header.purchase_order_date.isoformat() if getattr(header, "purchase_order_date", None) else "",
                m.sheet_name,
                m.mark_no,
                m.drawing_no or "",
                getattr(m, "revision_no", "") or "",
                getattr(m, "area_of_supply", "") or "",
                c.item_no,
                c.item_description_raw,
                getattr(c, "grade_raw", "") or "",
                c.item.item_description if c.item_id else "",
                float(c.item_part_quantity),
                float(c.length_mm) if c.length_mm is not None else "",
                float(c.width_mm) if c.width_mm is not None else "",
                float(c.line_weight_kg) if c.line_weight_kg is not None else "",
                c.excel_row,
            ])

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="BOM_MASTER_{header.id}.xlsx"'
    wb.save(resp)
    return resp