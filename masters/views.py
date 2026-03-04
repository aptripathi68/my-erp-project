from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Group2, Grade, Item


@require_GET
def api_group2(request):
    data = list(
        Group2.objects.order_by("name").values("id", "code", "name")
    )
    return JsonResponse(data, safe=False)


@require_GET
def api_grades(request):
    group2_id = request.GET.get("group2")

    qs = Grade.objects.all()
    if group2_id:
        qs = qs.filter(group2_id=group2_id)

    data = list(
        qs.order_by("name").values("id", "code", "name", "group2_id")
    )
    return JsonResponse(data, safe=False)


@require_GET
def api_items(request):
    """
    Items endpoint for cascading dropdown.
    Recommended usage:
      /api/items/?group2=<group2_id>&grade=<grade_id>

    Safety: if group2 is missing, return [] instead of ALL items.
    """
    group2_id = request.GET.get("group2")
    grade_id = request.GET.get("grade")

    # Prevent dumping the full item master accidentally
    if not group2_id:
        return JsonResponse([], safe=False)

    qs = Item.objects.filter(group2_id=group2_id)
    if grade_id:
        qs = qs.filter(grade_id=grade_id)

    data = list(
        qs.order_by("item_description").values(
            "id",
            "item_master_id",
            "item_description",
            "group1_name",
            "section_name",
            "unit_weight",
            "group2_id",
            "grade_id",
        )
    )
    return JsonResponse(data, safe=False)