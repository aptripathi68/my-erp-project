from __future__ import annotations

from decimal import Decimal, InvalidOperation
from io import BytesIO

import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from masters.models import Item
from masters.models import Group2

from .models import (
    EstimateExpense,
    EstimateProject,
    EstimateProjectSupplier,
    EstimateRawMaterialLine,
    EstimateRawMaterialRate,
    EstimateSupplier,
)
from .services import (
    create_default_suppliers_if_missing,
    ensure_project_cost_heads,
    generate_budget_heads,
    recalculate_cost_heads,
    refresh_budget_totals,
    sync_project_supplier_rates,
)


def _parse_decimal(value: str, default: Decimal = Decimal("0")) -> Decimal:
    value = (value or "").strip()
    if not value:
        return default
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return default


def _parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return timezone.datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _can_manage_rates(user) -> bool:
    return user.role in {"Admin", "Marketing", "Management"}


def _can_manage_costs(user) -> bool:
    return user.role in {"Admin", "Planning", "Management"}


def _can_manage_accounts(user) -> bool:
    return user.role in {"Admin", "Accounts", "Management"}


@login_required
def estimate_list(request):
    projects = EstimateProject.objects.all().prefetch_related("project_suppliers")
    return render(request, "estimation/estimate_list.html", {"projects": projects})


@login_required
def estimate_create(request):
    if request.method == "POST":
        client_name = (request.POST.get("client_name") or "").strip()
        project_name = (request.POST.get("project_name") or "").strip()
        quantity_mt = _parse_decimal(request.POST.get("quantity_mt"))
        notes = (request.POST.get("notes") or "").strip()

        if not client_name or not project_name or quantity_mt <= 0:
            messages.error(request, "Client name, project name, and quantity in MT are required.")
            return render(request, "estimation/estimate_create.html", {})

        project = EstimateProject.objects.create(
            client_name=client_name,
            project_name=project_name,
            quantity_mt=quantity_mt,
            notes=notes,
            created_by=request.user,
            updated_by=request.user,
        )
        create_default_suppliers_if_missing()
        ensure_project_cost_heads(project)
        recalculate_cost_heads(project)
        messages.success(request, f"Estimation inquiry {project.inquiry_no} created.")
        return redirect("estimation:estimate_detail", project_id=project.id)

    return render(request, "estimation/estimate_create.html", {})


@login_required
def estimate_detail(request, project_id: int):
    project = get_object_or_404(
        EstimateProject.objects.prefetch_related(
            "raw_material_lines__item__grade",
            "raw_material_lines__supplier_rates__supplier",
            "project_suppliers__supplier",
            "cost_heads",
            "budget_heads__expenses",
            "boms",
        ),
        pk=project_id,
    )
    ensure_project_cost_heads(project)
    sync_project_supplier_rates(project)
    recalculate_cost_heads(project)
    refresh_budget_totals(project)

    supplier_links = list(project.project_suppliers.select_related("supplier"))
    rate_matrix = []
    for line in project.raw_material_lines.all():
        supplier_rate_map = {rate.supplier_id: rate for rate in line.supplier_rates.all()}
        row_rates = [supplier_rate_map.get(link.supplier_id) for link in supplier_links]
        rate_matrix.append((line, row_rates))

    context = {
        "project": project,
        "group2_list": Group2.objects.order_by("name"),
        "suppliers": EstimateSupplier.objects.filter(is_active=True),
        "supplier_links": supplier_links,
        "rate_matrix": rate_matrix,
        "cost_heads": project.cost_heads.all(),
        "budget_heads": project.budget_heads.all(),
        "can_manage_rates": _can_manage_rates(request.user),
        "can_manage_costs": _can_manage_costs(request.user),
        "can_manage_accounts": _can_manage_accounts(request.user),
    }
    return render(request, "estimation/estimate_detail.html", context)


@login_required
def create_supplier(request):
    if request.method != "POST":
        return redirect("estimation:estimate_list")

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Supplier name is required.")
        return redirect(request.POST.get("next") or "estimation:estimate_list")

    supplier, created = EstimateSupplier.objects.get_or_create(name=name)
    if created:
        supplier.contact_person = (request.POST.get("contact_person") or "").strip()
        supplier.phone = (request.POST.get("phone") or "").strip()
        supplier.email = (request.POST.get("email") or "").strip()
        supplier.save()
        messages.success(request, f"Supplier {supplier.name} created.")
    else:
        messages.info(request, f"Supplier {supplier.name} already exists.")
    return redirect(request.POST.get("next") or "estimation:estimate_list")


