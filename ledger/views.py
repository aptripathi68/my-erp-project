from django.http import JsonResponse
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
import json

from .models import StockLedgerEntry, StockObject, StockLocation, StockTxn, StockTxnLine
from masters.models import Item


# ------------------------------
# STOCK BY ITEM
# ------------------------------

def api_stock_by_item(request):

    rows = (
        StockLedgerEntry.objects
        .values("item__id", "item__name")
        .annotate(
            qty=Sum("qty"),
            weight=Sum("weight")
        )
        .order_by("item__name")
    )

    data = []

    for r in rows:
        data.append({
            "item_id": r["item__id"],
            "item": r["item__name"],
            "qty": float(r["qty"] or 0),
            "weight": float(r["weight"] or 0),
        })

    return JsonResponse(data, safe=False)


# ------------------------------
# STOCK BY LOCATION
# ------------------------------

def api_stock_by_location(request):

    rows = (
        StockLedgerEntry.objects
        .values("location__id", "location__name")
        .annotate(
            qty=Sum("qty"),
            weight=Sum("weight")
        )
        .order_by("location__name")
    )

    data = []

    for r in rows:
        data.append({
            "location_id": r["location__id"],
            "location": r["location__name"],
            "qty": float(r["qty"] or 0),
            "weight": float(r["weight"] or 0),
        })

    return JsonResponse(data, safe=False)


# ------------------------------
# STOCK BY MARK NUMBER
# ------------------------------

def api_stock_by_mark(request):

    rows = (
        StockLedgerEntry.objects
        .values("stock_object__mark_no")
        .annotate(
            qty=Sum("qty"),
            weight=Sum("weight")
        )
        .order_by("stock_object__mark_no")
    )

    data = []

    for r in rows:

        mark = r["stock_object__mark_no"]

        if not mark:
            continue

        data.append({
            "mark_no": mark,
            "qty": float(r["qty"] or 0),
            "weight": float(r["weight"] or 0),
        })

    return JsonResponse(data, safe=False)


# ------------------------------
# STOCK BY OFFCUT QR
# ------------------------------

def api_stock_by_qr(request):

    rows = (
        StockLedgerEntry.objects
        .filter(stock_object__object_type="OFFCUT")
        .values(
            "stock_object__qr_code",
            "item__name",
            "location__name"
        )
        .annotate(
            qty=Sum("qty"),
            weight=Sum("weight")
        )
    )

    data = []

    for r in rows:

        data.append({
            "qr_code": r["stock_object__qr_code"],
            "item": r["item__name"],
            "location": r["location__name"],
            "qty": float(r["qty"] or 0),
            "weight": float(r["weight"] or 0),
        })

    return JsonResponse(data, safe=False)


# ------------------------------
# OFFCUT CAPTURE API
# ------------------------------

@csrf_exempt
def api_offcut_capture(request):

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:

        data = json.loads(request.body)

        qr_code = data.get("qr_code")
        item_id = data.get("item_id")
        qty = data.get("qty")
        weight = data.get("weight")
        photo_url = data.get("photo_url")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        # QR required
        if not qr_code:
            return JsonResponse({"error": "QR code required"}, status=400)

        # QR must be exactly 16 digits
        if not qr_code.isdigit() or len(qr_code) != 16:
            return JsonResponse({"error": "QR must be exactly 16 digits"}, status=400)

        # Prevent duplicate QR
        if StockObject.objects.filter(qr_code=qr_code).exists():
            return JsonResponse({"error": "QR already exists"}, status=400)

        item = Item.objects.get(id=item_id)
        store = StockLocation.objects.get(name="Store")

        # create offcut object
        obj = StockObject.objects.create(
            object_type="OFFCUT",
            item=item,
            qty=qty,
            weight=weight,
            qr_code=qr_code,
            photo_url=photo_url,
            capture_latitude=latitude,
            capture_longitude=longitude,
        )

        # create stock transaction
        txn = StockTxn.objects.create(txn_type="IN_OFFCUT")

        StockTxnLine.objects.create(
            txn=txn,
            item=item,
            stock_object=obj,
            qty=qty,
            weight=weight,
            to_location=store,
        )

        return JsonResponse({
            "status": "success",
            "offcut_id": obj.id,
            "qr_code": qr_code
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
# ------------------------------
# OFFCUT LOOKUP BY QR
# ------------------------------

def api_offcut_lookup(request, qr_code):

    try:

        obj = StockObject.objects.get(qr_code=qr_code)

        # find current location from ledger
        last_entry = (
            StockLedgerEntry.objects
            .filter(stock_object=obj)
            .order_by("-created_at")
            .first()
        )

        location = None
        if last_entry:
            location = last_entry.location.name

        data = {
            "qr_code": obj.qr_code,
            "item": obj.item.item_description,
            "qty": float(obj.qty),
            "weight": float(obj.weight),
            "location": location,
            "photo_url": obj.photo_url,
            "latitude": obj.capture_latitude,
            "longitude": obj.capture_longitude,
            "created_at": obj.created_at,
        }

        return JsonResponse(data)

    except StockObject.DoesNotExist:

# Off-cut lookup API

from django.shortcuts import get_object_or_404

def api_offcut_detail(request, qr_code):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    if (not qr_code.isdigit()) or len(qr_code) != 16:
        return JsonResponse({"error": "QR must be exactly 16 digits"}, status=400)

    obj = get_object_or_404(
        StockObject,
        object_type="OFFCUT",
        qr_code=qr_code
    )

    # current location from ledger (latest entry)
    last = (
        StockLedgerEntry.objects
        .filter(stock_object=obj)
        .order_by("-created_at")
        .values("location__id", "location__name")
        .first()
    )

    return JsonResponse({
        "id": obj.id,
        "qr_code": obj.qr_code,
        "object_type": obj.object_type,
        "item_id": obj.item_id,
        "item": obj.item.item_description,   # adjust if you want other field
        "qty": float(obj.qty),
        "weight": float(obj.weight),
        "photo_url": obj.photo_url,
        "capture_latitude": float(obj.capture_latitude) if obj.capture_latitude is not None else None,
        "capture_longitude": float(obj.capture_longitude) if obj.capture_longitude is not None else None,
        "created_at": obj.created_at.isoformat(),
        "current_location": last["location__name"] if last else None,
        "current_location_id": last["location__id"] if last else None,
    })