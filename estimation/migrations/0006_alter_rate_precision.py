from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("estimation", "0005_alter_quantity_precision"),
    ]

    operations = [
        migrations.AlterField(
            model_name="estimaterawmaterialline",
            name="final_rate_per_mt",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.AlterField(
            model_name="estimaterawmaterialline",
            name="lowest_rate_per_mt",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.AlterField(
            model_name="estimaterawmaterialrate",
            name="rate_per_mt",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True),
        ),
    ]
