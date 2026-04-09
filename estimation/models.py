from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from masters.models import Item


ZERO = Decimal("0.00")


class EstimateSupplier(models.Model):
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class EstimateProject(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        RATE_FINALIZATION = "RATE_FINALIZATION", "Rate Finalization"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        PO_RECEIVED = "PO_RECEIVED", "PO Received"
        IN_EXECUTION = "IN_EXECUTION", "In Execution"
        CLOSED = "CLOSED", "Closed"

    inquiry_no = models.CharField(max_length=30, unique=True, editable=False, db_index=True)
    client_name = models.CharField(max_length=255)
    project_name = models.CharField(max_length=255)
    quantity_mt = models.DecimalField(max_digits=15, decimal_places=6, default=0)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    quotation_locked = models.BooleanField(default=False)

    work_order_no = models.CharField(max_length=100, blank=True)
    purchase_order_no = models.CharField(max_length=100, blank=True)
    purchase_order_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)

    raw_material_cost_per_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_estimated_cost_per_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quotation_price_per_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quotation_price_per_mt = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quotation_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    quoted_price_per_mt = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    approved_price_per_mt = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    decision_notes = models.TextField(blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    planning_notes = models.TextField(blank=True)
    marketing_notes = models.TextField(blank=True)
    management_notes = models.TextField(blank=True)
    accounts_notes = models.TextField(blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_estimate_projects",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_estimate_projects",
        null=True,
        blank=True,
    )
    decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="decided_estimate_projects",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at", "inquiry_no"]

    def __str__(self) -> str:
        return f"{self.inquiry_no} - {self.project_name}"

    @property
    def quantity_kg(self) -> Decimal:
        return self.quantity_mt or ZERO

    @property
    def estimated_price_per_mt(self) -> Decimal:
        return self.quotation_price_per_mt or ZERO

    @property
    def estimated_price_per_kg(self) -> Decimal:
        return self.quotation_price_per_kg or ZERO

    @property
    def estimated_value(self) -> Decimal:
        return self.quotation_value or ZERO

    def save(self, *args, **kwargs):
        if not self.inquiry_no:
            year = timezone.now().year
            prefix = f"EST/{year}/"
            last = (
                EstimateProject.objects.filter(inquiry_no__startswith=prefix)
                .order_by("inquiry_no")
                .last()
            )
            if last:
                last_number = int(last.inquiry_no.split("/")[-1])
            else:
                last_number = 0
            self.inquiry_no = f"{prefix}{last_number + 1:05d}"
        super().save(*args, **kwargs)

    @property
    def financial_year_label(self) -> str:
        base_date = self.purchase_order_date or self.created_at.date()
        start_year = base_date.year if base_date.month >= 4 else base_date.year - 1
        end_year = start_year + 1
        return f"FY {start_year}-{str(end_year)[-2:]}"


class EstimateProjectSupplier(models.Model):
    project = models.ForeignKey(
        EstimateProject,
        on_delete=models.CASCADE,
        related_name="project_suppliers",
    )
    supplier = models.ForeignKey(
        EstimateSupplier,
        on_delete=models.PROTECT,
        related_name="project_links",
    )
    column_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["column_order", "supplier__name"]
        unique_together = [("project", "supplier")]

    def __str__(self) -> str:
        return f"{self.project.inquiry_no} - {self.supplier.name}"


class EstimateSupplierQuotationFile(models.Model):
    project = models.ForeignKey(
        EstimateProject,
        on_delete=models.CASCADE,
        related_name="supplier_quotation_files",
    )
    supplier = models.ForeignKey(
        EstimateSupplier,
        on_delete=models.PROTECT,
        related_name="quotation_files",
    )
    file_key = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="")
    file_size = models.BigIntegerField(null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_estimate_supplier_files",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["supplier__name", "-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.project.inquiry_no} - {self.supplier.name} - {self.original_filename or self.file_key}"


class EstimateRawMaterialLine(models.Model):
    project = models.ForeignKey(
        EstimateProject,
        on_delete=models.CASCADE,
        related_name="raw_material_lines",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="estimate_raw_material_lines",
    )
    finished_weight_mt = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    quantity_mt = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    final_rate_per_mt = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    lowest_rate_per_mt = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.project.inquiry_no} - {self.item.item_description}"

    def recalculate_from_rates(self, save: bool = True) -> None:
        rates = list(
            self.supplier_rates.exclude(rate_per_mt__isnull=True).values_list("rate_per_mt", flat=True)
        )
        if rates:
            self.lowest_rate_per_mt = min(rates)
        else:
            self.lowest_rate_per_mt = ZERO

        chosen_rate = self.final_rate_per_mt or self.lowest_rate_per_mt or ZERO
        self.final_rate_per_mt = chosen_rate
        self.total_amount = (self.quantity_mt or ZERO) * chosen_rate

        if save:
            self.save(update_fields=["lowest_rate_per_mt", "final_rate_per_mt", "total_amount"])


class EstimateRawMaterialRate(models.Model):
    line = models.ForeignKey(
        EstimateRawMaterialLine,
        on_delete=models.CASCADE,
        related_name="supplier_rates",
    )
    supplier = models.ForeignKey(
        EstimateSupplier,
        on_delete=models.PROTECT,
        related_name="raw_material_rates",
    )
    rate_per_mt = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ["supplier__name"]
        unique_together = [("line", "supplier")]

    def __str__(self) -> str:
        return f"{self.line_id} - {self.supplier.name}"


class EstimateCostHead(models.Model):
    class LineType(models.TextChoices):
        ENTRY = "ENTRY", "Entry"
        TOTAL = "TOTAL", "Total"

    project = models.ForeignKey(
        EstimateProject,
        on_delete=models.CASCADE,
        related_name="cost_heads",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    line_type = models.CharField(max_length=20, choices=LineType.choices, default=LineType.ENTRY)
    percentage = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    rate_per_kg = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    remarks = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    is_percentage_editable = models.BooleanField(default=True)
    is_rate_editable = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        unique_together = [("project", "code")]

    def __str__(self) -> str:
        return f"{self.project.inquiry_no} - {self.name}"


class EstimateBudgetHead(models.Model):
    project = models.ForeignKey(
        EstimateProject,
        on_delete=models.CASCADE,
        related_name="budget_heads",
    )
    cost_head = models.ForeignKey(
        EstimateCostHead,
        on_delete=models.PROTECT,
        related_name="budget_heads",
    )
    budget_code = models.CharField(max_length=120, unique=True, editable=False)
    name = models.CharField(max_length=255)
    budget_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    spent_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    approved_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["budget_code"]

    def __str__(self) -> str:
        return self.budget_code

    def save(self, *args, **kwargs):
        if not self.budget_code:
            work_order = self.project.work_order_no or self.project.inquiry_no.replace("/", "-")
            count = self.project.budget_heads.exclude(pk=self.pk).count() + 1
            self.budget_code = f"{work_order}/{count:03d}"
        super().save(*args, **kwargs)


class EstimateExpense(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    budget_head = models.ForeignKey(
        EstimateBudgetHead,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    expense_date = models.DateField(default=timezone.now)
    reference_no = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_estimate_expenses",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_estimate_expenses",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.budget_head.budget_code} - {self.amount}"
