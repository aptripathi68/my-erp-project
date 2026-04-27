# ledger/services/stock_queries.py
from decimal import Decimal

from django.db.models import Sum, F, Value, DecimalField, Q, ExpressionWrapper
from django.db.models.functions import Coalesce

from ledger.models import StockLedgerEntry


DEC0 = Value(Decimal("0.000"), output_field=DecimalField(max_digits=18, decimal_places=3))
MONEY0 = Value(Decimal("0.00"), output_field=DecimalField(max_digits=18, decimal_places=2))


def _base_qs():
    # Select related to avoid N+1 when we expose item/location info
    return StockLedgerEntry.objects.select_related("item", "location", "stock_object")


def stock_by_item(location_id=None, object_type=None):
    """
    Stock summarized by Item (optionally filtered by location and object_type)
    Returns qty_sum, weight_sum, derived_weight_sum (qty * item.unit_weight)
    """
    qs = _base_qs()
    if location_id:
        qs = qs.filter(location_id=location_id)
    if object_type:
        qs = qs.filter(stock_object__object_type=object_type)

    rows = (
        qs.values(
            "item_id",
            "item__item_master_id",
            "item__item_description",
            "item__unit_weight",
        )
        .annotate(
            qty_sum=Coalesce(Sum("qty"), DEC0),
            weight_sum=Coalesce(Sum("weight"), DEC0),
            derived_weight_sum=Coalesce(
                Sum(F("qty") * F("item__unit_weight")),
                DEC0,
            ),
            value_sum=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("weight") * F("stock_object__rate_per_kg"),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    )
                ),
                MONEY0,
            ),
        )
        .order_by("item__item_description")
    )

    # Convert to plain dict list + weight_tons (assuming kg -> tons)
    out = []
    for r in rows:
        weight_kg = r["derived_weight_sum"] or Decimal("0")
        out.append(
            {
                "item_id": r["item_id"],
                "item_master_id": r["item__item_master_id"],
                "item_description": r["item__item_description"],
                "unit_weight": str(r["item__unit_weight"]),
                "qty": str(r["qty_sum"]),
                "weight": str(r["weight_sum"]),
                "stock_value": str((r["value_sum"] or Decimal("0.00")).quantize(Decimal("0.01"))),
                "derived_weight": str(r["derived_weight_sum"]),
                "derived_weight_tons": str((weight_kg / Decimal("1000")).quantize(Decimal("0.001"))),
            }
        )
    return out


def stock_by_location(item_id=None, object_type=None):
    """
    Stock summarized by Location (optionally filtered by item and object_type)
    """
    qs = _base_qs()
    if item_id:
        qs = qs.filter(item_id=item_id)
    if object_type:
        qs = qs.filter(stock_object__object_type=object_type)

    rows = (
        qs.values(
            "location_id",
            "location__name",
            "location__location_type",
        )
        .annotate(
            qty_sum=Coalesce(Sum("qty"), DEC0),
            weight_sum=Coalesce(Sum("weight"), DEC0),
            value_sum=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("weight") * F("stock_object__rate_per_kg"),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    )
                ),
                MONEY0,
            ),
        )
        .order_by("location__name")
    )

    out = []
    for r in rows:
        out.append(
            {
                "location_id": r["location_id"],
                "location_name": r["location__name"],
                "location_type": r["location__location_type"],
                "qty": str(r["qty_sum"]),
                "weight": str(r["weight_sum"]),
                "stock_value": str((r["value_sum"] or Decimal("0.00")).quantize(Decimal("0.01"))),
                "weight_tons": str((Decimal(r["weight_sum"]) / Decimal("1000")).quantize(Decimal("0.001"))),
            }
        )
    return out


