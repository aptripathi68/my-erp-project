from django.contrib import admin
from .models import Group2, Grade, Item


@admin.register(Group2)
class Group2Admin(admin.ModelAdmin):
    list_display = ["code", "name", "grade_count", "item_count"]
    search_fields = ["code", "name"]
    ordering = ["code"]

    def grade_count(self, obj):
        return obj.grades.count()
    grade_count.short_description = "Grades"

    def item_count(self, obj):
        return Item.objects.filter(group2=obj).count()
    item_count.short_description = "Items"


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "group2", "item_count"]
    list_filter = ["group2"]
    search_fields = ["code", "name"]
    ordering = ["group2__code", "code"]

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = "Items"


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """
    Online Item Master maintenance:
    - browse rows in list view
    - inline edit a few safe fields
    - click first column for full edit
    - add new row from admin
    - while editing an item, Group2 and Grade remain normal dropdown widgets
      so Django can show the related-object add/edit buttons if permissions allow
    """

    list_display = [
        "item_master_id",
        "item_description_short",
        "section_name",
        "group2",
        "grade",
        "unit_weight",
        "unit_weight_basis",
        "is_active",
    ]

    list_filter = [
        "group2",
        "grade",
        "unit_weight_basis",
        "is_active",
    ]

    search_fields = [
        "item_master_id",
        "item_description",
        "section_name",
        "item_description_norm",
        "hsn_code",
    ]

    # Keep inline editing light for speed/safety
    list_editable = [
        "unit_weight",
        "unit_weight_basis",
        "is_active",
    ]

    ordering = ["item_master_id"]
    list_per_page = 25
    save_on_top = True

    list_select_related = ("group2", "grade")

    readonly_fields = [
        "item_description_norm",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Basic Information", {
            "fields": (
                "item_master_id",
                "item_description",
                "section_name",
                "item_description_norm",
                "group2",
                "grade",
                "is_active",
            )
        }),
        ("Weight Information", {
            "fields": (
                "unit_weight",
                "unit_weight_basis",
            )
        }),
        ("Other Details", {
            "classes": ("collapse",),
            "fields": (
                "group1_name",
                "hsn_code",
                "tax_rate",
                "import_batch_id",
            )
        }),
        ("Audit", {
            "classes": ("collapse",),
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("group2", "grade")
        )

    @admin.display(description="Item Description")
    def item_description_short(self, obj):
        text = obj.item_description or ""
        return text[:80] + ("..." if len(text) > 80 else "")