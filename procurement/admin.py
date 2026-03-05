
from django.contrib import admin
from .models import Site, GRN, GRNItem

class GRNItemInline(admin.TabularInline):
    model = GRNItem
    extra = 1
    fields = ['item', 'quantity_received', 'unit_price', 'total_price', 'batch_number']
    readonly_fields = ['total_price']

@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']

@admin.register(GRN)
class GRNAdmin(admin.ModelAdmin):
    list_display = ['grn_number', 'received_date', 'supplier_name', 'site', 'received_by', 'total_value']
    list_filter = ['received_date', 'site']
    search_fields = ['grn_number', 'supplier_name']
    readonly_fields = ['grn_number', 'total_quantity', 'total_value', 'total_weight']
    inlines = [GRNItemInline]
    
    fieldsets = (
        ('GRN Information', {
            'fields': ('grn_number', 'received_date', 'supplier_name', 'site', 'received_by', 'notes')
        }),
        ('Totals', {
            'fields': ('total_quantity', 'total_value', 'total_weight'),
            'classes': ('collapse',)
        }),
    )

@admin.register(GRNItem)
class GRNItemAdmin(admin.ModelAdmin):
    list_display = ['grn', 'item', 'quantity_received', 'unit_price', 'total_price']
    list_filter = ['grn__received_date']
    search_fields = ['item__item_description', 'batch_number']

# ===============================
# BOM ADMIN REGISTRATION
# ===============================

from .models import BOMHeader, BOMMark, BOMComponent


@admin.register(BOMHeader)
class BOMHeaderAdmin(admin.ModelAdmin):

    list_display = (
        "bom_name",
        "uploaded_at",
        "uploaded_by"
    )

    search_fields = (
        "bom_name",
    )

    ordering = (
        "-uploaded_at",
    )


@admin.register(BOMMark)
class BOMMarkAdmin(admin.ModelAdmin):

    list_display = (
        "mark_no",
        "sheet_name",
        "bom",
    )

    search_fields = (
        "mark_no",
    )

    list_filter = (
        "bom",
        "sheet_name",
    )


@admin.register(BOMComponent)
class BOMComponentAdmin(admin.ModelAdmin):

    list_display = (
        "mark",
        "item",
        "item_description_raw",
        "qty_all",
        "length_mm",
        "line_weight_kg",
    )

    search_fields = (
        "item_description_raw",
        "mark__mark_no",
    )

    list_filter = (
        "item",
    )