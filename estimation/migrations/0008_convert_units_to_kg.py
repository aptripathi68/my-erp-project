from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


THOUSAND = Decimal("1000")
THREE = Decimal("0.001")
TWO = Decimal("0.01")


def _q3(value):
    return (value or Decimal("0")).quantize(THREE, rounding=ROUND_HALF_UP)


def _q2(value):
    return (value or Decimal("0")).quantize(TWO, rounding=ROUND_HALF_UP)


def convert_to_kg(apps, schema_editor):
    EstimateProject = apps.get_model("estimation", "EstimateProject")
    EstimateRawMaterialLine = apps.get_model("estimation", "EstimateRawMaterialLine")
    EstimateRawMaterialRate = apps.get_model("estimation", "EstimateRawMaterialRate")
    EstimateCostHead = apps.get_model("estimation", "EstimateCostHead")

    for project in EstimateProject.objects.all():
        project.quantity_mt = _q3(Decimal(project.quantity_mt or 0) * THOUSAND)
        project.quotation_price_per_mt = _q2(Decimal(project.quotation_price_per_mt or 0) / THOUSAND)
        project.quoted_price_per_mt = _q2(Decimal(project.quoted_price_per_mt or 0) / THOUSAND)
        project.approved_price_per_mt = _q2(Decimal(project.approved_price_per_mt or 0) / THOUSAND)
        project.save(
            update_fields=[
                "quantity_mt",
                "quotation_price_per_mt",
                "quoted_price_per_mt",
                "approved_price_per_mt",
                "updated_at",
            ]
        )

    for line in EstimateRawMaterialLine.objects.all():
        line.finished_weight_mt = _q3(Decimal(line.finished_weight_mt or 0) * THOUSAND)
        line.quantity_mt = _q3(Decimal(line.quantity_mt or 0) * THOUSAND)
        line.final_rate_per_mt = _q3(Decimal(line.final_rate_per_mt or 0) / THOUSAND)
        line.lowest_rate_per_mt = _q3(Decimal(line.lowest_rate_per_mt or 0) / THOUSAND)
        line.save(
            update_fields=[
                "finished_weight_mt",
                "quantity_mt",
                "final_rate_per_mt",
                "lowest_rate_per_mt",
            ]
        )

    for rate in EstimateRawMaterialRate.objects.exclude(rate_per_mt__isnull=True):
        rate.rate_per_mt = _q3(Decimal(rate.rate_per_mt or 0) / THOUSAND)
        rate.save(update_fields=["rate_per_mt"])

    paint_codes = {"PRIMER", "MIO", "FINISH_PAINT", "THINNER"}
    for head in EstimateCostHead.objects.filter(code__in=paint_codes):
        if head.percentage is not None:
            head.percentage = _q3(Decimal(head.percentage) / THOUSAND)
        if head.remarks:
            head.remarks = head.remarks.replace("LTR/MT", "LTR/Kg")
        head.save(update_fields=["percentage", "remarks"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("estimation", "0007_estimaterawmaterialline_finished_weight_mt"),
    ]

    operations = [
        migrations.RunPython(convert_to_kg, noop_reverse),
    ]
