from django.http import JsonResponse
from .models import Grade, Item


def api_grades(request):
    group2_id = request.GET.get("group2_id")
    qs = Grade.objects.all()

    if group2_id:
        qs = qs.filter(group2_id=group2_id)

    data = list(qs.values("id", "name").order_by("name"))
    return JsonResponse({"results": data})


def api_items(request):
    group2_id = request.GET.get("group2_id")
    grade_id = request.GET.get("grade_id")

    qs = Item.objects.filter(is_active=True)

    if group2_id:
        qs = qs.filter(group2_id=group2_id)

    if grade_id:
        qs = qs.filter(grade_id=grade_id)

    data = list(
        qs.values(
            "id",
            "item_master_id",
            "item_description",
            "unit_weight",
            "section_name",
            "group1_name",
        ).order_by("item_description")
    )

    return JsonResponse({"results": data})