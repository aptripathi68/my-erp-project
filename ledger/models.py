from django.db import models
from django.conf import settings
from masters.models import Item


class StockLocation(models.Model):
    LOCATION_TYPES = [
        ("STORE", "Store"),
        ("FABRICATION", "Fabrication Agency"),
        ("PAINTING", "Painting Agency"),
        ("DISPATCH_SECTION", "Dispatch Section"),
        ("TRUCK", "Truck"),
    ]

    name = models.CharField(max_length=200)
    location_type = models.CharField(max_length=30, choices=LOCATION_TYPES)

    # optional GPS (for yard/offcut tracing)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.location_type})"


class StockObject(models.Model):
    OBJECT_TYPES = [
        ("RAW", "Raw Material"),
        ("OFFCUT", "Offcut"),
        ("FINISHED_MARK", "Finished Mark"),
    ]

    object_type = models.CharField(max_length=20, choices=OBJECT_TYPES)

    item = models.ForeignKey(Item, on_delete=models.PROTECT)

    qty = models.DecimalField(max_digits=12, decimal_places=3)
    weight = models.DecimalField(max_digits=12, decimal_places=3)

    qr_code = models.CharField(max_length=50, unique=True, null=True, blank=True)

    mark_no = models.CharField(max_length=100, blank=True)

    photo_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.object_type} - {self.item}"


class StockTxn(models.Model):
    TXN_TYPES = [
        ("GRN_RAW", "Raw Material Inward"),
        ("IN_OFFCUT", "Offcut Inward"),
        ("ISSUE_FAB", "Issue to Fabrication"),
        ("RETURN_FAB", "Return from Fabrication"),
        ("ISSUE_PAINT", "Issue to Painting"),
        ("RETURN_PAINT", "Return from Painting"),
        ("DISPATCH", "Dispatch"),
    ]

    txn_type = models.CharField(max_length=30, choices=TXN_TYPES)

    reference_no = models.CharField(max_length=100, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    posted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.txn_type} - {self.id}"


class StockTxnLine(models.Model):
    txn = models.ForeignKey(StockTxn, on_delete=models.CASCADE, related_name="lines")

    item = models.ForeignKey(Item, on_delete=models.PROTECT)

    stock_object = models.ForeignKey(
        StockObject,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    qty = models.DecimalField(max_digits=12, decimal_places=3)
    weight = models.DecimalField(max_digits=12, decimal_places=3)

    from_location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        related_name="from_location",
        null=True,
        blank=True,
    )

    to_location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        related_name="to_location",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.item} {self.qty}"


class StockLedgerEntry(models.Model):
    txn = models.ForeignKey(StockTxn, on_delete=models.PROTECT)

    item = models.ForeignKey(Item, on_delete=models.PROTECT)

    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT)

    stock_object = models.ForeignKey(
        StockObject,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    qty = models.DecimalField(max_digits=12, decimal_places=3)
    weight = models.DecimalField(max_digits=12, decimal_places=3)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]