from django.contrib import admin
from .models import BOMMark


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

    list_filter = (
        "uploaded_at",
        "client_name",
        "project_name",
    )

    ordering = ("-uploaded_at",)


@admin.register(BOMMark)
class BOMMarkAdmin(admin.ModelAdmin):
    list_display = (
        "erc_mark",
        "erc_quantity",
        "main_section",
        "sheet_name",
        "drawing_no",
        "revision_no",
        "area_of_supply",
        "bom",
    )

    search_fields = (
        "erc_mark",
        "main_section",
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
        "bom_mark",
        "part_mark",
        "section_name",
        "grade_name",
        "part_quantity_per_assy",
        "length_mm",
        "width_mm",
        "engg_weight_kg",
        "item",
        "excel_row",
    )

    search_fields = (
        "bom_mark__erc_mark",
        "part_mark",
        "section_name",
        "grade_name",
        "item_description_raw",
        "item__item_description",
    )

    list_filter = (
        "grade_name",
        "item",
    )

    list_select_related = (
        "bom_mark",
        "item",
    )