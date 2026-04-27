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
    rack_number = models.CharField(max_length=50, blank=True)
    shelf_number = models.CharField(max_length=50, blank=True)
    bin_number = models.CharField(max_length=50, blank=True)
    remarks = models.CharField(max_length=255, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.location_type})"


from django.core.validators import RegexValidator


class StockObject(models.Model):
    OBJECT_TYPES = [
        ("RAW", "Raw Material"),
        ("OFFCUT", "Offcut"),
        ("SCRAP", "Scrap"),
        ("FINISHED_MARK", "Finished Mark"),
    ]

    SOURCE_TYPES = [
        ("OPENING", "Opening Stock"),
        ("NEW_PURCHASE", "New Purchase Inward"),
        ("RETURN_FAB", "Return from Fabrication"),
        ("RETURN_PAINT", "Return from Painting"),
        ("CORRECTION", "Correction Entry"),
        ("TEMP_RETURN", "Temporary Return"),
    ]

    object_type = models.CharField(max_length=20, choices=OBJECT_TYPES)
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES, default="OPENING")

    item = models.ForeignKey(Item, on_delete=models.PROTECT)

    qty = models.DecimalField(max_digits=12, decimal_places=3)
    weight = models.DecimalField(max_digits=12, decimal_places=3)
    rate_per_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Pre-printed QR codes can vary in length across suppliers; keep only digit validation.
    qr_code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\d+$',
                message="QR code must contain digits only."
            )
        ]
    )

    mark_no = models.CharField(max_length=100, blank=True)

    photo_url = models.URLField(blank=True)
    heat_number = models.CharField(max_length=100, blank=True)
    plate_number = models.CharField(max_length=100, blank=True)
    test_certificate_no = models.CharField(max_length=100, blank=True)
    test_certificate_url = models.URLField(max_length=500, blank=True)
    test_certificate_file_unavailable = models.BooleanField(default=False)

    # GPS capture for OFFCUT yard tracking
    capture_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    capture_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rack_number = models.CharField(max_length=50, blank=True)
    shelf_number = models.CharField(max_length=50, blank=True)
    bin_number = models.CharField(max_length=50, blank=True)
    remarks = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    qr_required = models.BooleanField(default=False)

    def save(self, *args, **kwargs):

        """
        Automatically enforce QR policy.
        """

        if self.object_type == "RAW":
            self.qr_required = False

        elif self.object_type == "OFFCUT":
            self.qr_required = True

        elif self.object_type == "FINISHED_MARK":
            self.qr_required = True

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.object_type} - {self.item}"


class StockTxn(models.Model):
    TXN_TYPES = [
        ("OPENING_RAW", "Opening Raw Material Inward"),
        ("OPENING_OFFCUT", "Opening Offcut Inward"),
        ("OPENING_SCRAP", "Opening Scrap Inward"),
        ("GRN_RAW", "Raw Material Inward"),
        ("IN_OFFCUT", "Offcut Inward"),
        ("IN_SCRAP", "Scrap Inward"),
        ("ISSUE_FAB", "Issue to Fabrication"),
        ("RETURN_FAB", "Return from Fabrication"),
        ("ISSUE_PAINT", "Issue to Painting"),
        ("RETURN_PAINT", "Return from Painting"),
        ("TEMP_ISSUE", "Temporary Issue Pending ERP Integration"),
        ("TEMP_RETURN", "Temporary Return Pending ERP Integration"),
        ("STOCK_CORRECTION", "Stock Correction"),
        ("DISPATCH", "Dispatch"),
    ]

    ENTRY_SOURCE_TYPES = [
        ("OPENING", "Opening Stock"),
        ("NEW_PURCHASE", "New Purchase Inward"),
        ("RETURN", "Return"),
        ("CORRECTION", "Correction"),
        ("TEMPORARY", "Temporary Bridge"),
    ]

    BRIDGE_STATUS_CHOICES = [
        ("NOT_APPLICABLE", "Not Applicable"),
        ("OPEN", "Open"),
        ("PARTIALLY_RETURNED", "Partially Returned"),
        ("RETURNED", "Returned"),
        ("CONSUMED", "Consumed"),
        ("PENDING_ERP_INTEGRATION", "Pending ERP Integration"),
        ("INTEGRATED", "Integrated"),
    ]

    txn_type = models.CharField(max_length=30, choices=TXN_TYPES)

    reference_no = models.CharField(max_length=100, blank=True)
    entry_source_type = models.CharField(max_length=30, choices=ENTRY_SOURCE_TYPES, default="OPENING")
    project_reference = models.CharField(max_length=100, blank=True)
    project_name = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)
    bridge_status = models.CharField(
        max_length=30,
        choices=BRIDGE_STATUS_CHOICES,
        default="NOT_APPLICABLE",
    )
    parent_txn = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_transactions",
    )
    integrated_at = models.DateTimeField(null=True, blank=True)

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

    @property
    def is_temporary_issue(self):
        return self.txn_type == "TEMP_ISSUE"

    @property
    def is_temporary_return(self):
        return self.txn_type == "TEMP_RETURN"


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