@login_required
def add_project_supplier(request, project_id: int):
    project = get_object_or_404(EstimateProject, pk=project_id)
    if request.method != "POST":
        return redirect("estimation:estimate_detail", project_id=project.id)

    supplier_id = request.POST.get("supplier_id")
    supplier = get_object_or_404(EstimateSupplier, pk=supplier_id)
    next_order = project.project_suppliers.count() + 1
    EstimateProjectSupplier.objects.get_or_create(
        project=project,
        supplier=supplier,
        defaults={"column_order": next_order},
    )
    sync_project_supplier_rates(project)
    project.status = EstimateProject.Status.RATE_FINALIZATION
    project.updated_by = request.user
    project.save(update_fields=["status", "updated_by", "updated_at"])
    messages.success(request, f"{supplier.name} added to the rate finalization sheet.")
    return redirect("estimation:estimate_detail", project_id=project.id)


@login_required
def add_raw_material_line(request, project_id: int):
    project = get_object_or_404(EstimateProject, pk=project_id)
    if request.method != "POST":
        return redirect("estimation:estimate_detail", project_id=project.id)

    item_id = request.POST.get("item_id")
    quantity_mt = _parse_decimal(request.POST.get("quantity_mt"))
    if not item_id or quantity_mt <= 0:
        messages.error(request, "Select a raw material item and enter quantity in MT.")
        return redirect("estimation:estimate_detail", project_id=project.id)

    item = get_object_or_404(Item, pk=item_id, is_active=True)
    EstimateRawMaterialLine.objects.create(
        project=project,
        item=item,
        quantity_mt=quantity_mt,
        sort_order=project.raw_material_lines.count() + 1,
    )
    sync_project_supplier_rates(project)
    recalculate_cost_heads(project)
    project.status = EstimateProject.Status.RATE_FINALIZATION
    project.updated_by = request.user
    project.save(update_fields=["status", "updated_by", "updated_at"])
    messages.success(request, "Raw material line added.")
    return redirect("estimation:estimate_detail", project_id=project.id)


@login_required
def update_rate_sheet(request, project_id: int):
    project = get_object_or_404(EstimateProject, pk=project_id)
    if request.method != "POST":
        return redirect("estimation:estimate_detail", project_id=project.id)
    if not _can_manage_rates(request.user):
        messages.error(request, "You do not have permission to update supplier rates.")
        return redirect("estimation:estimate_detail", project_id=project.id)

    for line in project.raw_material_lines.prefetch_related("supplier_rates"):
        final_key = f"final_rate_{line.id}"
        line.final_rate_per_mt = _parse_decimal(request.POST.get(final_key))
        line.save(update_fields=["final_rate_per_mt"])
        for rate in line.supplier_rates.all():
            field_name = f"rate_{line.id}_{rate.supplier_id}"
            rate.rate_per_mt = _parse_decimal(request.POST.get(field_name), default=None)
            rate.save(update_fields=["rate_per_mt"])
        line.recalculate_from_rates(save=True)

    recalculate_cost_heads(project)
    project.status = EstimateProject.Status.QUOTATION_PENDING
    project.updated_by = request.user
    project.save(update_fields=["status", "updated_by", "updated_at"])
    messages.success(request, "Rate finalization sheet updated.")
    return redirect("estimation:estimate_detail", project_id=project.id)


@login_required
def update_cost_heads(request, project_id: int):
    project = get_object_or_404(EstimateProject, pk=project_id)
    if request.method != "POST":
        return redirect("estimation:estimate_detail", project_id=project.id)
    if not _can_manage_costs(request.user):
        messages.error(request, "You do not have permission to update estimation cost heads.")
        return redirect("estimation:estimate_detail", project_id=project.id)
    if project.quotation_locked:
        messages.error(request, "Quotation is locked and cannot be edited.")
        return redirect("estimation:estimate_detail", project_id=project.id)

    for head in project.cost_heads.filter(line_type="ENTRY"):
        if head.is_percentage_editable:
            head.percentage = _parse_decimal(request.POST.get(f"percentage_{head.id}"))
        if head.is_rate_editable and head.code != "RAW_MATERIAL_COST":
            head.rate_per_kg = _parse_decimal(request.POST.get(f"rate_{head.id}"))
        head.remarks = (request.POST.get(f"remarks_{head.id}") or "").strip()
        head.save(update_fields=["percentage", "rate_per_kg", "remarks"])

    recalculate_cost_heads(project)
    project.updated_by = request.user
    project.save(update_fields=["updated_by", "updated_at"])
    messages.success(request, "Quotation calculation updated.")
    return redirect("estimation:estimate_detail", project_id=project.id)


