import json
from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
import openpyxl

from masters.models import Item

from .forms import (
    InventoryInwardForm,
    StockLocationForm,
    StockObjectDetailEditForm,
    TemporaryIssueForm,
    TemporaryReturnForm,
    TransferStoreRecordsForm,
)
from .models import StockLedgerEntry, StockLocation, StockObject, StockTxn, StockTxnLine
from .services.stock_engine import post_stock_txn
from .services.stock_queries import (
    editable_store_stock_objects,
    stock_by_item,
    stock_by_location,
    stock_by_store_item,
)
from .storage import build_inventory_photo_object_key, upload_inventory_photo


def _has_inventory_access(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.role in {"Admin", "Store", "Management", "Planning", "Procurement"}
    )


def _can_manage_inventory(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.role in {"Admin", "Store", "Management"}
    )


def _can_admin_inventory(user):
    return user.is_authenticated and (user.is_superuser or user.role == "Admin")


def _store_delete_status(location):
    has_ledger_entries = StockLedgerEntry.objects.filter(location=location).exists()
    has_txn_lines = StockTxnLine.objects.filter(from_location=location).exists() or StockTxnLine.objects.filter(to_location=location).exists()
    if has_ledger_entries or has_txn_lines:
        return {
            "can_delete": False,
            "reason": "Used in stock records",
        }
    return {
        "can_delete": True,
        "reason": "Safe to delete",
    }


def _purge_reserved_store_records(location):
    ledger_qs = StockLedgerEntry.objects.filter(location=location)
    stock_object_ids = set(ledger_qs.exclude(stock_object_id__isnull=True).values_list("stock_object_id", flat=True))
    ledger_deleted = ledger_qs.count()
    ledger_qs.delete()

    txn_line_qs = StockTxnLine.objects.filter(from_location=location) | StockTxnLine.objects.filter(to_location=location)
    txn_line_qs = txn_line_qs.distinct()
    stock_object_ids.update(txn_line_qs.exclude(stock_object_id__isnull=True).values_list("stock_object_id", flat=True))
    txn_ids = list(txn_line_qs.values_list("txn_id", flat=True).distinct())
    txn_line_deleted = txn_line_qs.count()
    txn_line_qs.delete()

    orphan_txn_qs = StockTxn.objects.filter(id__in=txn_ids).annotate(line_count=Count("lines")).filter(line_count=0)
    orphan_txn_deleted = orphan_txn_qs.count()
    orphan_txn_qs.delete()

    removable_stock_objects = StockObject.objects.filter(id__in=stock_object_ids)
    removable_stock_objects = removable_stock_objects.exclude(stockledgerentry__isnull=False).exclude(stocktxnline__isnull=False).distinct()
    stock_object_deleted = removable_stock_objects.count()
    removable_stock_objects.delete()

    location.delete()

    return {
        "ledger_deleted": ledger_deleted,
        "txn_line_deleted": txn_line_deleted,
        "orphan_txn_deleted": orphan_txn_deleted,
        "stock_object_deleted": stock_object_deleted,
    }


def _temporary_return_totals(issue_txn):
    totals = (
        StockTxnLine.objects.filter(txn__parent_txn=issue_txn, txn__txn_type="TEMP_RETURN", txn__posted=True)
        .aggregate(qty=Sum("qty"), weight=Sum("weight"))
    )
    return totals["qty"] or Decimal("0"), totals["weight"] or Decimal("0")


def _refresh_temporary_issue_status(issue_txn):
    if not issue_txn or not issue_txn.is_temporary_issue:
        return
    line = issue_txn.lines.first()
    if not line:
        return
    returned_qty, returned_weight = _temporary_return_totals(issue_txn)
    if returned_qty <= 0 and returned_weight <= 0:
        status = "PENDING_ERP_INTEGRATION"
    elif returned_qty >= (line.qty or Decimal("0")) and returned_weight >= (line.weight or Decimal("0")):
        status = "RETURNED"
    else:
        status = "PARTIALLY_RETURNED"
    if issue_txn.bridge_status != status:
        issue_txn.bridge_status = status
        issue_txn.save(update_fields=["bridge_status"])


