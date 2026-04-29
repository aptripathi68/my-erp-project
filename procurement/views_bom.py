from __future__ import annotations

import tempfile
from io import BytesIO
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import re

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

import openpyxl
from openpyxl.utils import get_column_letter

from estimation.models import EstimateProject
from drawings.models import Drawing
from .models import BOMColumnMapping, BOMComponent, BOMHeader, BOMMark
from .services.backbone import duplicate_work_order_exists, normalize_wo_number, sync_bom_to_backbone
from .services.planning import bom_material_evaluation, bom_planning_summary, generate_int_erc_jobs
from .services.bom_importer import build_header_signature, validate_and_extract_workbook, workbook_sheet_headers


MAPPING_FIELDS = (
    "item_description",
    "grade",
    "mark_no",
    "erc_quantity",
    "item_no",
    "qty_all",
    "length",
    "width",
    "unit_wt",
)

STANDARD_BOM_COLUMNS = [
    "Dispatch MKD No",
    "Assembly Qty",
    "Part Mark / Item No",
    "Section / Profile",
    "Grade / Quality",
    "Part-Qty per Assembly",
    "Length mm",
    "Width mm",
    "Weight per Assembly",
    "Remarks",
]


def _has_planning_access(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.is_staff
        or user.role in {"Admin", "Planning", "Management", "Store", "Procurement"}
    )


def _session_safe_errors(errors):
    safe = []
    for err in errors:
        row = {}
        for k, v in err.items():
            if isinstance(v, list):
                row[k] = [str(x) for x in v]
            elif v is None:
                row[k] = ""
            else:
                row[k] = str(v)
        safe.append(row)
    return safe