@login_required
def finalize_quotation(request, project_id: int):
    project = get_object_or_404(EstimateProject, pk=project_id)
    if request.method != "POST":
        return redirect("estimation:estimate_detail", project_id=project.id)

    project.quotation_locked = True
    project.status = EstimateProject.Status.QUOTATION_FINALIZED
    project.updated_by = request.user
    project.save(update_fields=["quotation_locked", "status", "updated_by", "updated_at"])
    messages.success(request, "Quotation finalized and locked.")
    return redirect("estimation:estimate_detail", project_id=project.id)


@login_required
def mark_po_received(request, project_id: int):
    project = get_object_or_404(EstimateProject, pk=project_id)
    if request.method != "POST":
        return redirect("estimation:estimate_detail", project_id=project.id)
    if not _can_manage_accounts(request.user) and request.user.role not in {"Planning", "Admin", "Management"}:
        messages.error(request, "You do not have permission to mark PO received.")
        return redirect("estimation:estimate_detail", project_id=project.id)

    project.work_order_no = (request.POST.get("work_order_no") or "").strip()
    project.purchase_order_no = (request.POST.get("purchase_order_no") or "").strip()
    project.purchase_order_date = _parse_date(request.POST.get("purchase_order_date"))
    project.delivery_date = _parse_date(request.POST.get("delivery_date"))
    project.status = EstimateProject.Status.PO_RECEIVED
    project.quotation_locked = True
    project.updated_by = request.user
    project.save()
    generate_budget_heads(project)
    refresh_budget_totals(project)
    messages.success(request, "PO details saved and budget heads generated.")
    return redirect("estimation:estimate_detail", project_id=project.id)


@login_required
def add_expense(request, project_id: int):
    project = get_object_or_404(EstimateProject, pk=project_id)
    if request.method != "POST":
        return redirect("estimation:estimate_detail", project_id=project.id)
    if not _can_manage_accounts(request.user):
        messages.error(request, "You do not have permission to add expenditures.")
        return redirect("estimation:estimate_detail", project_id=project.id)

    budget = get_object_or_404(project.budget_heads.all(), pk=request.POST.get("budget_head_id"))
    amount = _parse_decimal(request.POST.get("amount"))
    description = (request.POST.get("description") or "").strip()
    if amount <= 0 or not description:
        messages.error(request, "Budget head, amount, and description are required.")
        return redirect("estimation:estimate_detail", project_id=project.id)

    EstimateExpense.objects.create(
        budget_head=budget,
        expense_date=request.POST.get("expense_date") or timezone.now().date(),
        reference_no=(request.POST.get("reference_no") or "").strip(),
        amount=amount,
        description=description,
        created_by=request.user,
    )
    refresh_budget_totals(project)
    messages.success(request, "Expenditure recorded and marked pending for approval.")
    return redirect("estimation:estimate_detail", project_id=project.id)


@login_required
def approve_expense(request, expense_id: int):
    expense = get_object_or_404(EstimateExpense.objects.select_related("budget_head__project"), pk=expense_id)
    if request.method != "POST":
        return redirect("estimation:estimate_detail", project_id=expense.budget_head.project_id)
    if request.user.role not in {"Admin", "Management"}:
        messages.error(request, "Only management can approve expenditures.")
        return redirect("estimation:estimate_detail", project_id=expense.budget_head.project_id)

    expense.status = EstimateExpense.Status.APPROVED
    expense.approved_by = request.user
    expense.approved_at = timezone.now()
    expense.save(update_fields=["status", "approved_by", "approved_at"])
    refresh_budget_totals(expense.budget_head.project)
    messages.success(request, "Expenditure approved.")
    return redirect("estimation:estimate_detail", project_id=expense.budget_head.project_id)


@login_required
def export_quotation(request, project_id: int):
    project = get_object_or_404(EstimateProject.objects.prefetch_related("cost_heads"), pk=project_id)
    recalculate_cost_heads(project)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Estimation"

    ws["A2"] = "KALPADEEP INDUSTRIES PVT LTD"
    ws["A3"] = "Estimation"
    ws["B3"] = "Standard"
    ws["C3"] = project.project_name
    ws["D3"] = float(project.quantity_mt)
    ws["A4"] = f"Client : {project.client_name}"
    ws["B4"] = "Percentage"
    ws["C4"] = "Cost per Kg"
    ws["D4"] = "COST"
    ws["E4"] = "Remarks"

    row = 5
    for head in project.cost_heads.all():
        ws.cell(row=row, column=1, value=head.name)
        ws.cell(row=row, column=2, value=float(head.percentage) if head.percentage is not None else "")
        ws.cell(row=row, column=3, value=float(head.rate_per_kg or 0))
        ws.cell(row=row, column=4, value=float(head.amount or 0))
        ws.cell(row=row, column=5, value=head.remarks)
        row += 1

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{project.inquiry_no}_quotation.xlsx"'
    return response