def _build_stock_object(*, object_type, item, qty, weight, source_type, remarks="", qr_code="", photo_url=""):
    return StockObject.objects.create(
        object_type=object_type,
        source_type=source_type,
        item=item,
        qty=qty,
        weight=weight,
        qr_code=qr_code or None,
        photo_url=photo_url or "",
        remarks=remarks,
    )


def _upload_inventory_photo_if_present(form, *, stock_for: str, object_type: str) -> str:
    upload = form.cleaned_data.get("raw_material_photo")
    if not upload:
        return ""
    object_key = build_inventory_photo_object_key(
        stock_for=stock_for,
        object_type=object_type,
        filename=getattr(upload, "name", "") or "raw-material-photo.jpg",
    )
    return upload_inventory_photo(
        upload,
        object_key,
        content_type=getattr(upload, "content_type", "") or "application/octet-stream",
    )


def _inventory_context(request):
    selected_store_id = request.GET.get("store")
    active_store_locations = StockLocation.objects.filter(is_active=True, location_type="STORE").order_by("name")
    selected_store = None
    if selected_store_id:
        try:
            selected_store = active_store_locations.get(id=selected_store_id)
        except StockLocation.DoesNotExist:
            selected_store = None
    store_locations = StockLocation.objects.filter(location_type="STORE").order_by("is_active", "name")
    active_store_locations = store_locations.filter(is_active=True)
    inactive_store_locations = store_locations.filter(is_active=False)
    stock_by_location_rows = stock_by_location()
    store_stock_rows = [row for row in stock_by_location_rows if row["location_type"] == "STORE"]
    process_stock_rows = [
        row
        for row in stock_by_location_rows
        if row["location_type"] in {"FABRICATION", "PAINTING", "DISPATCH_SECTION"}
    ]
    issue_rows = []
    inactive_store_location_rows = [
        {
            "location": location,
            "transfer_form": TransferStoreRecordsForm(),
            **_store_delete_status(location),
        }
        for location in inactive_store_locations
    ]
    issue_qs = (
        StockTxn.objects.filter(txn_type="TEMP_ISSUE", posted=True)
        .select_related("created_by")
        .prefetch_related("lines__item", "lines__from_location", "lines__to_location", "child_transactions")
        .order_by("-created_at")
    )
    for issue in issue_qs[:50]:
        line = issue.lines.first()
        returned_qty, returned_weight = _temporary_return_totals(issue)
        issue_rows.append(
            {
                "txn": issue,
                "line": line,
                "returned_qty": returned_qty,
                "returned_weight": returned_weight,
                "pending_qty": max((line.qty or Decimal("0")) - returned_qty, Decimal("0")) if line else Decimal("0"),
                "pending_weight": max((line.weight or Decimal("0")) - returned_weight, Decimal("0")) if line else Decimal("0"),
            }
        )

    return {
        "locations": StockLocation.objects.order_by("location_type", "name"),
        "store_locations": store_locations,
        "active_store_locations": active_store_locations,
        "inactive_store_locations": inactive_store_locations,
        "inactive_store_location_rows": inactive_store_location_rows,
        "store_location_count": active_store_locations.count(),
        "inactive_store_location_count": inactive_store_locations.count(),
        "stock_by_item": stock_by_item(),
        "stock_by_location": stock_by_location_rows,
        "store_stock_rows": store_stock_rows,
        "store_item_rows": stock_by_store_item(location_id=selected_store.id if selected_store else None),
        "editable_store_item_rows": editable_store_stock_objects(location_id=selected_store.id if selected_store else None),
        "selected_store": selected_store,
        "process_stock_rows": process_stock_rows,
        "temporary_issue_rows": issue_rows,
        "pending_issue_count": sum(1 for row in issue_rows if row["txn"].bridge_status != "RETURNED"),
        "can_manage_inventory": _can_manage_inventory(request.user),
        "can_admin_inventory": _can_admin_inventory(request.user),
    }


