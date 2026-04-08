from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("estimation", "0004_estimatesupplierquotationfile"),
    ]

    operations = [
        migrations.AlterField(
            model_name="estimateproject",
            name="quantity_mt",
            field=models.DecimalField(decimal_places=6, default=0, max_digits=15),
        ),
        migrations.AlterField(
            model_name="estimaterawmaterialline",
            name="quantity_mt",
            field=models.DecimalField(decimal_places=6, default=0, max_digits=15),
        ),
    ]
