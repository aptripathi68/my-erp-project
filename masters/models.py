from django.db import models


class Group2(models.Model):
    """Group2 master from Excel"""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['code']
        verbose_name_plural = "Groups 2"

    def __str__(self):
        return f"{self.code} - {self.name}"


class Grade(models.Model):
    """Grade master from Excel"""
    group2 = models.ForeignKey(
        Group2,
        on_delete=models.CASCADE,
        related_name='grades'
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['group2', 'code']
        unique_together = ['group2', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Item(models.Model):
    item_master_id = models.CharField(max_length=50, unique=True, db_index=True)

    group2 = models.ForeignKey(
        Group2,
        on_delete=models.PROTECT,
        related_name='items'
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.PROTECT,
        related_name='items'
    )

    item_description = models.TextField()

    # From Excel
    group1_name = models.CharField(max_length=200, blank=True)
    section_name = models.CharField(max_length=200, blank=True)

    unit_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    # Optional future fields
    hsn_code = models.CharField(max_length=20, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    import_batch_id = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['group2', 'grade', 'item_description']
        indexes = [
            models.Index(fields=['item_master_id']),
        ]

    def __str__(self):
        return f"{self.item_master_id} - {self.item_description[:50]}"