@login_required
def export_store_stock_excel(request):
    if not _has_inventory_access(request.user):
        messages.error(request, "You do not have permission to access inventory management.")
        return redirect("dashboard_home")

    selected_store_id = request.GET.get("store")
    selected_store = None
    if selected_store_id:
        selected_store = get_object_or_404(StockLocation, pk=selected_store_id, is_active=True, location_type="STORE")

    rows = stock_by_store_item(location_id=selected_store.id if selected_store else None)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Store Stock"

    heading = "Store-wise Items in Store"
    if selected_store:
        heading = f"Store-wise Items in Store - {selected_store.name}"
    ws.append([heading])
    ws.append([])
    ws.append(["Store", "Rack No", "Shelf No", "Bin No", "Item Master ID", "Item Description", "Object Type", "Qty", "Weight (Kgs)"])

    for row in rows:
        ws.append(
            [
                row["location_name"],
                row["rack_number"],
                row["shelf_number"],
                row["bin_number"],
                row["item_master_id"],
                row["item_description"],
                row["object_type"],
                row["qty"],
                row["weight"],
            ]
        )

    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            value = "" if cell.value is None else str(cell.value)
            max_length = max(max_length, len(value))
        ws.column_dimensions[column_letter].width = min(max_length + 4, 40)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = "store_stock_register.xlsx"
    if selected_store:
        safe_name = selected_store.name.replace(" ", "_")
        filename = f"store_stock_register_{safe_name}.xlsx"

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _render_inventory_form(request, *, page_title, page_intro, form, submit_label, post_url):
    context = _inventory_context(request)
    context.update(
        {
            "page_title": page_title,
            "page_intro": page_intro,
            "form": form,
            "submit_label": submit_label,
            "post_url": post_url,
            "back_url": "ledger:inventory_dashboard",
        }
    )
    return render(request, "ledger/inventory_form.html", context)


def _render_store_form(request, *, form, page_title="Store Creation", editing_location=None):
    context = _inventory_context(request)
    context.update(
        {
            "page_title": page_title,
            "page_intro": "Create or maintain store locations here. Latitude and longitude should be captured from the mobile GPS only at this stage.",
            "form": form,
            "submit_label": "Save Store Location" if editing_location is None else "Update Store Location",
            "post_url": "ledger:create_location" if editing_location is None else "ledger:edit_location",
            "post_kwargs": {} if editing_location is None else {"location_id": editing_location.id},
            "back_url": "ledger:inventory_dashboard",
            "store_locations": StockLocation.objects.filter(location_type="STORE").order_by("is_active", "name"),
            "editing_location": editing_location,
        }
    )
    return render(request, "ledger/store_location_form.html", context)


def _render_stock_object_edit_form(request, *, form, stock_object, current_store_name):
    context = _inventory_context(request)
    context.update(
        {
            "page_title": "Edit Stored Item Details",
            "page_intro": (
                f"Update only rack, shelf, bin, and remarks for the current stored item. "
                f"Quantity and weight history remain unchanged. Current store: {current_store_name}."
            ),
            "form": form,
            "submit_label": "Update Stored Item Details",
            "post_url": "ledger:edit_stock_object_details",
            "post_kwargs": {"stock_object_id": stock_object.id},
            "back_url": "ledger:inventory_dashboard",
            "stock_object": stock_object,
            "current_store_name": current_store_name,
        }
    )
    return render(request, "ledger/store_item_edit.html", context)


@login_required
def inventory_dashboard(request):
    if not _has_inventory_access(request.user):
        messages.error(request, "You do not have permission to access inventory management.")
        return redirect("dashboard_home")
    return render(request, "ledger/inventory_home.html", _inventory_context(request))


