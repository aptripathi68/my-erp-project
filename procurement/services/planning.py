from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

from django.db import transaction
from django.db.models import Sum

from ledger.models import StockLedgerEntry
from procurement.models import BOMComponent, BOMHeader, FabricationJob, FabricationJobComponent


ZERO = Decimal("0.000")


def _wo_prefix(bom: BOMHeader) -> str:
    raw = (bom.purchase_order_no or bom.bom_name or f"BOM-{bom.id}").strip()
    return raw.replace(" ", "-")[:70]


def _erc_quantity_to_count(value) -> int:
    qty = Decimal(value or "0")
    if qty <= 0:
        return 0
    return int(qty.to_integral_value(rounding=ROUND_CEILING))


def generate_int_erc_jobs(bom: BOMHeader) -> dict:
    """
    Generate one execution unit per ERC quantity.
    Existing FabricationJob rows are reused so repeated clicks are idempotent.
    """
    created_jobs = 0
    created_components = 0
    prefix = _wo_prefix(bom)

    with transaction.atomic():
        for mark in bom.marks.prefetch_related("components").all():
            unit_count = _erc_quantity_to_count(mark.erc_quantity)
            if unit_count <= 0:
                continue

            for sequence in range(1, unit_count + 1):
                job_mark = f"{prefix}-{mark.erc_mark}/{sequence}"[:120]
                job, was_created = FabricationJob.objects.get_or_create(
                    bom_mark=mark,
                    job_sequence=sequence,
                    defaults={"job_mark": job_mark},
                )
                if was_created:
                    created_jobs += 1

                existing_component_count = job.components.count()
                if existing_component_count:
                    continue

                components = [
                    FabricationJobComponent(
                        fabrication_job=job,
                        part_mark=component.part_mark,
                        section_name=component.section_name,
                        grade_name=component.grade_name,
                        part_quantity=component.part_quantity_per_assy,
                        length_mm=component.length_mm,
                        width_mm=component.width_mm,
                        engg_weight_kg=component.engg_weight_kg,
                        item=component.item,
                    )
                    for component in mark.components.all()
                ]
                FabricationJobComponent.objects.bulk_create(components, batch_size=1000)
                created_components += len(components)

    return {
        "created_jobs": created_jobs,
        "created_components": created_components,
    }


def bom_material_evaluation(bom: BOMHeader) -> dict:
    requirements = {}

    component_rows = (
        BOMComponent.objects.filter(bom_mark__bom=bom, item__isnull=False)
        .select_related("item", "bom_mark")
        .order_by("item__item_description")
    )
    for component in component_rows:
        item = component.item
        erc_qty = Decimal(component.bom_mark.erc_quantity or "0")
        part_qty = Decimal(component.part_quantity_per_assy or "0")
        line_weight = Decimal(component.engg_weight_kg or "0")

        row = requirements.setdefault(
            item.id,
            {
                "item_id": item.id,
                "item_description": item.item_description,
                "required_qty": ZERO,
                "required_weight": ZERO,
                "available_qty": ZERO,
                "available_weight": ZERO,
                "shortage_qty": ZERO,
                "shortage_weight": ZERO,
                "covered": False,
            },
        )
        row["required_qty"] += part_qty * erc_qty
        row["required_weight"] += line_weight * erc_qty

    stock_rows = (
        StockLedgerEntry.objects.filter(
            location__location_type="STORE",
            location__is_active=True,
            item_id__in=requirements.keys(),
        )
        .values("item_id")
        .annotate(qty=Sum("qty"), weight=Sum("weight"))
    )
    for stock in stock_rows:
        row = requirements.get(stock["item_id"])
        if not row:
            continue
        row["available_qty"] = stock["qty"] or ZERO
        row["available_weight"] = stock["weight"] or ZERO

    rows = []
    total_required_weight = ZERO
    total_available_weight = ZERO
    total_shortage_weight = ZERO
    for row in requirements.values():
        row["shortage_qty"] = max(row["required_qty"] - row["available_qty"], ZERO)
        row["shortage_weight"] = max(row["required_weight"] - row["available_weight"], ZERO)
        row["covered"] = row["shortage_qty"] <= ZERO and row["shortage_weight"] <= ZERO
        total_required_weight += row["required_weight"]
        total_available_weight += row["available_weight"]
        total_shortage_weight += row["shortage_weight"]
        rows.append(row)

    rows.sort(key=lambda item: item["item_description"])
    covered_rows = sum(1 for row in rows if row["covered"])

    return {
        "rows": rows,
        "total_items": len(rows),
        "covered_items": covered_rows,
        "shortage_items": len(rows) - covered_rows,
        "total_required_weight": total_required_weight,
        "total_available_weight": total_available_weight,
        "total_shortage_weight": total_shortage_weight,
        "fully_covered": bool(rows) and covered_rows == len(rows),
    }


def bom_planning_summary():
    summaries = []
    for bom in BOMHeader.objects.prefetch_related("marks__fabrication_jobs").order_by("-uploaded_at"):
        marks = list(bom.marks.all())
        job_count = sum(mark.fabrication_jobs.count() for mark in marks)
        expected_jobs = sum(_erc_quantity_to_count(mark.erc_quantity) for mark in marks)
        evaluation = bom_material_evaluation(bom)
        summaries.append(
            {
                "bom": bom,
                "mark_count": len(marks),
                "expected_jobs": expected_jobs,
                "job_count": job_count,
                "shortage_items": evaluation["shortage_items"],
                "fully_covered": evaluation["fully_covered"],
            }
        )
    return summaries
