from django.contrib import admin

from .models import (
    Site,
    GRN,
    GRNItem,
    BOMHeader,
    BOMMark,
    BOMComponent,
    ERC,
    INTERCUnit,
    RequirementLine,
    WorkOrder,
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
        "work_order",
        "purchase_order_date",
        "uploaded_at",
        "uploaded_by",
    )

    search_fields = (
        "bom_name",
        "project_name",
        "client_name",
        "purchase_order_no",
        "work_order__wo_number",
    )

    list_filter = (
        "uploaded_at",
        "client_name",
        "project_name",
    )

    ordering = ("-uploaded_at",)


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("wo_number", "project_name", "client_name", "status", "created_at")
    list_filter = ("status", "client_name")
    search_fields = ("wo_number", "project_name", "client_name", "purchase_order_no")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ERC)
class ERCAdmin(admin.ModelAdmin):
    list_display = ("erc_mark", "erc_quantity", "work_order", "sheet_name", "drawing_no", "status")
    list_filter = ("status", "work_order", "sheet_name")
    search_fields = ("erc_mark", "drawing_no", "work_order__wo_number")
    list_select_related = ("work_order", "bom_header")


@admin.register(INTERCUnit)
class INTERCUnitAdmin(admin.ModelAdmin):
    list_display = ("int_erc_code", "work_order", "erc", "sequence", "status", "dispatch_state")
    list_filter = ("status", "dispatch_state", "work_order")
    search_fields = ("int_erc_code", "erc__erc_mark", "work_order__wo_number")
    list_select_related = ("work_order", "erc")


@admin.register(RequirementLine)
class RequirementLineAdmin(admin.ModelAdmin):
    list_display = (
        "int_erc_unit",
        "item_specification",
        "grade_name",
        "required_qty",
        "required_weight_kg",
        "is_fully_covered",
    )
    list_filter = ("is_fully_covered", "work_order")
    search_fields = (
        "int_erc_unit__int_erc_code",
        "item_specification",
        "grade_name",
        "work_order__wo_number",
    )
    list_select_related = ("work_order", "erc", "int_erc_unit", "item")


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