def stock_by_store_item(location_id=None):
    """
    Stock summarized store-wise, rack-wise, shelf-wise, bin-wise, and item-wise
    for working register / export.
    Only active store locations are included.
    """
    qs = _base_qs().filter(location__location_type="STORE", location__is_active=True)
    if location_id:
        qs = qs.filter(location_id=location_id)

    rows = (
        qs.values(
            "location_id",
            "location__name",
            "stock_object__rack_number",
            "stock_object__shelf_number",
            "stock_object__bin_number",
            "stock_object__heat_number",
            "stock_object__plate_number",
            "stock_object__test_certificate_no",
            "stock_object__test_certificate_url",
            "stock_object__test_certificate_file_unavailable",
            "item_id",
            "item__item_master_id",
            "item__item_description",
            "stock_object__object_type",
        )
        .annotate(
            qty_sum=Coalesce(Sum("qty"), DEC0),
            weight_sum=Coalesce(Sum("weight"), DEC0),
            value_sum=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("weight") * F("stock_object__rate_per_kg"),
                        output_field=DecimalField(max_digits=18, decimal_places=2),
                    )
                ),
                MONEY0,
            ),
        )
        .order_by(
            "location__name",
            "stock_object__rack_number",
            "stock_object__shelf_number",
            "stock_object__bin_number",
            "item__item_description",
            "stock_object__object_type",
        )
    )

    out = []
    for r in rows:
        qty_sum = r["qty_sum"] or Decimal("0")
        weight_sum = r["weight_sum"] or Decimal("0")
        if qty_sum == 0 and weight_sum == 0:
            continue
        out.append(
            {
                "location_id": r["location_id"],
                "location_name": r["location__name"],
                "rack_number": r["stock_object__rack_number"] or "-",
                "shelf_number": r["stock_object__shelf_number"] or "-",
                "bin_number": r["stock_object__bin_number"] or "-",
                "heat_number": r["stock_object__heat_number"] or "-",
                "plate_number": r["stock_object__plate_number"] or "-",
                "test_certificate_no": r["stock_object__test_certificate_no"] or "-",
                "test_certificate_url": r["stock_object__test_certificate_url"] or "",
                "test_certificate_file_unavailable": r["stock_object__test_certificate_file_unavailable"],
                "item_id": r["item_id"],
                "item_master_id": r["item__item_master_id"],
                "item_description": r["item__item_description"],
                "object_type": r["stock_object__object_type"] or "-",
                "qty": str(qty_sum),
                "weight": str(weight_sum),
                "rate_per_kg": str((r["value_sum"] / weight_sum).quantize(Decimal("0.01")) if weight_sum else Decimal("0.00")),
                "stock_value": str((r["value_sum"] or Decimal("0.00")).quantize(Decimal("0.01"))),
            }
        )
    return out


def editable_store_stock_objects(location_id=None, entry_date=None, search_text=None):
    """
    Current positive stock objects available in active stores.
    Used for editing non-stock operational fields like rack/shelf/bin/remarks.
    """
    qs = _base_qs().filter(
        location__location_type="STORE",
        location__is_active=True,
        stock_object_id__isnull=False,
    )
    if location_id:
        qs = qs.filter(location_id=location_id)
    if entry_date:
        qs = qs.filter(stock_object__created_at__date=entry_date)
    if search_text:
        qs = qs.filter(
            Q(stock_object__qr_code__icontains=search_text)
            | Q(item__item_description__icontains=search_text)
            | Q(location__name__icontains=search_text)
        )

    rows = (
        qs.values(
            "stock_object_id",
            "stock_object__qr_code",
            "stock_object__object_type",
            "stock_object__rack_number",
            "stock_object__shelf_number",
            "stock_object__bin_number",
            "stock_object__remarks",
            "stock_object__rate_per_kg",
            "stock_object__heat_number",
            "stock_object__plate_number",
            "stock_object__test_certificate_no",
            "stock_object__test_certificate_url",
            "stock_object__test_certificate_file_unavailable",
            "location_id",
            "location__name",
            "item__item_description",
            "stock_object__created_at",
        )
        .annotate(
            qty_sum=Coalesce(Sum("qty"), DEC0),
            weight_sum=Coalesce(Sum("weight"), DEC0),
        )
        .order_by("-stock_object__created_at", "location__name", "item__item_description", "stock_object__qr_code", "stock_object_id")
    )

    out = []
    for r in rows:
        qty_sum = r["qty_sum"] or Decimal("0")
        weight_sum = r["weight_sum"] or Decimal("0")
        if qty_sum <= 0 and weight_sum <= 0:
            continue
        out.append(
            {
                "stock_object_id": r["stock_object_id"],
                "qr_code": r["stock_object__qr_code"] or "-",
                "object_type": r["stock_object__object_type"] or "-",
                "rack_number": r["stock_object__rack_number"] or "-",
                "shelf_number": r["stock_object__shelf_number"] or "-",
                "bin_number": r["stock_object__bin_number"] or "-",
                "remarks": r["stock_object__remarks"] or "-",
                "rate_per_kg": str((r["stock_object__rate_per_kg"] or Decimal("0.00")).quantize(Decimal("0.01"))),
                "stock_value": str((weight_sum * (r["stock_object__rate_per_kg"] or Decimal("0.00"))).quantize(Decimal("0.01"))),
                "heat_number": r["stock_object__heat_number"] or "-",
                "plate_number": r["stock_object__plate_number"] or "-",
                "test_certificate_no": r["stock_object__test_certificate_no"] or "-",
                "test_certificate_url": r["stock_object__test_certificate_url"] or "",
                "test_certificate_file_unavailable": r["stock_object__test_certificate_file_unavailable"],
                "location_id": r["location_id"],
                "location_name": r["location__name"],
                "item_description": r["item__item_description"],
                "entry_date": r["stock_object__created_at"],
                "qty": str(qty_sum),
                "weight": str(weight_sum),
            }
        )
    return out


