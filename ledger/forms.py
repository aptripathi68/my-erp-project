from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Sum

from masters.models import Group2, Item

from .models import StockLocation, StockObject, StockTxn


class StockLocationForm(forms.ModelForm):
    class Meta:
        model = StockLocation
        fields = [
            "name",
            "location_type",
            "latitude",
            "longitude",
            "remarks",
            "is_active",
        ]
        labels = {
            "name": "Store / Location Name",
            "location_type": "Location Type",
            "latitude": "Latitude",
            "longitude": "Longitude",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location_type"].choices = [("STORE", "Store")]
        self.fields["location_type"].initial = "STORE"
        self.fields["latitude"].widget.attrs.update({"readonly": "readonly", "placeholder": "Capture from mobile GPS"})
        self.fields["longitude"].widget.attrs.update({"readonly": "readonly", "placeholder": "Capture from mobile GPS"})


class TransferStoreRecordsForm(forms.Form):
    target_location = forms.ModelChoiceField(
        queryset=StockLocation.objects.filter(is_active=True, location_type="STORE").order_by("name"),
        label="Transfer to active store",
    )


class InventoryInwardForm(forms.Form):
    STOCK_FOR_CHOICES = [
        ("PROJECT", "Item entry against project"),
        ("SPARE", "Item entry of spare store"),
    ]

    entry_type = forms.ChoiceField(
        choices=[
            ("OPENING", "Opening Stock"),
            ("NEW_PURCHASE", "New Purchase Inward"),
            ("RETURN", "Return Entry"),
            ("CORRECTION", "Correction Entry"),
        ]
    )
    stock_for = forms.ChoiceField(choices=STOCK_FOR_CHOICES, initial="PROJECT")
    object_type = forms.ChoiceField(
        choices=[
            ("RAW", "Fresh Raw Material"),
            ("OFFCUT", "Off-cut"),
            ("SCRAP", "Scrap"),
        ]
    )
    group2 = forms.ModelChoiceField(
        queryset=Group2.objects.order_by("name"),
        label="Group-2",
        required=False,
    )
    section_name = forms.CharField(
        label="Section Name",
        required=False,
        widget=forms.Select(choices=[("", "Select section")]),
    )
    grade_selector = forms.CharField(
        label="Grade",
        required=False,
        widget=forms.Select(choices=[("", "Select grade")]),
    )
    item = forms.ModelChoiceField(
        queryset=Item.objects.filter(is_active=True).order_by("item_description"),
        label="Item Description",
    )
    location = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True, location_type="STORE").order_by("name"))
    project_reference = forms.CharField(required=False, max_length=100)
    project_name = forms.CharField(required=False, max_length=255)
    rack_number = forms.CharField(required=False, max_length=50)
    shelf_number = forms.CharField(required=False, max_length=50)
    bin_number = forms.CharField(required=False, max_length=50)
    qty = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    weight = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    qr_code = forms.CharField(
        required=False,
        max_length=16,
        label="QR Code",
        widget=forms.TextInput(
            attrs={
                "readonly": "readonly",
                "placeholder": "Scan pre-printed QR from mobile camera",
            }
        ),
    )
    raw_material_photo = forms.ImageField(
        required=False,
        label="Photo of Raw Material",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/*",
                "capture": "environment",
                "class": "camera-photo-input",
            }
        ),
    )
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        cleaned = super().clean()
        group2 = cleaned.get("group2")
        section_name = (cleaned.get("section_name") or "").strip()
        grade_selector = (cleaned.get("grade_selector") or "").strip()
        item = cleaned.get("item")
        object_type = cleaned.get("object_type")
        qr_code = (cleaned.get("qr_code") or "").strip()
        stock_for = cleaned.get("stock_for")
        project_reference = (cleaned.get("project_reference") or "").strip()

        if not group2:
            self.add_error("group2", "Group-2 is required.")
        if not section_name:
            self.add_error("section_name", "Section Name is required.")
        if not grade_selector:
            self.add_error("grade_selector", "Grade is required.")
        if item:
            if group2 and item.group2_id != group2.id:
                self.add_error("item", "Selected item does not belong to the selected Group-2.")
            if section_name and item.section_name != section_name:
                self.add_error("item", "Selected item does not belong to the selected Section Name.")
            if grade_selector and str(item.grade_id) != grade_selector:
                self.add_error("item", "Selected item does not belong to the selected Grade.")
        if object_type == "OFFCUT":
            if not qr_code:
                self.add_error("qr_code", "QR code is compulsory for off-cuts.")
            elif (not qr_code.isdigit()) or len(qr_code) != 16:
                self.add_error("qr_code", "QR code must be exactly 16 digits.")
            elif StockObject.objects.filter(qr_code=qr_code).exists():
                self.add_error("qr_code", "This QR code already exists.")
        if stock_for == "PROJECT" and not project_reference:
            self.add_error("project_reference", "Project reference is required for item entry against project.")
        return cleaned


class TemporaryIssueForm(forms.Form):
    project_reference = forms.CharField(max_length=100)
    project_name = forms.CharField(required=False, max_length=255)
    item = forms.ModelChoiceField(queryset=Item.objects.filter(is_active=True).order_by("item_description"))
    source_location = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True, location_type="STORE").order_by("name"))
    destination_location = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True).exclude(location_type="STORE").order_by("name"))
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
        if stock_object and item and stock_object.item_id != item.id:
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
    destination_location = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True, location_type="STORE").order_by("name"))
    rack_number = forms.CharField(required=False, max_length=50)
    shelf_number = forms.CharField(required=False, max_length=50)
    bin_number = forms.CharField(required=False, max_length=50)
    qty = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    weight = forms.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    qr_code = forms.CharField(
        required=False,
        max_length=16,
        label="QR Code",
        widget=forms.TextInput(
            attrs={
                "readonly": "readonly",
                "placeholder": "Scan pre-printed QR from mobile camera",
            }
        ),
    )
    raw_material_photo = forms.ImageField(
        required=False,
        label="Photo of Raw Material",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/*",
                "capture": "environment",
                "class": "camera-photo-input",
            }
        ),
    )
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
