from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

from django.db import transaction

from procurement.models import (
    BOMHeader,
    ERC,
    FabricationJob,
    FabricationJobComponent,
    INTERCUnit,
    RequirementLine,
    WorkOrder,
)


def normalize_wo_number(value: str) -> str:
    return (value or "").strip()


def duplicate_work_order_exists(wo_number: str) -> bool:
    wo_number = normalize_wo_number(wo_number)
    if not wo_number:
        return False

    return (
        WorkOrder.objects.filter(wo_number__iexact=wo_number).exists()
        or BOMHeader.objects.filter(bom_name__iexact=wo_number).exists()
    )


def _wo_prefix(work_order: WorkOrder) -> str:
    return work_order.wo_number.replace(" ", "-")[:70]


def _erc_quantity_to_count(value) -> int:
    qty = Decimal(value or "0")
    if qty <= 0:
        return 0
    return int(qty.to_integral_value(rounding=ROUND_CEILING))


def sync_bom_to_backbone(bom: BOMHeader, *, created_by) -> dict:
    """
    Create the formal Phase 1A backbone from an already imported BOM.
    Existing legacy BOM/FabricationJob records are kept and linked.
    """
    wo_number = normalize_wo_number(bom.bom_name)
    if not wo_number:
        raise ValueError("WO Number is required.")

    with transaction.atomic():
        work_order, _ = WorkOrder.objects.get_or_create(
            wo_number=wo_number,
            defaults={
                "estimate_project": bom.estimate_project,
                "project_name": bom.project_name,
                "client_name": bom.client_name,
                "purchase_order_no": bom.purchase_order_no,
                "purchase_order_date": bom.purchase_order_date,
                "delivery_date": bom.delivery_date,
                "order_rate": bom.order_rate,
                "order_value": bom.order_value,
                "created_by": created_by,
            },
        )

        if not bom.work_order_id:
            bom.work_order = work_order
            bom.save(update_fields=["work_order"])

        created_ercs = 0
        created_units = 0
        created_requirements = 0
        linked_jobs = 0
        prefix = _wo_prefix(work_order)

        for mark in bom.marks.prefetch_related("components").all():
            erc, erc_created = ERC.objects.get_or_create(
                work_order=work_order,
                bom_header=bom,
                sheet_name=mark.sheet_name,
                erc_mark=mark.erc_mark or "",
                drawing_no=mark.drawing_no or "",
                defaults={
                    "erc_quantity": mark.erc_quantity,
                    "drawing": mark.drawing,
                },
            )
            if erc_created:
                created_ercs += 1

            if not mark.erc_id:
                mark.erc = erc
                mark.save(update_fields=["erc"])

            unit_count = _erc_quantity_to_count(erc.erc_quantity)
            for sequence in range(1, unit_count + 1):
                int_code = f"{prefix}-{erc.erc_mark}/{sequence}"[:140]
                int_unit, unit_created = INTERCUnit.objects.get_or_create(
                    erc=erc,
                    sequence=sequence,
                    defaults={
                        "work_order": work_order,
                        "int_erc_code": int_code,
                    },
                )
                if unit_created:
                    created_units += 1

                job, _ = FabricationJob.objects.get_or_create(
                    bom_mark=mark,
                    job_sequence=sequence,
                    defaults={
                        "job_mark": int_code[:120],
                        "int_erc_unit": int_unit,
                    },
                )
                if job.int_erc_unit_id != int_unit.id:
                    job.int_erc_unit = int_unit
                    job.save(update_fields=["int_erc_unit"])
                    linked_jobs += 1

                if not job.components.exists():
                    FabricationJobComponent.objects.bulk_create(
                        [
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
                        ],
                        batch_size=1000,
                    )

                existing_requirement_count = int_unit.requirement_lines.count()
                if existing_requirement_count:
                    continue

                requirements = []
                for component in mark.components.all():
                    if not component.item_id:
                        continue

                    required_qty = component.part_quantity_per_assy or Decimal("0")
                    required_weight = component.engg_weight_kg or Decimal("0")
                    requirements.append(
                        RequirementLine(
                            work_order=work_order,
                            erc=erc,
                            int_erc_unit=int_unit,
                            bom_component=component,
                            item=component.item,
                            item_specification=component.item.item_description,
                            grade_name=component.grade_name,
                            part_mark=component.part_mark,
                            required_qty=required_qty,
                            required_weight_kg=required_weight,
                        )
                    )

                RequirementLine.objects.bulk_create(requirements, batch_size=1000)
                created_requirements += len(requirements)

    return {
        "work_order_id": work_order.id,
        "created_ercs": created_ercs,
        "created_units": created_units,
        "created_requirements": created_requirements,
        "linked_jobs": linked_jobs,
    }