def stock_by_mark(mark_no, location_id=None):
    """
    Stock for FINISHED_MARK by mark_no (optionally location)
    """
    qs = _base_qs().filter(stock_object__object_type="FINISHED_MARK", stock_object__mark_no=mark_no)
    if location_id:
        qs = qs.filter(location_id=location_id)

    rows = (
        qs.values(
            "stock_object_id",
            "stock_object__mark_no",
            "location_id",
            "location__name",
            "item_id",
            "item__item_description",
        )
        .annotate(
            qty_sum=Coalesce(Sum("qty"), DEC0),
            weight_sum=Coalesce(Sum("weight"), DEC0),
        )
        .order_by("location__name", "item__item_description")
    )
    return [
        {
            "stock_object_id": r["stock_object_id"],
            "mark_no": r["stock_object__mark_no"],
            "location_id": r["location_id"],
            "location_name": r["location__name"],
            "item_id": r["item_id"],
            "item_description": r["item__item_description"],
            "qty": str(r["qty_sum"]),
            "weight": str(r["weight_sum"]),
            "weight_tons": str((Decimal(r["weight_sum"]) / Decimal("1000")).quantize(Decimal("0.001"))),
        }
        for r in rows
    ]


def stock_by_qr(qr_code, location_id=None):
    """
    Stock for OFFCUT or FINISHED_MARK by qr_code (optionally location)
    """
    qs = _base_qs().filter(stock_object__qr_code=qr_code)
    if location_id:
        qs = qs.filter(location_id=location_id)

    rows = (
        qs.values(
            "stock_object_id",
            "stock_object__object_type",
            "stock_object__qr_code",
            "stock_object__mark_no",
            "location_id",
            "location__name",
            "item_id",
            "item__item_description",
        )
        .annotate(
            qty_sum=Coalesce(Sum("qty"), DEC0),
            weight_sum=Coalesce(Sum("weight"), DEC0),
        )
        .order_by("location__name")
    )
    return [
        {
            "stock_object_id": r["stock_object_id"],
            "object_type": r["stock_object__object_type"],
            "qr_code": r["stock_object__qr_code"],
            "mark_no": r["stock_object__mark_no"],
            "location_id": r["location_id"],
            "location_name": r["location__name"],
            "item_id": r["item_id"],
            "item_description": r["item__item_description"],
            "qty": str(r["qty_sum"]),
            "weight": str(r["weight_sum"]),
            "weight_tons": str((Decimal(r["weight_sum"]) / Decimal("1000")).quantize(Decimal("0.001"))),
        }
        for r in rows
    ]
