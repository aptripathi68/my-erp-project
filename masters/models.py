from __future__ import annotations

import re
import secrets

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
    - remove plate 'mm' thickness suffix for PL items
    - remove all spaces
    """
    text = (text or "").strip()
    text = text.replace("×", "x")
    text = _ws_re.sub(" ", text)
    text = text.lower()

    if text.startswith("pl"):
        text = re.sub(r"(?<=\d)\s*mm\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bmm\b", "", text, flags=re.IGNORECASE)
        text = _ws_re.sub(" ", text).strip()

    text = text.replace(" ", "")
    return text


def clean_section_name(section: str) -> str:
    """
    Clean Section Name before saving.

    Removes 'MM' suffix from plate thickness.
    Example:
        PL10MM → PL10
        PL 10 MM → PL 10
    """
    section = (section or "").strip().upper()
    section = _ws_re.sub(" ", section)

    if section.startswith("PL"):
        section = re.sub(r"(?<=\d)\s*MM\b", "", section, flags=re.IGNORECASE)
        section = re.sub(r"\bMM\b", "", section, flags=re.IGNORECASE)
        section = _ws_re.sub(" ", section).strip()

    return section


def is_plate_description(item_description: str) -> bool:
    """
    Heuristic: treat descriptions starting with 'PL' as steel plates.
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

    item_description = models.TextField()

    item_description_norm = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Auto-computed normalized description for matching and uniqueness. Not editable.",
    )

    group1_name = models.CharField(max_length=200, blank=True)
    section_name = models.CharField(max_length=200, blank=True)

    unit_weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    unit_weight_basis = models.CharField(
        max_length=20,
        choices=UnitWeightBasis.choices,
        default=UnitWeightBasis.KG_PER_M,
        db_index=True,
    )

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
        """
        norm = normalize_item_description(self.item_description)
        if not norm:
            raise ValidationError({"item_description": "Item description cannot be blank."})

        self.item_description_norm = norm

        qs = Item.objects.filter(item_description_norm=norm)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.exists():
            clash = qs.first()
            raise ValidationError({
                "item_description": (
                    f"Duplicate item_description after normalization. "
                    f"Conflicts with item_master_id={clash.item_master_id} "
                    f"('{clash.item_description}')."
                )
            })

    def save(self, *args, **kwargs):

        # Auto-generate system item_master_id
        if not self.item_master_id:
            while True:
                generated_id = secrets.token_hex(6)
                if not Item.objects.filter(item_master_id=generated_id).exists():
                    self.item_master_id = generated_id
                    break

        # Clean section name (remove MM for plates)
        self.section_name = clean_section_name(self.section_name)

        # Normalize description
        self.item_description_norm = normalize_item_description(self.item_description)

        # Set weight basis automatically
        if is_plate_description(self.item_description):
            self.unit_weight_basis = self.UnitWeightBasis.KG_PER_SQM
        else:
            self.unit_weight_basis = self.UnitWeightBasis.KG_PER_M

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        desc = (self.item_description or "")[:50]
        return f"{self.item_master_id} - {desc}"