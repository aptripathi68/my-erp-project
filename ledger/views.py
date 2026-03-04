# ledger/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ledger.services.stock_queries import (
    stock_by_item,
    stock_by_location,
    stock_by_mark,
    stock_by_qr,
)


@require_GET
def api_stock_by_item(request):
    """
    GET /api/stock/by-item/?location=<id>&object_type=RAW|OFFCUT|FINISHED_MARK
    """
    location = request.GET.get("location")
    object_type = request.GET.get("object_type")
    data = stock_by_item(location_id=location, object_type=object_type)
    return JsonResponse(data, safe=False)


@require_GET
def api_stock_by_location(request):
    """
    GET /api/stock/by-location/?item=<id>&object_type=RAW|OFFCUT|FINISHED_MARK
    """
    item = request.GET.get("item")
    object_type = request.GET.get("object_type")
    data = stock_by_location(item_id=item, object_type=object_type)
    return JsonResponse(data, safe=False)


@require_GET
def api_stock_by_mark(request):
    """
    GET /api/stock/by-mark/?mark_no=<MARK>&location=<id>
    """
    mark_no = request.GET.get("mark_no")
    if not mark_no:
        return JsonResponse({"error": "mark_no is required"}, status=400)

    location = request.GET.get("location")
    data = stock_by_mark(mark_no=mark_no, location_id=location)
    return JsonResponse(data, safe=False)


@require_GET
def api_stock_by_qr(request):
    """
    GET /api/stock/by-qr/?qr=<QR_CODE>&location=<id>
    """
    qr = request.GET.get("qr")
    if not qr:
        return JsonResponse({"error": "qr is required"}, status=400)

    location = request.GET.get("location")
    data = stock_by_qr(qr_code=qr, location_id=location)
    return JsonResponse(data, safe=False)