from django.http import JsonResponse
from .models import Group2, Grade, Item

def api_group2(request):
    data = list(
        Group2.objects.order_by("name").values("id", "code", "name")
    )
    return JsonResponse(data, safe=False)

def api_grades(request):
    group2_id = request.GET.get("group2")
    qs = Grade.objects.all()
    if group2_id:
        qs = qs.filter(group2_id=group2_id)
    data = list(qs.order_by("name").values("id", "code", "name", "group2_id"))
    return JsonResponse(data, safe=False)

def api_items(request):
    group2_id = request.GET.get("group2")
    grade_id = request.GET.get("grade")

    qs = Item.objects.select_related("group2", "grade").all()
    if group2_id:
        qs = qs.filter(group2_id=group2_id)
    if grade_id:
        qs = qs.filter(grade_id=grade_id)

    data = list(
        qs.order_by("item_description").values(
            "id",
            "item_master_id",
            "item_description",
            "unit_weight",
            "group2_id",
            "grade_id",
        )
    )
    return JsonResponse(data, safe=False)