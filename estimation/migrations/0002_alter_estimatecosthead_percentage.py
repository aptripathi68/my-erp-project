from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("estimation", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="estimatecosthead",
            name="percentage",
            field=models.DecimalField(blank=True, decimal_places=5, max_digits=10, null=True),
        ),
    ]
