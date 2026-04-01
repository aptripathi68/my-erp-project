from django.contrib import admin

from .models import (
    EstimateBudgetHead,
    EstimateCostHead,
    EstimateExpense,
    EstimateProject,
    EstimateProjectSupplier,
    EstimateRawMaterialLine,
    EstimateRawMaterialRate,
    EstimateSupplier,
)


class EstimateProjectSupplierInline(admin.TabularInline):
    model = EstimateProjectSupplier
    extra = 0


class EstimateRawMaterialRateInline(admin.TabularInline):
    model = EstimateRawMaterialRate
    extra = 0


@admin.register(EstimateSupplier)
class EstimateSupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "contact_person", "phone", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "contact_person", "phone", "email"]


@admin.register(EstimateProject)
class EstimateProjectAdmin(admin.ModelAdmin):
    list_display = [
        "inquiry_no",
        "client_name",
        "project_name",
        "quantity_mt",
        "status",
        "quotation_locked",
        "work_order_no",
    ]
    list_filter = ["status", "quotation_locked", "created_at"]
    search_fields = ["inquiry_no", "client_name", "project_name", "purchase_order_no", "work_order_no"]
    inlines = [EstimateProjectSupplierInline]


@admin.register(EstimateRawMaterialLine)
class EstimateRawMaterialLineAdmin(admin.ModelAdmin):
    list_display = ["project", "item", "quantity_mt", "lowest_rate_per_mt", "final_rate_per_mt", "total_amount"]
    search_fields = ["project__inquiry_no", "project__project_name", "item__item_description", "item__section_name"]
    list_select_related = ["project", "item"]
    inlines = [EstimateRawMaterialRateInline]


@admin.register(EstimateCostHead)
class EstimateCostHeadAdmin(admin.ModelAdmin):
    list_display = ["project", "sort_order", "name", "line_type", "percentage", "rate_per_kg", "amount"]
    list_filter = ["line_type"]
    search_fields = ["project__inquiry_no", "project__project_name", "name", "code"]


@admin.register(EstimateBudgetHead)
class EstimateBudgetHeadAdmin(admin.ModelAdmin):
    list_display = ["budget_code", "project", "name", "budget_amount", "spent_amount", "approved_amount"]
    search_fields = ["budget_code", "project__inquiry_no", "project__project_name", "name"]


@admin.register(EstimateExpense)
class EstimateExpenseAdmin(admin.ModelAdmin):
    list_display = ["budget_head", "expense_date", "reference_no", "amount", "status", "created_by", "approved_by"]
    list_filter = ["status", "expense_date"]
    search_fields = ["budget_head__budget_code", "description", "reference_no"]