@login_required
def edit_stock_object_details(request, stock_object_id: int):
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can edit stored item details.")
        return redirect("ledger:inventory_dashboard")

    stock_object = get_object_or_404(StockObject, pk=stock_object_id)
    balance_row = (
        StockLedgerEntry.objects.filter(
            stock_object=stock_object,
            location__location_type="STORE",
            location__is_active=True,
        )
        .values("location_id", "location__name")
        .annotate(qty=Sum("qty"), weight=Sum("weight"))
        .order_by("location__name")
        .first()
    )
    if not balance_row or ((balance_row["qty"] or Decimal("0")) <= 0 and (balance_row["weight"] or Decimal("0")) <= 0):
        messages.error(request, "This stored item is not currently available in an active store for editing.")
        return redirect("ledger:inventory_dashboard")

    current_store_name = balance_row["location__name"]
    if request.method == "GET":
        form = StockObjectDetailEditForm(instance=stock_object)
        return _render_stock_object_edit_form(
            request,
            form=form,
            stock_object=stock_object,
            current_store_name=current_store_name,
        )

    form = StockObjectDetailEditForm(request.POST, instance=stock_object)
    if form.is_valid():
        form.save()
        messages.success(request, "Stored item details updated.")
        return redirect("ledger:inventory_dashboard")

    return _render_stock_object_edit_form(
        request,
        form=form,
        stock_object=stock_object,
        current_store_name=current_store_name,
    )


@login_required
def create_location(request):
    if request.method == "GET":
        if not _has_inventory_access(request.user):
            messages.error(request, "You do not have permission to access inventory management.")
            return redirect("dashboard_home")
        return _render_store_form(request, form=StockLocationForm())
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can create stock locations.")
        return redirect("ledger:inventory_dashboard")
    form = StockLocationForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Stock location saved.")
        return redirect("ledger:inventory_dashboard")
    return _render_store_form(request, form=form)


@login_required
def edit_location(request, location_id: int):
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can edit stock locations.")
        return redirect("ledger:inventory_dashboard")
    location = get_object_or_404(StockLocation, pk=location_id, location_type="STORE")
    if request.method == "GET":
        return _render_store_form(request, form=StockLocationForm(instance=location), page_title="Edit Store Location", editing_location=location)
    form = StockLocationForm(request.POST, instance=location)
    if form.is_valid():
        form.save()
        messages.success(request, "Store location updated.")
        return redirect("ledger:create_location")
    return _render_store_form(request, form=form, page_title="Edit Store Location", editing_location=location)


@login_required
def delete_location(request, location_id: int):
    if request.method != "POST":
        return redirect("ledger:create_location")
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can delete stock locations.")
        return redirect("ledger:inventory_dashboard")
    location = get_object_or_404(StockLocation, pk=location_id, location_type="STORE")
    location.is_active = False
    location.save(update_fields=["is_active"])
    messages.success(request, "Store location removed from active use.")
    return redirect("ledger:create_location")


@login_required
def permanent_delete_location(request, location_id: int):
    if request.method != "POST":
        return redirect("ledger:create_location")
    if not _can_admin_inventory(request.user):
        messages.error(request, "Only Admin can permanently delete reserved store locations.")
        return redirect("ledger:create_location")
    location = get_object_or_404(StockLocation, pk=location_id, location_type="STORE", is_active=False)
    try:
        location.delete()
    except ProtectedError:
        messages.error(
            request,
            "This store location is already linked with stock records and cannot be permanently deleted.",
        )
    else:
        messages.success(request, "Reserved store location permanently deleted.")
    return redirect("ledger:create_location")


@login_required
def purge_reserved_location_data(request, location_id: int):
    if request.method != "POST":
        return redirect("ledger:create_location")
    if not _can_admin_inventory(request.user):
        messages.error(request, "Only Admin can purge dummy reserved store data.")
        return redirect("ledger:create_location")

    location = get_object_or_404(StockLocation, pk=location_id, location_type="STORE", is_active=False)
    delete_status = _store_delete_status(location)
    if delete_status["can_delete"]:
        messages.info(request, "This reserved store is already safe to delete directly. Use permanent delete.")
        return redirect("ledger:create_location")

    with transaction.atomic():
        deleted = _purge_reserved_store_records(location)

    messages.success(
        request,
        (
            "Dummy reserved store data purged successfully. "
            f"Ledger rows deleted: {deleted['ledger_deleted']}, "
            f"transaction lines deleted: {deleted['txn_line_deleted']}, "
            f"empty transactions deleted: {deleted['orphan_txn_deleted']}, "
            f"stock objects deleted: {deleted['stock_object_deleted']}."
        ),
    )
    return redirect("ledger:create_location")