def _date_cell_to_iso(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return value


def _parse_decimal(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _quantity_to_count(value) -> int:
    qty = Decimal(value or "0")
    if qty <= 0:
        return 0
    return int(qty.to_integral_value(rounding=ROUND_CEILING))


def _mark_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "-", value or "").strip("-").upper()
    return token or "MARK"


def _internal_erc_mark(wo_number: str, dispatch_mkd_no: str, sequence: int) -> str:
    suffix = f"{_mark_token(dispatch_mkd_no)}-{sequence}"
    prefix_budget = max(1, 99 - len(suffix))
    prefix = _mark_token(wo_number)[:prefix_budget].strip("-") or "WO"
    return f"{prefix}-{suffix}"[:100]


def _create_working_bom(
    *,
    result,
    estimate_project,
    bom_name,
    project_name,
    client_name,
    purchase_order_no,
    purchase_order_date,
    delivery_date,
    order_rate,
    order_value,
    user,
) -> BOMHeader:
    with transaction.atomic():
        header = BOMHeader.objects.create(
            estimate_project=estimate_project,
            bom_name=bom_name,
            project_name=project_name,
            client_name=client_name,
            purchase_order_no=purchase_order_no,
            purchase_order_date=purchase_order_date,
            delivery_date=delivery_date,
            order_rate=order_rate,
            order_value=order_value,
            uploaded_by=user,
            uploaded_at=timezone.now(),
        )

        rows_by_dispatch = {}
        for row in result["extracted"]:
            key = (row.sheet_name, row.mark_no or "")
            rows_by_dispatch.setdefault(key, []).append(row)

        components = []
        for (sheet_name, dispatch_mkd_no), rows in rows_by_dispatch.items():
            assembly_qty = max(_quantity_to_count(row.erc_quantity) for row in rows) or 1
            for sequence in range(1, assembly_qty + 1):
                bom_mark = BOMMark.objects.create(
                    bom=header,
                    sheet_name=sheet_name,
                    erc_mark=_internal_erc_mark(bom_name, dispatch_mkd_no, sequence),
                    erc_quantity=Decimal("1"),
                    main_section=rows[0].item_description_raw or "",
                    drawing_no=dispatch_mkd_no or "",
                    drawing=None,
                )
                for row in rows:
                    components.append(
                        BOMComponent(
                            bom_mark=bom_mark,
                            part_mark=row.item_no or "",
                            section_name=row.item_description_raw or "",
                            grade_name=getattr(row, "grade_raw", "") or "",
                            part_quantity_per_assy=row.qty_all,
                            length_mm=row.length_mm,
                            width_mm=row.width_mm,
                            engg_weight_kg=row.line_weight_kg,
                            item_id=row.item_id,
                            item_description_raw=row.item_description_raw or "",
                            excel_row=row.excel_row,
                        )
                    )

        BOMComponent.objects.bulk_create(components, batch_size=2000)
        return header


def _build_user_sheet_mappings(request, headers_info):
    user_sheet_mappings = {}

    for sheet_name, info in headers_info.items():
        if not info.get("detected"):
            continue

        user_sheet_mappings[sheet_name] = {
            "item_description": request.POST.get(f"{sheet_name}__item_description", "").strip(),
            "grade": request.POST.get(f"{sheet_name}__grade", "").strip(),
            "mark_no": request.POST.get(f"{sheet_name}__mark_no", "").strip(),
            "erc_quantity": request.POST.get(f"{sheet_name}__erc_quantity", "").strip(),
            "item_no": request.POST.get(f"{sheet_name}__item_no", "").strip(),
            "qty_all": request.POST.get(f"{sheet_name}__qty_all", "").strip(),
            "length": request.POST.get(f"{sheet_name}__length", "").strip(),
            "width": request.POST.get(f"{sheet_name}__width", "").strip(),
            "unit_wt": request.POST.get(f"{sheet_name}__unit_wt", "").strip(),
        }

    return user_sheet_mappings


def _has_any_mapping(sheet_mappings):
    if not sheet_mappings:
        return False

    for sheet_map in sheet_mappings.values():
        if any(v for v in sheet_map.values()):
            return True
    return False


def _clean_sheet_mapping(mapping):
    if not isinstance(mapping, dict):
        return {}
    return {
        field: (mapping.get(field) or "").strip()
        for field in MAPPING_FIELDS
    }


def _load_persisted_mappings(headers_info):
    loaded = {}

    for sheet_name, info in headers_info.items():
        if not info.get("detected"):
            continue

        signature = info.get("header_signature") or build_header_signature(info.get("headers", []))
        if not signature:
            continue

        saved = (
            BOMColumnMapping.objects
            .filter(sheet_name=sheet_name, header_signature=signature)
            .order_by("-updated_at")
            .first()
        )
        if saved and saved.mapping:
            loaded[sheet_name] = _clean_sheet_mapping(saved.mapping)

    return loaded


def _persist_sheet_mappings(headers_info, sheet_mappings, user):
    for sheet_name, info in headers_info.items():
        if not info.get("detected"):
            continue

        mapping = _clean_sheet_mapping((sheet_mappings or {}).get(sheet_name, {}))
        if not any(mapping.values()):
            continue

        signature = info.get("header_signature") or build_header_signature(info.get("headers", []))
        if not signature:
            continue

        obj, created = BOMColumnMapping.objects.get_or_create(
            sheet_name=sheet_name,
            header_signature=signature,
            defaults={
                "mapping": mapping,
                "created_by": user,
                "updated_by": user,
            },
        )

        if not created:
            obj.mapping = mapping
            obj.updated_by = user
            obj.save(update_fields=["mapping", "updated_by", "updated_at"])


@login_required
def planning_dashboard(request):
    if not _has_planning_access(request.user):
        messages.error(request, "You do not have permission to access planning and material evaluation.")
        return redirect("dashboard_home")

    return render(
        request,
        "procurement/planning_dashboard.html",
        {
            "summaries": bom_planning_summary(),
        },
    )


@login_required
def planning_bom_detail(request, bom_id: int):
    if not _has_planning_access(request.user):
        messages.error(request, "You do not have permission to access planning and material evaluation.")
        return redirect("dashboard_home")

    bom = get_object_or_404(BOMHeader, pk=bom_id)
    evaluation = bom_material_evaluation(bom)
    jobs = (
        bom.marks.prefetch_related("fabrication_jobs")
        .order_by("sheet_name", "erc_mark")
    )
    return render(
        request,
        "procurement/planning_bom_detail.html",
        {
            "bom": bom,
            "evaluation": evaluation,
            "marks": jobs,
        },
    )


@login_required
def generate_bom_int_erc(request, bom_id: int):
    if request.method != "POST":
        return redirect("procurement:planning_bom_detail", bom_id=bom_id)
    if not _has_planning_access(request.user):
        messages.error(request, "You do not have permission to generate INT-ERC units.")
        return redirect("dashboard_home")

    bom = get_object_or_404(BOMHeader, pk=bom_id)
    result = generate_int_erc_jobs(bom)
    messages.success(
        request,
        (
            "INT-ERC generation completed. "
            f"New units: {result['created_jobs']}, component rows: {result['created_components']}."
        ),
    )
    return redirect("procurement:planning_bom_detail", bom_id=bom.id)


@staff_member_required
def download_standard_bom_template(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOM_UPLOAD"
    ws.append(STANDARD_BOM_COLUMNS)

    instructions = wb.create_sheet("Instructions")
    instructions.append(["Instruction", "Details"])
    instructions.append(["Do not rename BOM_UPLOAD headers", "Paste or enter all BOM rows below the header row in BOM_UPLOAD."])
    instructions.append(["BOM header details", "WO Number, project, client, PO, delivery, rate, and value are entered once on the upload screen."])
    instructions.append(["Dispatch MKD No", "Customer/company identity of the fabricated item."])
    instructions.append(["Assembly Qty", "Number of separate fabricated units for this Dispatch MKD No."])
    instructions.append(["Section / Profile", "Must match Item Master section/profile text."])
    instructions.append(["Grade / Quality", "Must match Item Master grade. Example: IS:2062 E250BR."])
    instructions.append(["Part-Qty per Assembly", "Quantity of this child part in one fabricated unit."])
    instructions.append(["Weight per Assembly", "Weight contribution of this child part for one fabricated unit."])
    instructions.append(["Working BOM", "After validation, Create Working BOM will create one internal ERC/Main Mark for each Assembly Qty."])

    widths = {
        "A": 24, "B": 14, "C": 18, "D": 22, "E": 20, "F": 22,
        "G": 12, "H": 12, "I": 20, "J": 30,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = 'attachment; filename="kalpadeep_standard_bom_template.xlsx"'
    wb.save(resp)
    return resp


@staff_member_required
def bom_upload(request):
    context = {}
    estimate_project = None
    estimate_id = request.GET.get("estimate_project") or request.POST.get("estimate_project")
    if estimate_id:
        try:
            estimate_project = EstimateProject.objects.get(pk=estimate_id)
        except EstimateProject.DoesNotExist:
            estimate_project = None

    # STEP 1: Upload standard template -> validate immediately
    if request.method == "POST" and request.FILES.get("file"):
        f = request.FILES["file"]

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            for chunk in f.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        bom_name = (request.POST.get("bom_name") or (estimate_project.work_order_no if estimate_project else "")).strip()
        project_name = (request.POST.get("project_name") or (estimate_project.project_name if estimate_project else "")).strip()
        client_name = (request.POST.get("client_name") or (estimate_project.client_name if estimate_project else "")).strip()
        purchase_order_no = (request.POST.get("purchase_order_no") or (estimate_project.purchase_order_no if estimate_project else "")).strip()
        purchase_order_date = (request.POST.get("purchase_order_date") or (estimate_project.purchase_order_date.isoformat() if estimate_project and estimate_project.purchase_order_date else "")).strip()
        delivery_date = (request.POST.get("delivery_date") or (estimate_project.delivery_date.isoformat() if estimate_project and estimate_project.delivery_date else "")).strip()
        order_rate = (request.POST.get("order_rate") or "").strip()
        order_value = (request.POST.get("order_value") or "").strip()

        result = validate_and_extract_workbook(tmp_path)
        request.session["bom_validation_errors"] = _session_safe_errors(result.get("errors", []))

        request.session["bom_tmp_path"] = tmp_path
        request.session["bom_name"] = bom_name
        request.session["project_name"] = project_name
        request.session["client_name"] = client_name
        request.session["purchase_order_no"] = purchase_order_no
        request.session["purchase_order_date"] = purchase_order_date
        request.session["delivery_date"] = delivery_date
        request.session["order_rate"] = order_rate
        request.session["order_value"] = order_value
        request.session["estimate_project_id"] = estimate_project.id if estimate_project else None

        context["bom_name"] = bom_name
        context["project_name"] = project_name
        context["client_name"] = client_name
        context["purchase_order_no"] = purchase_order_no
        context["purchase_order_date"] = purchase_order_date
        context["delivery_date"] = delivery_date
        context["order_rate"] = order_rate
        context["order_value"] = order_value
        context["estimate_project"] = estimate_project
        context["uploaded_step"] = True
        context["result"] = result

        return render(request, "procurement/bom_upload.html", context)

    # STEP 2: Re-validate / Create working BOM from the uploaded standard template
    if request.method == "POST" and request.POST.get("action") in ["validate", "create_working_bom"]:
        tmp_path = request.session.get("bom_tmp_path")
        bom_name = request.session.get("bom_name", "Uploaded BOM")
        project_name = request.session.get("project_name", "")
        client_name = request.session.get("client_name", "")
        purchase_order_no = request.session.get("purchase_order_no", "")
        purchase_order_date_raw = request.session.get("purchase_order_date", "")
        delivery_date_raw = request.session.get("delivery_date", "")
        order_rate_raw = request.session.get("order_rate", "")
        order_value_raw = request.session.get("order_value", "")
        estimate_project_id = request.session.get("estimate_project_id")

        if not tmp_path:
            context["error"] = "Please upload the BOM file first."
            return render(request, "procurement/bom_upload.html", context)

        estimate_project = None
        if estimate_project_id:
            try:
                estimate_project = EstimateProject.objects.get(pk=estimate_project_id)
            except EstimateProject.DoesNotExist:
                estimate_project = None

        result = validate_and_extract_workbook(tmp_path)

        request.session["bom_validation_errors"] = _session_safe_errors(result.get("errors", []))

        context["result"] = result
        context["bom_name"] = bom_name
        context["project_name"] = project_name
        context["client_name"] = client_name
        context["purchase_order_no"] = purchase_order_no
        context["purchase_order_date"] = purchase_order_date_raw
        context["delivery_date"] = delivery_date_raw
        context["order_rate"] = order_rate_raw
        context["order_value"] = order_value_raw
        context["estimate_project"] = estimate_project
        context["uploaded_step"] = True

        if request.POST.get("action") == "create_working_bom" and result["ok"]:
            wo_number = normalize_wo_number(bom_name)
            if not wo_number:
                context["error"] = "WO Number is required."
                return render(request, "procurement/bom_upload.html", context)
            if duplicate_work_order_exists(wo_number):
                context["error"] = "This WO already exists."
                return render(request, "procurement/bom_upload.html", context)

            purchase_order_date = None
            if purchase_order_date_raw:
                try:
                    purchase_order_date = date.fromisoformat(purchase_order_date_raw)
                except ValueError:
                    purchase_order_date = None

            delivery_date = None
            if delivery_date_raw:
                try:
                    delivery_date = date.fromisoformat(delivery_date_raw)
                except ValueError:
                    delivery_date = None

            order_rate = _parse_decimal(order_rate_raw)
            order_value = _parse_decimal(order_value_raw)

            header = _create_working_bom(
                result=result,
                estimate_project=estimate_project,
                bom_name=bom_name,
                project_name=project_name,
                client_name=client_name,
                purchase_order_no=purchase_order_no,
                purchase_order_date=purchase_order_date,
                delivery_date=delivery_date,
                order_rate=order_rate,
                order_value=order_value,
                user=request.user,
            )
            request.session["working_bom_id"] = header.id
            context["working_bom_id"] = header.id

        return render(request, "procurement/bom_upload.html", context)

    context["selected_mappings"] = request.session.get("bom_selected_mappings", {})
    context["bom_name"] = request.session.get("bom_name", "")
    context["project_name"] = request.session.get("project_name", "")
    context["client_name"] = request.session.get("client_name", "")
    context["purchase_order_no"] = request.session.get("purchase_order_no", "")
    context["purchase_order_date"] = request.session.get("purchase_order_date", "")
    context["delivery_date"] = request.session.get("delivery_date", "")
    context["order_rate"] = request.session.get("order_rate", "")
    context["order_value"] = request.session.get("order_value", "")
    context["working_bom_id"] = request.session.get("working_bom_id")
    context["estimate_project"] = estimate_project
    if estimate_project:
        context["bom_name"] = context["bom_name"] or estimate_project.work_order_no
        context["project_name"] = context["project_name"] or estimate_project.project_name
        context["client_name"] = context["client_name"] or estimate_project.client_name
        context["purchase_order_no"] = context["purchase_order_no"] or estimate_project.purchase_order_no
        context["purchase_order_date"] = (
            context["purchase_order_date"]
            or (estimate_project.purchase_order_date.isoformat() if estimate_project.purchase_order_date else "")
        )
        context["delivery_date"] = (
            context["delivery_date"]
            or (estimate_project.delivery_date.isoformat() if estimate_project.delivery_date else "")
        )
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
        "ERC Mark",
        "Part Mark",
        "Section Name",
        "Grade Name",
        "Engg Weight (kg)",
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
        "WO Number",
        "Project Name",
        "Client Name",
        "Purchase Order No",
        "Purchase Order Date",
        "Delivery Date",
        "Order Rate",
        "Order Value",
        "Source Sheet",
        "Dispatch MKD No",
        "Internal ERC/Main Mark",
        "Part Mark / Item No",
        "Section / Profile",
        "Grade / Quality",
        "Item Master Description",
        "Part-Qty per Assembly",
        "Length mm",
        "Width mm",
        "Weight per Assembly",
        "ERC/Main Mark Weight",
        "Source Excel Row",
    ])

    marks = header.marks.prefetch_related("components", "components__item").all()

    for m in marks:
        mark_weight = sum((c.engg_weight_kg or Decimal("0")) for c in m.components.all())
        for c in m.components.all():
            ws.append([
                header.bom_name,
                header.project_name or "",
                header.client_name or "",
                header.purchase_order_no or "",
                header.purchase_order_date.isoformat() if header.purchase_order_date else "",
                header.delivery_date.isoformat() if getattr(header, "delivery_date", None) else "",
                float(header.order_rate) if getattr(header, "order_rate", None) is not None else "",
                float(header.order_value) if getattr(header, "order_value", None) is not None else "",
                m.sheet_name,
                m.drawing_no or "",
                m.erc_mark or "",
                c.part_mark or "",
                c.section_name or "",
                c.grade_name or "",
                c.item.item_description if c.item_id else "",
                float(c.part_quantity_per_assy),
                float(c.length_mm) if c.length_mm is not None else "",
                float(c.width_mm) if c.width_mm is not None else "",
                float(c.engg_weight_kg) if c.engg_weight_kg is not None else "",
                float(mark_weight),
                c.excel_row,
            ])

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="BOM_MASTER_{header.id}.xlsx"'
    wb.save(resp)
    return resp


@staff_member_required
def working_bom_verified(request, bom_id: int):
    if request.method != "POST":
        return redirect("procurement:bom_upload")

    header = get_object_or_404(BOMHeader, id=bom_id)
    backbone_result = sync_bom_to_backbone(header, created_by=request.user)
    header.is_locked = True
    header.save(update_fields=["is_locked"])
    request.session.pop("working_bom_id", None)
    messages.success(
        request,
        (
            "Working BOM verified. "
            f"{backbone_result['created_ercs']} ERC record(s), "
            f"{backbone_result['created_units']} INT-ERC unit(s), and "
            f"{backbone_result['created_requirements']} requirement line(s) created."
        ),
    )
    return redirect("procurement:planning_bom_detail", bom_id=header.id)


@staff_member_required
def working_bom_not_verified(request, bom_id: int):
    if request.method != "POST":
        return redirect("procurement:bom_upload")

    header = get_object_or_404(BOMHeader, id=bom_id)
    header.delete()
    request.session.pop("working_bom_id", None)
    messages.warning(request, "Working BOM discarded. Please correct and upload the BOM again.")
    return redirect("procurement:bom_upload")


@staff_member_required
def bom_delete(request, bom_id):
    header = get_object_or_404(BOMHeader, id=bom_id)

    if request.method == "POST":
        drawing_count = Drawing.objects.filter(project=header).count()
        with transaction.atomic():
            Drawing.objects.filter(project=header).delete()
            header.delete()
        if drawing_count:
            messages.success(request, f"BOM and {drawing_count} linked drawing record(s) deleted successfully.")
        else:
            messages.success(request, "BOM deleted successfully.")
        return redirect("procurement:planning_dashboard")

    linked_drawing_count = Drawing.objects.filter(project=header).count()
    return render(
        request,
        "procurement/bom_delete_confirm.html",
        {
            "header": header,
            "linked_drawing_count": linked_drawing_count,
        },
    )
