from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0005_stockobject_bin_number_stockobject_rack_number_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stockobject",
            name="qr_code",
            field=models.CharField(
                blank=True,
                max_length=50,
                null=True,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        regex=r"^\d+$",
                        message="QR code must contain digits only.",
                    )
                ],
            ),
        ),
    ]
