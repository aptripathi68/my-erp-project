import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from masters.models import Item

from .forms import InventoryInwardForm, StockLocationForm, TemporaryIssueForm, TemporaryReturnForm
from .models import StockLedgerEntry, StockLocation, StockObject, StockTxn, StockTxnLine
from .services.stock_engine import post_stock_txn
from .services.stock_queries import stock_by_item, stock_by_location


def _has_inventory_access(user):
    return user.is_authenticated and user.role in {"Admin", "Store", "Management", "Planning", "Procurement"}


def _can_manage_inventory(user):
    return user.is_authenticated and user.role in {"Admin", "Store", "Management"}


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


def _build_stock_object(*, object_type, item, qty, weight, source_type, remarks="", qr_code="", photo_url="", latitude=None, longitude=None):
    return StockObject.objects.create(
        object_type=object_type,
        source_type=source_type,
        item=item,
        qty=qty,
        weight=weight,
        qr_code=qr_code or None,
        photo_url=photo_url or "",
        capture_latitude=latitude,
        capture_longitude=longitude,
        remarks=remarks,
    )


def _inventory_context(request):
    issue_rows = []
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
        "location_form": StockLocationForm(),
        "inward_form": InventoryInwardForm(),
        "issue_form": TemporaryIssueForm(),
        "return_form": TemporaryReturnForm(),
        "locations": StockLocation.objects.order_by("location_type", "name"),
        "stock_by_item": stock_by_item(),
        "stock_by_location": stock_by_location(),
        "temporary_issue_rows": issue_rows,
        "pending_issue_count": sum(1 for row in issue_rows if row["txn"].bridge_status != "RETURNED"),
        "can_manage_inventory": _can_manage_inventory(request.user),
    }


@login_required
def inventory_dashboard(request):
    if not _has_inventory_access(request.user):
        messages.error(request, "You do not have permission to access inventory management.")
        return redirect("dashboard_home")
    return render(request, "ledger/inventory_dashboard.html", _inventory_context(request))


@login_required
def create_location(request):
    if request.method != "POST":
        return redirect("ledger:inventory_dashboard")
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can create stock locations.")
        return redirect("ledger:inventory_dashboard")
    form = StockLocationForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Stock location saved.")
        return redirect("ledger:inventory_dashboard")
    context = _inventory_context(request)
    context["location_form"] = form
    return render(request, "ledger/inventory_dashboard.html", context)


@login_required
def create_inventory_inward(request):
    if request.method != "POST":
        return redirect("ledger:inventory_dashboard")
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can record inward inventory.")
        return redirect("ledger:inventory_dashboard")

    form = InventoryInwardForm(request.POST)
    if form.is_valid():
        entry_type = form.cleaned_data["entry_type"]
        object_type = form.cleaned_data["object_type"]
        item = form.cleaned_data["item"]
        location = form.cleaned_data["location"]
        qty = form.cleaned_data["qty"]
        weight = form.cleaned_data["weight"]
        qr_code = form.cleaned_data.get("qr_code") or ""
        remarks = form.cleaned_data.get("remarks") or ""

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
            photo_url=form.cleaned_data.get("photo_url") or "",
            latitude=form.cleaned_data.get("capture_latitude"),
            longitude=form.cleaned_data.get("capture_longitude"),
        )

        txn = StockTxn.objects.create(
            txn_type=txn_type_map[(entry_type, object_type)],
            reference_no=form.cleaned_data.get("reference_no") or "",
            entry_source_type=entry_type,
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
            messages.success(request, "Inventory inward recorded and posted.")
            return redirect("ledger:inventory_dashboard")
        except ValidationError as exc:
            txn.delete()
            stock_object.delete()
            form.add_error(None, exc.message)

    context = _inventory_context(request)
    context["inward_form"] = form
    return render(request, "ledger/inventory_dashboard.html", context)


@login_required
def create_temporary_issue(request):
    if request.method != "POST":
        return redirect("ledger:inventory_dashboard")
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
            messages.success(request, "Temporary issue posted and tagged for future ERP integration.")
            return redirect("ledger:inventory_dashboard")
        except ValidationError as exc:
            txn.delete()
            form.add_error(None, exc.message)

    context = _inventory_context(request)
    context["issue_form"] = form
    return render(request, "ledger/inventory_dashboard.html", context)


@login_required
def create_temporary_return(request):
    if request.method != "POST":
        return redirect("ledger:inventory_dashboard")
    if not _can_manage_inventory(request.user):
        messages.error(request, "Only Store, Management, or Admin can create temporary returns.")
        return redirect("ledger:inventory_dashboard")

    form = TemporaryReturnForm(request.POST)
    if form.is_valid():
        issue_txn = form.cleaned_data["issue_txn"]
        issue_line = issue_txn.lines.first()
        return_type = form.cleaned_data["return_type"]
        qty = form.cleaned_data["qty"]
        weight = form.cleaned_data["weight"]
        remarks = form.cleaned_data.get("remarks") or ""

        stock_object = _build_stock_object(
            object_type=return_type,
            item=issue_line.item,
            qty=qty,
            weight=weight,
            source_type="TEMP_RETURN",
            remarks=remarks,
            qr_code=form.cleaned_data.get("qr_code") or "",
            photo_url=form.cleaned_data.get("photo_url") or "",
            latitude=form.cleaned_data.get("capture_latitude"),
            longitude=form.cleaned_data.get("capture_longitude"),
        )

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
            messages.success(request, "Temporary return posted and linked to the original issue.")
            return redirect("ledger:inventory_dashboard")
        except ValidationError as exc:
            txn.delete()
            stock_object.delete()
            form.add_error(None, exc.message)

    context = _inventory_context(request)
    context["return_form"] = form
    return render(request, "ledger/inventory_dashboard.html", context)


# ------------------------------
# STOCK BY ITEM
# ------------------------------
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
        latitude = data.get("latitude")
        longitude = data.get("longitude")

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
            latitude=latitude,
            longitude=longitude,
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
            "capture_latitude": float(obj.capture_latitude) if obj.capture_latitude is not None else None,
            "capture_longitude": float(obj.capture_longitude) if obj.capture_longitude is not None else None,
            "created_at": obj.created_at.isoformat(),
            "current_location": last["location__name"] if last else None,
            "current_location_id": last["location__id"] if last else None,
        }
    )
