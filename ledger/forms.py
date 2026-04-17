from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Sum

from masters.models import Item

from .models import StockLocation, StockObject, StockTxn


class StockLocationForm(forms.ModelForm):
    class Meta:
        model = StockLocation
        fields = [
            "name",
            "location_type",
            "rack_number",
            "shelf_number",
            "bin_number",
            "latitude",
            "longitude",
            "remarks",
            "is_active",
        ]


class InventoryInwardForm(forms.Form):
    entry_type = forms.ChoiceField(
        choices=[
            ("OPENING", "Opening Stock"),
            ("NEW_PURCHASE", "New Purchase Inward"),
            ("RETURN", "Return Entry"),
            ("CORRECTION", "Correction Entry"),
        ]
    )
    object_type = forms.ChoiceField(
        choices=[
            ("RAW", "Fresh Raw Material"),
            ("OFFCUT", "Off-cut"),
            ("SCRAP", "Scrap"),
        ]
    )
    item = forms.ModelChoiceField(queryset=Item.objects.filter(is_active=True).order_by("item_description"))
    location = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True).order_by("name"))
    qty = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    weight = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    qr_code = forms.CharField(required=False, max_length=16)
    photo_url = forms.URLField(required=False)
    capture_latitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6)
    capture_longitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6)
    reference_no = forms.CharField(required=False, max_length=100)
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        object_type = cleaned.get("object_type")
        qr_code = (cleaned.get("qr_code") or "").strip()
        if object_type == "OFFCUT":
            if not qr_code:
                self.add_error("qr_code", "QR code is compulsory for off-cuts.")
            elif (not qr_code.isdigit()) or len(qr_code) != 16:
                self.add_error("qr_code", "QR code must be exactly 16 digits.")
            elif StockObject.objects.filter(qr_code=qr_code).exists():
                self.add_error("qr_code", "This QR code already exists.")
        return cleaned


class TemporaryIssueForm(forms.Form):
    project_reference = forms.CharField(max_length=100)
    project_name = forms.CharField(required=False, max_length=255)
    item = forms.ModelChoiceField(queryset=Item.objects.filter(is_active=True).order_by("item_description"))
    source_location = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True).order_by("name"))
    destination_location = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True).order_by("name"))
    stock_object = forms.ModelChoiceField(
        queryset=StockObject.objects.filter(object_type="OFFCUT").order_by("qr_code"),
        required=False,
    )
    qty = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    weight = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    reference_no = forms.CharField(required=False, max_length=100)
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        stock_object = cleaned.get("stock_object")
        if stock_object:
            if stock_object.item_id != item.id:
                self.add_error("stock_object", "Selected off-cut does not belong to the selected item.")
        return cleaned


class TemporaryReturnForm(forms.Form):
    issue_txn = forms.ModelChoiceField(
        queryset=StockTxn.objects.filter(txn_type="TEMP_ISSUE", posted=True).order_by("-created_at")
    )
    return_type = forms.ChoiceField(
        choices=[
            ("RAW", "Reusable Raw Material"),
            ("OFFCUT", "Off-cut"),
            ("SCRAP", "Scrap"),
        ]
    )
    destination_location = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True).order_by("name"))
    qty = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    weight = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    qr_code = forms.CharField(required=False, max_length=16)
    photo_url = forms.URLField(required=False)
    capture_latitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6)
    capture_longitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6)
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        issue_txn = cleaned.get("issue_txn")
        return_type = cleaned.get("return_type")
        qr_code = (cleaned.get("qr_code") or "").strip()
        qty = cleaned.get("qty") or Decimal("0")
        weight = cleaned.get("weight") or Decimal("0")

        if not issue_txn:
            return cleaned

        issue_line = issue_txn.lines.first()
        if not issue_line:
            raise ValidationError("Selected temporary issue has no issue line.")

        returned = (
            issue_txn.lines.model.objects.filter(txn__parent_txn=issue_txn, txn__txn_type="TEMP_RETURN", txn__posted=True)
            .aggregate(qty=Sum("qty"), weight=Sum("weight"))
        )
        returned_qty = returned["qty"] or Decimal("0")
        returned_weight = returned["weight"] or Decimal("0")
        remaining_qty = (issue_line.qty or Decimal("0")) - returned_qty
        remaining_weight = (issue_line.weight or Decimal("0")) - returned_weight

        if qty > remaining_qty:
            self.add_error("qty", f"Return quantity exceeds pending issued quantity ({remaining_qty}).")
        if weight > remaining_weight:
            self.add_error("weight", f"Return weight exceeds pending issued weight ({remaining_weight}).")

        if return_type == "OFFCUT":
            if not qr_code:
                self.add_error("qr_code", "QR code is compulsory for returned off-cuts.")
            elif (not qr_code.isdigit()) or len(qr_code) != 16:
                self.add_error("qr_code", "QR code must be exactly 16 digits.")
            elif StockObject.objects.filter(qr_code=qr_code).exists():
                self.add_error("qr_code", "This QR code already exists.")

        return cleaned