@login_required
def transfer_store_records(request, location_id: int):
    if request.method != "POST":
        return redirect("ledger:inventory_dashboard")
    if not _can_admin_inventory(request.user):
        messages.error(request, "Only Admin can transfer reserved store records.")
        return redirect("ledger:inventory_dashboard")

    source_location = get_object_or_404(StockLocation, pk=location_id, location_type="STORE", is_active=False)
    form = TransferStoreRecordsForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please select a valid active store for transfer.")
        return redirect("ledger:inventory_dashboard")

    target_location = form.cleaned_data["target_location"]
    if target_location.id == source_location.id:
        messages.error(request, "Source and target store cannot be the same.")
        return redirect("ledger:inventory_dashboard")

    with transaction.atomic():
        ledger_count = StockLedgerEntry.objects.filter(location=source_location).update(location=target_location)
        from_count = StockTxnLine.objects.filter(from_location=source_location).update(from_location=target_location)
        to_count = StockTxnLine.objects.filter(to_location=source_location).update(to_location=target_location)

    messages.success(
        request,
        (
            f"Transferred reserved store records to {target_location.name}. "
            f"Ledger rows updated: {ledger_count}, from-location rows updated: {from_count}, "
            f"to-location rows updated: {to_count}."
        ),
    )
    return redirect("ledger:inventory_dashboard")


@login_required
def create_inventory_inward(request):
    if request.method == "GET":
        if not _has_inventory_access(request.user):
            messages.error(request, "You do not have permission to access inventory management.")
            return redirect("dashboard_home")
        return _render_inventory_form(
            request,
            page_title="Item Entry In Store",
            page_intro="Select an already-created store location. Use this for item entry against a project, item entry of spare store, opening stock, new purchase inward, return entry, and correction entry.",
            form=InventoryInwardForm(),
            submit_label="Record Item Entry",
            post_url="ledger:create_inventory_inward",
        )
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can record inward inventory.")
        return redirect("ledger:inventory_dashboard")

    form = InventoryInwardForm(request.POST, request.FILES)
    if form.is_valid():
        entry_type = form.cleaned_data["entry_type"]
        object_type = form.cleaned_data["object_type"]
        stock_for = form.cleaned_data["stock_for"]
        item = form.cleaned_data["item"]
        location = form.cleaned_data["location"]
        qty = form.cleaned_data["qty"]
        weight = form.cleaned_data["weight"]
        qr_code = form.cleaned_data.get("qr_code") or ""
        remarks = form.cleaned_data.get("remarks") or ""
        photo_url = _upload_inventory_photo_if_present(form, stock_for=stock_for, object_type=object_type)

        txn_type_map = {
            ("OPENING", "RAW"): "OPENING_RAW",
            ("OPENING", "OFFCUT"): "OPENING_OFFCUT",
            ("OPENING", "SCRAP"): "OPENING_SCRAP",
            ("NEW_PURCHASE", "RAW"): "GRN_RAW",
            ("NEW_PURCHASE", "OFFCUT"): "IN_OFFCUT",
            ("NEW_PURCHASE", "SCRAP"): "IN_SCRAP",
            ("RETURN", "RAW"): "RETURN_FAB",
            ("RETURN", "OFFCUT"): "IN_OFFCUT",
            ("RETURN", "SCRAP"): "IN_SCRAP",
            ("CORRECTION", "RAW"): "STOCK_CORRECTION",
            ("CORRECTION", "OFFCUT"): "STOCK_CORRECTION",
            ("CORRECTION", "SCRAP"): "STOCK_CORRECTION",
        }

        source_type_map = {
            "OPENING": "OPENING",
            "NEW_PURCHASE": "NEW_PURCHASE",
            "RETURN": "RETURN_FAB",
            "CORRECTION": "CORRECTION",
        }

        stock_object = _build_stock_object(
            object_type=object_type,
            item=item,
            qty=qty,
            weight=weight,
            source_type=source_type_map[entry_type],
            remarks=remarks,
            qr_code=qr_code,
            photo_url=photo_url,
        )
        stock_object.rack_number = form.cleaned_data.get("rack_number") or ""
        stock_object.shelf_number = form.cleaned_data.get("shelf_number") or ""
        stock_object.bin_number = form.cleaned_data.get("bin_number") or ""
        stock_object.save(update_fields=["rack_number", "shelf_number", "bin_number"])

        txn = StockTxn.objects.create(
            txn_type=txn_type_map[(entry_type, object_type)],
            reference_no="",
            entry_source_type=entry_type,
            project_reference=form.cleaned_data.get("project_reference") or "",
            project_name=form.cleaned_data.get("project_name") or "",
            remarks=remarks,
            created_by=request.user,
            bridge_status="NOT_APPLICABLE",
        )
        StockTxnLine.objects.create(
            txn=txn,
            item=item,
            stock_object=stock_object,
            qty=qty,
            weight=weight,
            to_location=location,
        )
        try:
            post_stock_txn(txn.id)
            messages.success(request, "Item entry recorded in store successfully.")
            return redirect("ledger:inventory_dashboard")
        except ValidationError as exc:
            txn.delete()
            stock_object.delete()
            form.add_error(None, exc.message)

    return _render_inventory_form(
        request,
        page_title="Item Entry In Store",
        page_intro="Select an already-created store location. Use this for item entry against a project, item entry of spare store, opening stock, new purchase inward, return entry, and correction entry.",
        form=form,
        submit_label="Record Item Entry",
        post_url="ledger:create_inventory_inward",
    )


