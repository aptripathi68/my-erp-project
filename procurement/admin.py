
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