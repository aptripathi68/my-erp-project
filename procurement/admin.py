from django.contrib import admin

from .models import (
    Site,
    GRN,
    GRNItem,
    BOMHeader,
    BOMMark,
    BOMComponent,
)


class GRNItemInline(admin.TabularInline):
    model = GRNItem
    extra = 1
    fields = ["item", "quantity_received", "unit_price", "total_price", "batch_number"]
    readonly_fields = ["total_price"]


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["code", "name"]


@admin.register(GRN)
class GRNAdmin(admin.ModelAdmin):
    list_display = [
        "grn_number",
        "received_date",
        "supplier_name",
        "site",
        "received_by",
        "total_value",
    ]
    list_filter = ["received_date", "site"]
    search_fields = ["grn_number", "supplier_name"]
    readonly_fields = ["grn_number", "total_quantity", "total_value", "total_weight"]
    inlines = [GRNItemInline]

    fieldsets = (
        ("GRN Information", {
            "fields": ("grn_number", "received_date", "supplier_name", "site", "received_by", "notes")
        }),
        ("Totals", {
            "fields": ("total_quantity", "total_value", "total_weight"),
            "classes": ("collapse",),
        }),
    )


@admin.register(GRNItem)
class GRNItemAdmin(admin.ModelAdmin):
    list_display = ["grn", "item", "quantity_received", "unit_price", "total_price"]
    list_filter = ["grn__received_date"]
    search_fields = ["item__item_description", "batch_number"]


# ===============================
# BOM ADMIN REGISTRATION
# ===============================

@admin.register(BOMHeader)
class BOMHeaderAdmin(admin.ModelAdmin):
    list_display = (
        "bom_name",
        "project_name",
        "client_name",
        "purchase_order_no",
        "purchase_order_date",
        "uploaded_at",
        "uploaded_by",
    )

    search_fields = (
        "bom_name",
        "project_name",
        "client_name",
        "purchase_order_no",
    )

    ordering = ("-uploaded_at",)

    list_filter = (
        "uploaded_at",
        "client_name",
        "project_name",
    )


@admin.register(BOMMark)
class BOMMarkAdmin(admin.ModelAdmin):
    list_display = (
        "mark_no",
        "sheet_name",
        "drawing_no",
        "revision_no",
        "area_of_supply",
        "bom",
    )

    search_fields = (
        "mark_no",
        "drawing_no",
        "revision_no",
        "area_of_supply",
        "bom__bom_name",
    )

    list_filter = (
        "bom",
        "sheet_name",
        "area_of_supply",
    )


@admin.register(BOMComponent)
class BOMComponentAdmin(admin.ModelAdmin):
    list_display = (
        "mark",
        "item",
        "item_no",
        "item_description_raw",
        "grade_raw",
        "item_part_quantity",
        "length_mm",
        "width_mm",
        "line_weight_kg",
        "excel_row",
    )

    search_fields = (
        "item_description_raw",
        "grade_raw",
        "item_no",
        "mark__mark_no",
        "item__item_description",
    )

    list_filter = (
        "item",
        "grade_raw",
    )

    list_select_related = (
        "mark",
        "item",
    )