@login_required
def create_temporary_issue(request):
    if request.method == "GET":
        if not _has_inventory_access(request.user):
            messages.error(request, "You do not have permission to access inventory management.")
            return redirect("dashboard_home")
        return _render_inventory_form(
            request,
            page_title="Item Exit From Store",
            page_intro="Use this screen when a recorded store item is being utilized for fabrication before the full ERP issue flow is completed.",
            form=TemporaryIssueForm(),
            submit_label="Record Item Exit",
            post_url="ledger:create_temporary_issue",
        )
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can create temporary issues.")
        return redirect("ledger:inventory_dashboard")

    form = TemporaryIssueForm(request.POST)
    if form.is_valid():
        item = form.cleaned_data["item"]
        source_location = form.cleaned_data["source_location"]
        destination_location = form.cleaned_data["destination_location"]
        stock_object = form.cleaned_data.get("stock_object")

        txn = StockTxn.objects.create(
            txn_type="TEMP_ISSUE",
            reference_no=form.cleaned_data.get("reference_no") or "",
            entry_source_type="TEMPORARY",
            project_reference=form.cleaned_data["project_reference"],
            project_name=form.cleaned_data.get("project_name") or "",
            remarks=form.cleaned_data.get("remarks") or "",
            bridge_status="PENDING_ERP_INTEGRATION",
            created_by=request.user,
        )
        StockTxnLine.objects.create(
            txn=txn,
            item=item,
            stock_object=stock_object,
            qty=form.cleaned_data["qty"],
            weight=form.cleaned_data["weight"],
            from_location=source_location,
            to_location=destination_location,
        )
        try:
            post_stock_txn(txn.id)
            messages.success(request, "Item exit from store recorded and tagged for future ERP integration.")
            return redirect("ledger:inventory_dashboard")
        except ValidationError as exc:
            txn.delete()
            form.add_error(None, exc.message)

    return _render_inventory_form(
        request,
        page_title="Item Exit From Store",
        page_intro="Use this screen when a recorded store item is being utilized for fabrication before the full ERP issue flow is completed.",
        form=form,
        submit_label="Record Item Exit",
        post_url="ledger:create_temporary_issue",
    )


