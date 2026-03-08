from django.db import models

# Create your models here.
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from masters.models import Item
from users.models import User

class Site(models.Model):
    """Site master"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class GRN(models.Model):
    """Goods Receipt Note"""
    grn_number = models.CharField(max_length=20, unique=True, editable=False)
    received_date = models.DateField(default=timezone.now)
    supplier_name = models.CharField(max_length=200)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name='grns')
    received_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='received_grns',
        limit_choices_to={'role__in': ['Store', 'Admin']}
    )
    notes = models.TextField(blank=True)
    
    # Calculated fields
    total_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_weight = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_grns',
        null=True
    )

    class Meta:
        ordering = ['-received_date', '-grn_number']
        indexes = [
            models.Index(fields=['grn_number']),
            models.Index(fields=['received_date']),
        ]
    
    def __str__(self):
        return f"{self.grn_number} - {self.supplier_name}"

    def save(self, *args, **kwargs):
        if not self.grn_number:
            year = timezone.now().year
            last_grn = GRN.objects.filter(
                grn_number__startswith=f'GRN/{year}/'
            ).order_by('grn_number').last()
            
            if last_grn:
                last_number = int(last_grn.grn_number.split('/')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.grn_number = f'GRN/{year}/{new_number:05d}'
        
        super().save(*args, **kwargs)

    def update_totals(self):
        items = self.items.all()
        self.total_quantity = sum(item.quantity_received for item in items)
        self.total_value = sum(item.total_price for item in items)
        self.total_weight = sum(item.total_weight for item in items)
        self.save(update_fields=['total_quantity', 'total_value', 'total_weight'])


class GRNItem(models.Model):
    grn = models.ForeignKey(GRN, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='grn_items')
    quantity_received = models.DecimalField(
        max_digits=15, 
        decimal_places=3,
        validators=[MinValueValidator(0.001)]
    )
    unit_price = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    total_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_weight = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    batch_number = models.CharField(max_length=50, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        self.total_price = self.quantity_received * self.unit_price
        if self.item.unit_weight:
            self.total_weight = self.quantity_received * self.item.unit_weight
        super().save(*args, **kwargs)
        self.grn.update_totals()
    
    def __str__(self):
        return f"{self.grn.grn_number} - {self.item.item_description[:50]}"
    
    # ============================================
# BOM STRUCTURE (Fabrication Job Definition)
# ============================================


class BOMHeader(models.Model):
    """
    Represents one uploaded BOM file
    Example: JK Cement / Frigate / Wonder
    """

    from django.conf import settings
from django.db import models

class BOMHeader(models.Model):
    bom_name = models.CharField(max_length=255)
    project_name = models.CharField(max_length=255, blank=True)
    client_name = models.CharField(max_length=255, blank=True)
    purchase_order_no = models.CharField(max_length=100, blank=True)
    purchase_order_date = models.DateField(null=True, blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_boms",
    )
    uploaded_at = models.DateTimeField()

    class Meta:
        ordering = ["-uploaded_at", "bom_name"]

    def __str__(self):
        return self.bom_name


class BOMMark(models.Model):
    """
    Each fabrication MARK number
    Example: SPS-204
    """

    bom = models.ForeignKey(
        BOMHeader,
        on_delete=models.CASCADE,
        related_name="marks"
    )

    sheet_name = models.CharField(max_length=200)

    mark_no = models.CharField(max_length=100)

    drawing_no = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["mark_no"]
        indexes = [
            models.Index(fields=["mark_no"]),
        ]

    def __str__(self):
        return f"{self.mark_no}"


class BOMComponent(models.Model):
    """
    Child parts under each MARK
    """

    mark = models.ForeignKey(
        BOMMark,
        on_delete=models.CASCADE,
        related_name="components"
    )

    item_no = models.CharField(
        max_length=20,
        blank=True
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="bom_components"
    )

    # Raw description from Excel
    item_description_raw = models.CharField(max_length=255)

    qty_all = models.DecimalField(
        max_digits=10,
        decimal_places=3
    )

    length_mm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    line_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True
    )

    excel_row = models.IntegerField()

    class Meta:
        ordering = ["excel_row"]

    def __str__(self):
        return f"{self.mark.mark_no} - {self.item_description_raw}"