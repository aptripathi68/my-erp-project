from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q

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
    group2_id = request.GET.get("group2")
    grade_id = request.GET.get("grade")

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


@login_required
def item_master_list(request):
    q = (request.GET.get("q") or "").strip()

    items = Item.objects.select_related("group2", "grade").all()

    if q:
        items = items.filter(
            Q(item_master_id__icontains=q) |
            Q(section_name__icontains=q) |
            Q(item_description__icontains=q)
        )

    items = items.order_by("item_master_id")

    context = {
        "items": items,
        "q": q,
    }
    return render(request, "masters/item_master_list.html", context)


@login_required
def item_master_add(request):
    group2_list = Group2.objects.order_by("name")
    grade_list = Grade.objects.select_related("group2").order_by("name")

    if request.method == "POST":
        item_master_id = (request.POST.get("item_master_id") or "").strip()
        section_name = (request.POST.get("section_name") or "").strip()
        item_description = (request.POST.get("item_description") or "").strip()
        group2_id = request.POST.get("group2")
        grade_id = request.POST.get("grade")
        unit_weight = request.POST.get("unit_weight")
        unit_weight_basis = request.POST.get("unit_weight_basis")
        is_active = request.POST.get("is_active") == "on"

        errors = []

        if not item_master_id:
            errors.append("Item Master ID is required.")
        if not section_name:
            errors.append("Section Name is required.")
        if not item_description:
            errors.append("Item Description is required.")
        if not group2_id:
            errors.append("Group2 is required.")
        if not grade_id:
            errors.append("Grade is required.")
        if not unit_weight:
            errors.append("Unit Weight is required.")
        if not unit_weight_basis:
            errors.append("Unit Weight Basis is required.")

        if Item.objects.filter(item_master_id=item_master_id).exists():
            errors.append("Item Master ID already exists.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            try:
                Item.objects.create(
                    item_master_id=item_master_id,
                    section_name=section_name,
                    item_description=item_description,
                    group2_id=group2_id,
                    grade_id=grade_id,
                    unit_weight=unit_weight,
                    unit_weight_basis=unit_weight_basis,
                    is_active=is_active,
                )
                messages.success(request, "New item added successfully.")
                return redirect("item_master_list")
            except Exception as e:
                messages.error(request, f"Unable to save item: {e}")

    context = {
        "group2_list": group2_list,
        "grade_list": grade_list,
        "unit_weight_basis_choices": Item.UnitWeightBasis.choices,
    }
    return render(request, "masters/item_master_form.html", context)
@login_required
def item_master_edit(request, item_id):
    item = get_object_or_404(
        Item.objects.select_related("group2", "grade"),
        id=item_id
    )

    group2_list = Group2.objects.order_by("name")
    grade_list = Grade.objects.select_related("group2").order_by("name")

    if request.method == "POST":
        item_master_id = (request.POST.get("item_master_id") or "").strip()
        section_name = (request.POST.get("section_name") or "").strip()
        item_description = (request.POST.get("item_description") or "").strip()
        group2_id = request.POST.get("group2")
        grade_id = request.POST.get("grade")
        unit_weight = request.POST.get("unit_weight")
        unit_weight_basis = request.POST.get("unit_weight_basis")
        is_active = request.POST.get("is_active") == "on"

        errors = []

        if not item_master_id:
            errors.append("Item Master ID is required.")
        if not section_name:
            errors.append("Section Name is required.")
        if not item_description:
            errors.append("Item Description is required.")
        if not group2_id:
            errors.append("Group2 is required.")
        if not grade_id:
            errors.append("Grade is required.")
        if not unit_weight:
            errors.append("Unit Weight is required.")
        if not unit_weight_basis:
            errors.append("Unit Weight Basis is required.")

        if Item.objects.exclude(id=item.id).filter(item_master_id=item_master_id).exists():
            errors.append("Item Master ID already exists for another item.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            try:
                item.item_master_id = item_master_id
                item.section_name = section_name
                item.item_description = item_description
                item.group2_id = group2_id
                item.grade_id = grade_id
                item.unit_weight = unit_weight
                item.unit_weight_basis = unit_weight_basis
                item.is_active = is_active
                item.save()

                messages.success(request, "Item updated successfully.")
                return redirect("item_master_list")
            except Exception as e:
                messages.error(request, f"Unable to update item: {e}")

    context = {
        "item": item,
        "group2_list": group2_list,
        "grade_list": grade_list,
        "unit_weight_basis_choices": Item.UnitWeightBasis.choices,
    }

    return render(request, "masters/item_master_edit_form.html", context)