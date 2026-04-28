from django.conf import settings
from django.db import models, transaction


class Drawing(models.Model):
    """
    One drawing master.
    Drawings are maintained independently from BOM processing.
    """

    project = models.ForeignKey(
        "procurement.BOMHeader",
        on_delete=models.PROTECT,
        related_name="drawings",
        null=True,
        blank=True,
        help_text="Temporary project link. Can later be replaced by a dedicated Project master.",
    )
    drawing_no = models.CharField(max_length=100)
    title = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_drawings",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["drawing_no"]
        unique_together = [("project", "drawing_no")]
        indexes = [
            models.Index(fields=["drawing_no"]),
        ]

    def __str__(self):
        if self.project_id:
            return f"{self.project_id} - {self.drawing_no}"
        return self.drawing_no


class DrawingSheet(models.Model):
    """
    Stable identity of one sheet under a drawing.
    Example:
    Drawing D-101
      Sheet 1
      Sheet 2
      Sheet 3
    """

    drawing = models.ForeignKey(
        Drawing,
        on_delete=models.CASCADE,
        related_name="sheets",
    )
    sheet_no = models.CharField(max_length=20)

    class Meta:
        ordering = ["drawing", "sheet_no"]
        unique_together = [("drawing", "sheet_no")]
        indexes = [
            models.Index(fields=["sheet_no"]),
        ]
        verbose_name = "Add Drawing Sheet"
        verbose_name_plural = "Add Drawing Sheets"

    def __str__(self):
        return f"{self.drawing.drawing_no} / Sheet {self.sheet_no}"


class DrawingSheetRevision(models.Model):
    """
    One uploaded file version for one sheet.
    End users should use only VERIFIED + CURRENT revisions.
    """

    STATUS_PENDING = "PENDING"
    STATUS_VERIFIED = "VERIFIED"
    STATUS_REJECTED = "REJECTED"

    VERIFICATION_STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_REJECTED, "Rejected"),
    ]

    drawing_sheet = models.ForeignKey(
        DrawingSheet,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_no = models.CharField(max_length=50)

    file_key = models.CharField(
        max_length=500,
        help_text="Cloudflare R2 object key",
    )
    original_filename = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="application/pdf")
    file_size = models.BigIntegerField(null=True, blank=True)

    is_current = models.BooleanField(default=False)

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_drawing_revisions",
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_drawing_revisions",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["drawing_sheet", "-uploaded_at"]
        unique_together = [("drawing_sheet", "revision_no")]
        indexes = [
            models.Index(fields=["is_current"]),
            models.Index(fields=["revision_no"]),
            models.Index(fields=["verification_status"]),
        ]
        verbose_name = "Add Drawing Sheet Revision"
        verbose_name_plural = "Add Drawing Sheet Revisions"

    def __str__(self):
        return f"{self.drawing_sheet} Rev {self.revision_no}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.verification_status != self.STATUS_VERIFIED:
                self.is_current = False

            if self.is_current and self.verification_status == self.STATUS_VERIFIED:
                DrawingSheetRevision.objects.filter(
                    drawing_sheet=self.drawing_sheet,
                    is_current=True,
                ).exclude(pk=self.pk).update(is_current=False)

            super().save(*args, **kwargs)
class DrawingImportBatch(models.Model):
    bom = models.ForeignKey(
        "procurement.BOMHeader",
        on_delete=models.SET_NULL,
        related_name="drawing_import_batches",
        null=True,
        blank=True,
    )
    batch_name = models.CharField(max_length=255, blank=True, default="")
    source_filename = models.CharField(max_length=255, blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_drawing_batches",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.batch_name or f"Drawing Batch {self.id}"


class DrawingImportFile(models.Model):
    STATUS_ANALYZED = "ANALYZED"
    STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_SKIPPED = "SKIPPED"
    STATUS_IMPORTED = "IMPORTED"

    STATUS_CHOICES = [
        (STATUS_ANALYZED, "Analyzed"),
        (STATUS_NEEDS_REVIEW, "Needs Review"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_IMPORTED, "Imported"),
    ]

    batch = models.ForeignKey(
        DrawingImportBatch,
        on_delete=models.CASCADE,
        related_name="files",
    )
    original_filename = models.CharField(max_length=255, blank=True, default="")
    page_number = models.PositiveIntegerField(default=1)

    detected_drawing_no = models.CharField(max_length=255, blank=True, default="")
    detected_revision_no = models.CharField(max_length=50, blank=True, default="")

    confirmed_drawing_no = models.CharField(max_length=255, blank=True, default="")
    confirmed_revision_no = models.CharField(max_length=50, blank=True, default="")

    extracted_text = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ANALYZED,
    )

    imported_revision = models.ForeignKey(
        "drawings.DrawingSheetRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_source_files",
    )

    class Meta:
        ordering = ["batch", "page_number"]

    def __str__(self):
        return f"{self.original_filename} - Page {self.page_number}"
