from django.db import transaction
from django.core.exceptions import ValidationError

from ledger.models import (
    StockTxn,
    StockTxnLine,
    StockLedgerEntry,
)


def validate_qr_policy(line):
    """
    Enforces QR scanning policy
    """

    obj = line.stock_object

    if obj and obj.qr_required and not obj.qr_code:
        raise ValidationError(
            f"QR code required for object {obj.id}"
        )


def validate_offcut_scan(line, txn):
    """
    Ensure offcut QR is scanned when issuing to fabrication
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
    Main ledger posting engine
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

            # FROM LOCATION ENTRY
            if line.from_location:

                StockLedgerEntry.objects.create(
                    txn=txn,
                    item=line.item,
                    location=line.from_location,
                    stock_object=line.stock_object,
                    qty=-line.qty,
                    weight=-line.weight,
                )

            # TO LOCATION ENTRY
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