@login_required
def create_temporary_return(request):
    if request.method == "GET":
        if not _has_inventory_access(request.user):
            messages.error(request, "You do not have permission to access inventory management.")
            return redirect("dashboard_home")
        return _render_inventory_form(
            request,
            page_title="Item Return To Store",
            page_intro="Use this screen when unused material comes back to store. If the returned material is an off-cut, assign a QR code here.",
            form=TemporaryReturnForm(),
            submit_label="Record Item Return",
            post_url="ledger:create_temporary_return",
        )
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can create temporary returns.")
        return redirect("ledger:inventory_dashboard")

    form = TemporaryReturnForm(request.POST, request.FILES)
    if form.is_valid():
        issue_txn = form.cleaned_data["issue_txn"]
        issue_line = issue_txn.lines.first()
        return_type = form.cleaned_data["return_type"]
        qty = form.cleaned_data["qty"]
        weight = form.cleaned_data["weight"]
        remarks = form.cleaned_data.get("remarks") or ""
        photo_url = _upload_inventory_photo_if_present(
            form,
            stock_for=issue_txn.project_reference or "TEMP_RETURN",
            object_type=return_type,
        )

        stock_object = _build_stock_object(
            object_type=return_type,
            item=issue_line.item,
            qty=qty,
            weight=weight,
            source_type="TEMP_RETURN",
            remarks=remarks,
            qr_code=form.cleaned_data.get("qr_code") or "",
            photo_url=photo_url,
        )
        stock_object.rack_number = form.cleaned_data.get("rack_number") or ""
        stock_object.shelf_number = form.cleaned_data.get("shelf_number") or ""
        stock_object.bin_number = form.cleaned_data.get("bin_number") or ""
        stock_object.save(update_fields=["rack_number", "shelf_number", "bin_number"])

        txn = StockTxn.objects.create(
            txn_type="TEMP_RETURN",
            entry_source_type="TEMPORARY",
            project_reference=issue_txn.project_reference,
            project_name=issue_txn.project_name,
            remarks=remarks,
            bridge_status="PENDING_ERP_INTEGRATION",
            parent_txn=issue_txn,
            created_by=request.user,
        )
        StockTxnLine.objects.create(
            txn=txn,
            item=issue_line.item,
            stock_object=stock_object,
            qty=qty,
            weight=weight,
            from_location=issue_line.to_location,
            to_location=form.cleaned_data["destination_location"],
        )
        try:
            post_stock_txn(txn.id)
            _refresh_temporary_issue_status(issue_txn)
            messages.success(request, "Item return to store recorded and linked to the original issue.")
            return redirect("ledger:inventory_dashboard")
        except ValidationError as exc:
            txn.delete()
            stock_object.delete()
            form.add_error(None, exc.message)

    return _render_inventory_form(
        request,
        page_title="Item Return To Store",
        page_intro="Use this screen when unused material comes back to store. If the returned material is an off-cut, assign a QR code here.",
        form=form,
        submit_label="Record Item Return",
        post_url="ledger:create_temporary_return",
    )


def api_stock_by_item(request):
    rows = (
        StockLedgerEntry.objects.values("item__id", "item__item_description")
        .annotate(qty=Sum("qty"), weight=Sum("weight"))
        .order_by("item__item_description")
    )

    data = []
    for row in rows:
        data.append(
            {
                "item_id": row["item__id"],
                "item": row["item__item_description"],
                "qty": float(row["qty"] or 0),
                "weight": float(row["weight"] or 0),
            }
        )

    return JsonResponse(data, safe=False)


