from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("estimation", "0006_alter_rate_precision"),
    ]

    operations = [
        migrations.AddField(
            model_name="estimaterawmaterialline",
            name="finished_weight_mt",
            field=models.DecimalField(decimal_places=6, default=0, max_digits=15),
        ),
    ]
