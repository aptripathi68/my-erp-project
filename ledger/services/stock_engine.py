from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum

from ledger.models import (
    StockTxn,
    StockTxnLine,
    StockLedgerEntry,
)


def get_available_stock(item_id, location_id, stock_object_id=None):
    """
    Calculate current available stock from ledger
    """

    qs = StockLedgerEntry.objects.filter(
        item_id=item_id,
        location_id=location_id
    )

    if stock_object_id:
        qs = qs.filter(stock_object_id=stock_object_id)

    agg = qs.aggregate(
        qty=Sum("qty"),
        weight=Sum("weight")
    )

    qty = agg["qty"] or 0
    weight = agg["weight"] or 0

    return qty, weight


def validate_stock_availability(line):
    """
    Prevent negative inventory
    """

    if not line.from_location:
        return

    qty_available, weight_available = get_available_stock(
        item_id=line.item_id,
        location_id=line.from_location_id,
        stock_object_id=line.stock_object_id
    )

    if line.qty > qty_available:
        raise ValidationError(
            f"Insufficient stock for item {line.item_id} at location {line.from_location.name}. "
            f"Available={qty_available}, Requested={line.qty}"
        )

    if line.weight > weight_available:
        raise ValidationError(
            f"Insufficient weight for item {line.item_id} at location {line.from_location.name}. "
            f"Available={weight_available}, Requested={line.weight}"
        )


def validate_qr_policy(line):
    """
    Enforce QR policy
    """

    obj = line.stock_object

    if obj and obj.qr_required and not obj.qr_code:
        raise ValidationError(
            f"QR code required for object {obj.id}"
        )


def validate_offcut_scan(line, txn):
    """
    Ensure offcut QR scanned before fabrication issue
    """

    if txn.txn_type == "ISSUE_FAB":

        obj = line.stock_object

        if obj and obj.object_type == "OFFCUT":

            if not obj.qr_code:
                raise ValidationError(
                    "Offcut QR must be scanned before issue to fabrication"
                )


def post_stock_txn(txn_id):
    """
    Industrial-grade posting engine
    """

    txn = StockTxn.objects.get(id=txn_id)

    if txn.posted:
        raise ValidationError("Transaction already posted")

    lines = txn.lines.all()

    if not lines:
        raise ValidationError("Transaction has no lines")

    with transaction.atomic():

        for line in lines:

            validate_qr_policy(line)

            validate_offcut_scan(line, txn)

            validate_stock_availability(line)

            # FROM location entry
            if line.from_location:

                StockLedgerEntry.objects.create(
                    txn=txn,
                    item=line.item,
                    location=line.from_location,
                    stock_object=line.stock_object,
                    qty=-line.qty,
                    weight=-line.weight,
                )

            # TO location entry
            if line.to_location:

                StockLedgerEntry.objects.create(
                    txn=txn,
                    item=line.item,
                    location=line.to_location,
                    stock_object=line.stock_object,
                    qty=line.qty,
                    weight=line.weight,
                )

        txn.posted = True
        txn.save()

    return True