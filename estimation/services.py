from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import (
    EstimateBudgetHead,
    EstimateCostHead,
    EstimateExpense,
    EstimateProject,
    EstimateRawMaterialLine,
    EstimateRawMaterialRate,
    EstimateSupplier,
)


ZERO = Decimal("0")
TWOPLACES = Decimal("0.01")
FOURPLACES = Decimal("0.0001")


COST_HEAD_DEFAULTS = [
    {"code": "RAW_MATERIAL_COST", "name": "Raw Material Cost", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": "Including Transport"},
    {"code": "INWARD_TRANSPORTATION", "name": "Inward Transportation", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": ""},
    {"code": "SCRAP_BURNING", "name": "Scrap Burning", "percentage": Decimal("-0.03888"), "rate_per_kg": Decimal("28"), "remarks": ""},
    {"code": "OFFCUT_RECOVERY", "name": "Offcut Recovery", "percentage": Decimal("-0.05830"), "rate_per_kg": Decimal("35"), "remarks": ""},
    {"code": "RAW_MATERIAL_UNLOADING", "name": "Raw Material Unloading at Shop", "percentage": Decimal("1"), "rate_per_kg": Decimal("0.161"), "remarks": ""},
    {"code": "TOTAL_RM_COST", "name": "Total RM Cost", "line_type": EstimateCostHead.LineType.TOTAL, "remarks": "Including Material Interest"},
    {"code": "FABRICATION", "name": "Fabrication (Labour & Consumable)", "percentage": Decimal("1"), "rate_per_kg": Decimal("11"), "remarks": "Bought-Outs Excluded"},
    {"code": "BENDING", "name": "Bending", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": ""},
    {"code": "JIGG_FIXTURE", "name": "Jigg & Fixture Cost", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": ""},
    {"code": "ASSEMBLY", "name": "Assembly", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": ""},
    {"code": "NDT_INSPECTION", "name": "NDT (Inspection)", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": ""},
    {"code": "INSPECTION", "name": "Inspection", "percentage": Decimal("1"), "rate_per_kg": Decimal("0.15"), "remarks": ""},
    {"code": "PAINT_PROCUREMENT", "name": "Paint Procurement", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": "130 Micron painted"},
    {"code": "PRIMER", "name": "PRIMER (Inorganic ethyl zinc silicate)", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": "@6 LTR/MT"},
    {"code": "MIO", "name": "MIO (Epoxypolyamide MIO)", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": "@6 LTR/MT"},
    {"code": "FINISH_PAINT", "name": "FINISH PAINT (Aliphatic polyurethane)", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": "@6 LTR/MT"},
    {"code": "THINNER", "name": "THINNER", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": ""},
    {"code": "BLASTING_PAINT_APPLICATION", "name": "Blasting & Paint Application", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": ""},
    {"code": "PAINT_TESTING", "name": "Paint Testing", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": ""},
    {"code": "LOADING_DISPATCH", "name": "Loading for Dispatch", "percentage": Decimal("1"), "rate_per_kg": Decimal("0.2"), "remarks": ""},
    {"code": "PACKING", "name": "Packing", "percentage": Decimal("1"), "rate_per_kg": Decimal("0.15"), "remarks": ""},
    {"code": "TRANSPORTATION", "name": "Transportation", "percentage": Decimal("1"), "rate_per_kg": Decimal("0"), "remarks": "Ex-Works"},
    {"code": "TOTAL_CONVERSION_COST", "name": "Total Conversion Cost", "line_type": EstimateCostHead.LineType.TOTAL, "remarks": ""},
    {"code": "ELECTRICITY", "name": "Electricity", "percentage": Decimal("1"), "rate_per_kg": Decimal("0.95"), "remarks": "200 MT PER MONTH"},
    {"code": "PLANT_OVERHEAD_FE", "name": "Plant Over Head/FE", "percentage": Decimal("1"), "rate_per_kg": Decimal("4.22"), "remarks": "200 MT PER MONTH"},
    {"code": "TOTAL_ESTIMATED_COST", "name": "Total Estimated Cost", "line_type": EstimateCostHead.LineType.TOTAL, "remarks": ""},
    {"code": "BANK_INTEREST", "name": "Bank Interest", "percentage": Decimal("1"), "rate_per_kg": Decimal("1.01"), "remarks": ""},
    {"code": "MARGIN", "name": "Margin @ 8%", "percentage": Decimal("1"), "rate_per_kg": Decimal("6.93"), "remarks": ""},
    {"code": "QUOTATION_PRICE", "name": "Quotation Price/MT (Round-Off)", "line_type": EstimateCostHead.LineType.TOTAL, "remarks": ""},
]


ENTRY_COST_CODES = [
    "RAW_MATERIAL_COST",
    "INWARD_TRANSPORTATION",
    "SCRAP_BURNING",
    "OFFCUT_RECOVERY",
    "RAW_MATERIAL_UNLOADING",
    "FABRICATION",
    "BENDING",
    "JIGG_FIXTURE",
    "ASSEMBLY",
    "NDT_INSPECTION",
    "INSPECTION",
    "PAINT_PROCUREMENT",
    "PRIMER",
    "MIO",
    "FINISH_PAINT",
    "THINNER",
    "BLASTING_PAINT_APPLICATION",
    "PAINT_TESTING",
    "LOADING_DISPATCH",
    "PACKING",
    "TRANSPORTATION",
    "ELECTRICITY",
    "PLANT_OVERHEAD_FE",
    "BANK_INTEREST",
    "MARGIN",
]


def quantize2(value: Decimal) -> Decimal:
    return (value or ZERO).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def quantize4(value: Decimal) -> Decimal:
    return (value or ZERO).quantize(FOURPLACES, rounding=ROUND_HALF_UP)


def ensure_project_cost_heads(project: EstimateProject) -> None:
    if EstimateCostHead.objects.filter(project=project).exists():
        return

    for index, cfg in enumerate(COST_HEAD_DEFAULTS, start=1):
        EstimateCostHead.objects.create(
            project=project,
            code=cfg["code"],
            name=cfg["name"],
            line_type=cfg.get("line_type", EstimateCostHead.LineType.ENTRY),
            percentage=cfg.get("percentage"),
            rate_per_kg=cfg.get("rate_per_kg", ZERO),
            remarks=cfg.get("remarks", ""),
            sort_order=index,
            is_percentage_editable=cfg.get("line_type") != EstimateCostHead.LineType.TOTAL,
            is_rate_editable=cfg.get("line_type") != EstimateCostHead.LineType.TOTAL,
        )


def sync_project_supplier_rates(project: EstimateProject) -> None:
    suppliers = [ps.supplier for ps in project.project_suppliers.select_related("supplier")]
    lines = list(project.raw_material_lines.all())
    for line in lines:
        existing = {rate.supplier_id for rate in line.supplier_rates.all()}
        for supplier in suppliers:
            if supplier.id not in existing:
                EstimateRawMaterialRate.objects.create(line=line, supplier=supplier)
        line.recalculate_from_rates(save=True)


def update_material_totals(project: EstimateProject) -> None:
    total_amount = ZERO
    total_qty_mt = ZERO
    for line in project.raw_material_lines.prefetch_related("supplier_rates"):
        line.recalculate_from_rates(save=True)
        total_amount += line.total_amount or ZERO
        total_qty_mt += line.quantity_mt or ZERO

    raw_cost_per_kg = ZERO
    if total_qty_mt:
        raw_cost_per_kg = total_amount / (total_qty_mt * Decimal("1000"))

    if total_qty_mt:
        project.quantity_mt = quantize2(total_qty_mt)
    project.raw_material_cost_per_kg = quantize2(raw_cost_per_kg)
    project.save(update_fields=["quantity_mt", "raw_material_cost_per_kg", "updated_at"])


def recalculate_cost_heads(project: EstimateProject) -> None:
    ensure_project_cost_heads(project)
    update_material_totals(project)

    cost_heads = {head.code: head for head in EstimateCostHead.objects.filter(project=project)}
    quantity_kg = project.quantity_kg or ZERO

    raw_cost = cost_heads["RAW_MATERIAL_COST"]
    raw_cost.rate_per_kg = project.raw_material_cost_per_kg
    raw_cost.amount = quantize2(quantity_kg * (raw_cost.percentage or ZERO) * (raw_cost.rate_per_kg or ZERO))
    raw_cost.save(update_fields=["rate_per_kg", "amount"])

    for code in ENTRY_COST_CODES:
        if code == "RAW_MATERIAL_COST":
            continue
        head = cost_heads[code]
        percentage = head.percentage if head.percentage is not None else Decimal("1")
        rate_per_kg = head.rate_per_kg or ZERO
        head.amount = quantize2(quantity_kg * percentage * rate_per_kg)
        head.save(update_fields=["amount"])

    total_rm = sum((cost_heads[code].amount or ZERO) for code in [
        "RAW_MATERIAL_COST",
        "INWARD_TRANSPORTATION",
        "SCRAP_BURNING",
        "OFFCUT_RECOVERY",
        "RAW_MATERIAL_UNLOADING",
    ])
    cost_heads["TOTAL_RM_COST"].rate_per_kg = quantize4(total_rm / quantity_kg) if quantity_kg else ZERO
    cost_heads["TOTAL_RM_COST"].amount = quantize2(total_rm)
    cost_heads["TOTAL_RM_COST"].save(update_fields=["rate_per_kg", "amount"])

    total_conversion = sum((cost_heads[code].amount or ZERO) for code in [
        "TOTAL_RM_COST",
        "FABRICATION",
        "BENDING",
        "JIGG_FIXTURE",
        "ASSEMBLY",
        "NDT_INSPECTION",
        "INSPECTION",
        "PAINT_PROCUREMENT",
        "PRIMER",
        "MIO",
        "FINISH_PAINT",
        "THINNER",
        "BLASTING_PAINT_APPLICATION",
        "PAINT_TESTING",
        "LOADING_DISPATCH",
        "PACKING",
        "TRANSPORTATION",
    ])
    cost_heads["TOTAL_CONVERSION_COST"].rate_per_kg = quantize4(total_conversion / quantity_kg) if quantity_kg else ZERO
    cost_heads["TOTAL_CONVERSION_COST"].amount = quantize2(total_conversion)
    cost_heads["TOTAL_CONVERSION_COST"].save(update_fields=["rate_per_kg", "amount"])

    total_estimated = sum((cost_heads[code].amount or ZERO) for code in [
        "TOTAL_CONVERSION_COST",
        "ELECTRICITY",
        "PLANT_OVERHEAD_FE",
    ])
    cost_heads["TOTAL_ESTIMATED_COST"].rate_per_kg = quantize4(total_estimated / quantity_kg) if quantity_kg else ZERO
    cost_heads["TOTAL_ESTIMATED_COST"].amount = quantize2(total_estimated)
    cost_heads["TOTAL_ESTIMATED_COST"].save(update_fields=["rate_per_kg", "amount"])

    quotation_total = sum((cost_heads[code].amount or ZERO) for code in [
        "TOTAL_ESTIMATED_COST",
        "BANK_INTEREST",
        "MARGIN",
    ])
    quotation_rate_per_kg = quantize4(quotation_total / quantity_kg) if quantity_kg else ZERO
    cost_heads["QUOTATION_PRICE"].rate_per_kg = quotation_rate_per_kg
    cost_heads["QUOTATION_PRICE"].amount = quantize2(quotation_total)
    cost_heads["QUOTATION_PRICE"].save(update_fields=["rate_per_kg", "amount"])

    project.total_estimated_cost_per_kg = quantize2(cost_heads["TOTAL_ESTIMATED_COST"].rate_per_kg)
    project.quotation_price_per_kg = quantize2(quotation_rate_per_kg)
    project.quotation_price_per_mt = quantize2(quotation_rate_per_kg * Decimal("1000"))
    project.quotation_value = quantize2(quotation_total)
    project.save(
        update_fields=[
            "total_estimated_cost_per_kg",
            "quotation_price_per_kg",
            "quotation_price_per_mt",
            "quotation_value",
            "updated_at",
        ]
    )


def create_default_suppliers_if_missing() -> None:
    if EstimateSupplier.objects.exists():
        return
    for name in ["Supplier 1", "Supplier 2", "Supplier 3"]:
        EstimateSupplier.objects.create(name=name)


def generate_budget_heads(project: EstimateProject) -> None:
    project.budget_heads.all().delete()
    cost_heads = project.cost_heads.exclude(line_type=EstimateCostHead.LineType.TOTAL).order_by("sort_order")
    for head in cost_heads:
        EstimateBudgetHead.objects.create(
            project=project,
            cost_head=head,
            name=head.name,
            budget_amount=head.amount or ZERO,
        )


def refresh_budget_totals(project: EstimateProject) -> None:
    for budget in project.budget_heads.prefetch_related("expenses"):
        spent = ZERO
        approved = ZERO
        for expense in budget.expenses.all():
            spent += expense.amount or ZERO
            if expense.status == EstimateExpense.Status.APPROVED:
                approved += expense.amount or ZERO
        budget.spent_amount = quantize2(spent)
        budget.approved_amount = quantize2(approved)
        budget.save(update_fields=["spent_amount", "approved_amount"])