def api_stock_by_location(request):
    rows = (
        StockLedgerEntry.objects.values("location__id", "location__name")
        .annotate(qty=Sum("qty"), weight=Sum("weight"))
        .order_by("location__name")
    )

    data = []
    for row in rows:
        data.append(
            {
                "location_id": row["location__id"],
                "location": row["location__name"],
                "qty": float(row["qty"] or 0),
                "weight": float(row["weight"] or 0),
            }
        )

    return JsonResponse(data, safe=False)


def api_stock_by_mark(request):
    rows = (
        StockLedgerEntry.objects.values("stock_object__mark_no")
        .annotate(qty=Sum("qty"), weight=Sum("weight"))
        .order_by("stock_object__mark_no")
    )

    data = []
    for row in rows:
        mark = row["stock_object__mark_no"]
        if not mark:
            continue
        data.append(
            {
                "mark_no": mark,
                "qty": float(row["qty"] or 0),
                "weight": float(row["weight"] or 0),
            }
        )

    return JsonResponse(data, safe=False)


def api_stock_by_qr(request):
    rows = (
        StockLedgerEntry.objects.filter(stock_object__object_type="OFFCUT")
        .values("stock_object__qr_code", "item__item_description", "location__name")
        .annotate(qty=Sum("qty"), weight=Sum("weight"))
        .order_by("stock_object__qr_code")
    )

    data = []
    for row in rows:
        data.append(
            {
                "qr_code": row["stock_object__qr_code"],
                "item": row["item__item_description"],
                "location": row["location__name"],
                "qty": float(row["qty"] or 0),
                "weight": float(row["weight"] or 0),
            }
        )

    return JsonResponse(data, safe=False)


@csrf_exempt
def api_offcut_capture(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body)
        qr_code = data.get("qr_code")
        item_id = data.get("item_id")
        qty = Decimal(str(data.get("qty") or "0"))
        weight = Decimal(str(data.get("weight") or "0"))
        photo_url = data.get("photo_url")

        if not qr_code:
            return JsonResponse({"error": "QR code required"}, status=400)
        if not qr_code.isdigit() or len(qr_code) != 16:
            return JsonResponse({"error": "QR must be exactly 16 digits"}, status=400)
        if StockObject.objects.filter(qr_code=qr_code).exists():
            return JsonResponse({"error": "QR already exists"}, status=400)

        item = Item.objects.get(id=item_id)
        store = StockLocation.objects.filter(location_type="STORE", is_active=True).order_by("name").first()
        if not store:
            return JsonResponse({"error": "Create a store location first."}, status=400)

        stock_object = _build_stock_object(
            object_type="OFFCUT",
            item=item,
            qty=qty,
            weight=weight,
            source_type="OPENING",
            qr_code=qr_code,
            photo_url=photo_url or "",
        )
        txn = StockTxn.objects.create(
            txn_type="IN_OFFCUT",
            entry_source_type="OPENING",
            bridge_status="NOT_APPLICABLE",
        )
        StockTxnLine.objects.create(
            txn=txn,
            item=item,
            stock_object=stock_object,
            qty=qty,
            weight=weight,
            to_location=store,
        )
        post_stock_txn(txn.id)

        return JsonResponse({"status": "success", "offcut_id": stock_object.id, "qr_code": qr_code})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


def api_offcut_detail(request, qr_code):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)
    if (not qr_code.isdigit()) or len(qr_code) != 16:
        return JsonResponse({"error": "QR must be exactly 16 digits"}, status=400)

    obj = get_object_or_404(StockObject, object_type="OFFCUT", qr_code=qr_code)
    last = (
        StockLedgerEntry.objects.filter(stock_object=obj)
        .order_by("-created_at")
        .values("location__id", "location__name")
        .first()
    )

    return JsonResponse(
        {
            "id": obj.id,
            "qr_code": obj.qr_code,
            "object_type": obj.object_type,
            "item_id": obj.item_id,
            "item": obj.item.item_description,
            "qty": float(obj.qty),
            "weight": float(obj.weight),
            "photo_url": obj.photo_url,
            "created_at": obj.created_at.isoformat(),
            "current_location": last["location__name"] if last else None,
            "current_location_id": last["location__id"] if last else None,
        }
    )
