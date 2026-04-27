from django.contrib import admin
from django import forms
from .models import (
    StockLocation,
    StockObject,
    StockTxn,
    StockTxnLine,
    StockLedgerEntry,
)


class StockTxnLineInline(admin.TabularInline):
    model = StockTxnLine
    extra = 1


class StoreLocationAdminForm(forms.ModelForm):
    class Meta:
        model = StockLocation
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location_type"].choices = [("STORE", "Store")]
        self.fields["location_type"].initial = "STORE"


@admin.register(StockTxn)
class StockTxnAdmin(admin.ModelAdmin):
    inlines = [StockTxnLineInline]
    list_display = [
        "id",
        "txn_type",
        "reference_no",
        "project_reference",
        "bridge_status",
        "posted",
        "created_at",
    ]
    list_filter = ["txn_type", "bridge_status", "posted", "entry_source_type"]
    search_fields = ["reference_no", "project_reference", "project_name"]

@admin.register(StockLocation)
class StockLocationAdmin(admin.ModelAdmin):
    form = StoreLocationAdminForm
    list_display = ["name", "latitude", "longitude", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "remarks"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(location_type="STORE")


@admin.register(StockObject)
class StockObjectAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "object_type",
        "source_type",
        "item",
        "qr_code",
        "heat_number",
        "plate_number",
        "test_certificate_no",
        "test_certificate_file_unavailable",
        "weight",
        "rate_per_kg",
        "stock_value",
        "created_at",
    ]
    list_filter = ["object_type", "source_type", "qr_required", "test_certificate_file_unavailable"]
    search_fields = [
        "item__item_description",
        "qr_code",
        "heat_number",
        "plate_number",
        "test_certificate_no",
        "mark_no",
        "remarks",
    ]

    @admin.display(description="Stock Value")
    def stock_value(self, obj):
        return (obj.weight or 0) * (obj.rate_per_kg or 0)


@admin.register(StockLedgerEntry)
class StockLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "txn", "item", "location", "qty", "weight", "created_at"]
    list_filter = ["location", "item"]
    search_fields = ["item__item_description", "location__name", "stock_object__qr_code"]
