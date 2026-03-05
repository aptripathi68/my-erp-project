# masters/models.py
from __future__ import annotations

import re
from django.db import models
from django.core.exceptions import ValidationError


# -----------------------------
# Normalization helpers
# -----------------------------
_ws_re = re.compile(r"\s+")


def normalize_item_description(text: str) -> str:
    """
    Normalization used for BOM ↔ Item matching and duplicate prevention.

    Rules:
    - trim
    - × → x
    - collapse whitespace
    - lowercase
    - remove all spaces (so 'ISA 50x50x6' == 'ISA50x50x6')
    """
    text = (text or "").strip()
    text = text.replace("×", "x")
    text = _ws_re.sub(" ", text)
    text = text.lower()
    text = text.replace(" ", "")
    return text


def is_plate_description(item_description: str) -> bool:
    """
    Heuristic: treat descriptions starting with 'PL' as steel plates.
    Adjust if your Item Master uses different naming patterns.
    Examples:
      - 'PL 147x10'
      - 'PLT 10MM 1250X2500'
    """
    d = (item_description or "").strip().upper()
    return d.startswith("PL") or d.startswith("PLT")


# -----------------------------
# Masters
# -----------------------------
class Group2(models.Model):
    """Group2 master from Excel"""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "Groups 2"

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Grade(models.Model):
    """Grade master from Excel"""
    group2 = models.ForeignKey(
        Group2,
        on_delete=models.CASCADE,
        related_name="grades",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["group2", "code"]
        unique_together = ["group2", "code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Item(models.Model):
    """
    Item master row.

    Important project rule:
    - For plates: unit_weight is kg per square meter (kg/m²)
    - For remaining sections: unit_weight is kg per meter (kg/m)

    We store unit_weight_basis to make this explicit and safe.
    """

    class UnitWeightBasis(models.TextChoices):
        KG_PER_M = "KG_PER_M", "kg per meter"
        KG_PER_SQM = "KG_PER_SQM", "kg per square meter"

    item_master_id = models.CharField(max_length=50, unique=True, db_index=True)

    group2 = models.ForeignKey(
        Group2,
        on_delete=models.PROTECT,
        related_name="items",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.PROTECT,
        related_name="items",
    )

    # Human-readable description (your key for BOM matching)
    item_description = models.TextField()

    # NEW: normalized key for robust matching and to prevent duplicates
    item_description_norm = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        blank=True,
        default="",
        help_text="Auto-generated normalized item_description for BOM matching.",
    )

    # From Excel
    group1_name = models.CharField(max_length=200, blank=True)
    section_name = models.CharField(max_length=200, blank=True)

    # Weight value; meaning depends on unit_weight_basis
    unit_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    # NEW: weight basis (kg/m vs kg/m²)
    unit_weight_basis = models.CharField(
        max_length=20,
        choices=UnitWeightBasis.choices,
        default=UnitWeightBasis.KG_PER_M,
        db_index=True,
    )

    # Optional future fields
    hsn_code = models.CharField(max_length=20, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    import_batch_id = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["group2", "grade", "item_description"]
        indexes = [
            models.Index(fields=["item_master_id"]),
            models.Index(fields=["item_description_norm"]),
            models.Index(fields=["is_active"]),
        ]

    def clean(self) -> None:
        """
        Extra safety: ensure norm is computed and unique.
        Django will enforce unique constraint, but this gives a clearer message.
        """
        norm = normalize_item_description(self.item_description)
        if not norm:
            raise ValidationError({"item_description": "Item description cannot be blank."})

        # If someone manually set it, keep it consistent
        self.item_description_norm = norm

        qs = Item.objects.filter(item_description_norm=norm)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            # show the clashing item id for easy fix
            clash = qs.first()
            raise ValidationError({
                "item_description": (
                    f"Duplicate item_description after normalization. "
                    f"Conflicts with item_master_id={clash.item_master_id} "
                    f"('{clash.item_description}')."
                )
            })

    def save(self, *args, **kwargs):
        # Always compute normalized description
        self.item_description_norm = normalize_item_description(self.item_description)

        # Auto-set basis based on description (safe default)
        if is_plate_description(self.item_description):
            self.unit_weight_basis = self.UnitWeightBasis.KG_PER_SQM
        else:
            self.unit_weight_basis = self.UnitWeightBasis.KG_PER_M

        # Optional: run model validation on save (helps admin edits)
        # Comment out if you prefer speed over strict validation.
        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        desc = (self.item_description or "")[:50]
        return f"{self.item_master_id} - {desc}"