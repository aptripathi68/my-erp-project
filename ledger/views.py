from django.http import JsonResponse
from django.db.models import Sum
from .models import StockLedgerEntry


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