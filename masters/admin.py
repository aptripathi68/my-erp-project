from django.contrib import admin
from .models import Group2, Grade, Item


@admin.register(Group2)
class Group2Admin(admin.ModelAdmin):
    list_display = ["code", "name", "grade_count", "item_count"]
    search_fields = ["code", "name"]

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

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = "Items"


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """
    Item Master Online Grid:
    - List view shows many rows (like Excel)
    - Inline edit for safe fields
    - Full edit still available by clicking item_master_id
    - Add new item still available from top-right "Add Item"
    """

    list_display = [
        "item_master_id",
        "item_description",
        "group2",
        "grade",
        "unit_weight",
        "unit_weight_basis",
        "is_active",
        "updated_at",
    ]

    # Inline editable fields in list view (safe operations)
    # NOTE: Django rule: first column of list_display cannot be editable.
    list_editable = [
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
        "item_description_norm",
        "hsn_code",
    ]

    ordering = ["item_description"]
    list_per_page = 50
    save_on_top = True  # shows Save buttons at top also

    # Optional: make it harder to accidentally delete
    actions = None

    # Optional: show read-only fields in the edit form (detail page)
    readonly_fields = ["item_description_norm", "created_at", "updated_at"]

    fieldsets = (
        ("Basic", {
            "fields": (
                "item_master_id",
                "item_description",
                "item_description_norm",
                "group2",
                "grade",
                "is_active",
            )
        }),
        ("Weight", {
            "fields": (
                "unit_weight",
                "unit_weight_basis",
            )
        }),
        ("Tax / Optional", {
            "classes": ("collapse",),
            "fields": (
                "hsn_code",
                "tax_rate",
                "group1_name",
                "section_name",
                "import_batch_id",
            )
        }),
        ("Timestamps", {
            "classes": ("collapse",),
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )