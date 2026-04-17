from django.contrib import admin
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
    list_display = ["name", "location_type", "rack_number", "shelf_number", "bin_number", "is_active"]
    list_filter = ["location_type", "is_active"]
    search_fields = ["name", "rack_number", "shelf_number", "bin_number"]


@admin.register(StockObject)
class StockObjectAdmin(admin.ModelAdmin):
    list_display = ["id", "object_type", "source_type", "item", "qr_code", "weight", "created_at"]
    list_filter = ["object_type", "source_type", "qr_required"]
    search_fields = ["item__item_description", "qr_code", "mark_no", "remarks"]


@admin.register(StockLedgerEntry)
class StockLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "txn", "item", "location", "qty", "weight", "created_at"]
    list_filter = ["location", "item"]
    search_fields = ["item__item_description", "location__name", "stock_object__qr_code"]
