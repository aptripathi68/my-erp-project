from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("procurement", "0009_add_production_status_to_bommark"),
    ]

    operations = [
        migrations.CreateModel(
            name="BOMColumnMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sheet_name", models.CharField(max_length=200)),
                ("header_signature", models.CharField(db_index=True, max_length=1000)),
                ("mapping", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_bom_column_mappings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_bom_column_mappings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
                "unique_together": {("sheet_name", "header_signature")},
            },
        ),
        migrations.AddIndex(
            model_name="bomcolumnmapping",
            index=models.Index(fields=["sheet_name", "header_signature"], name="procurement_b_sheet_n_0a36bc_idx"),
        ),
    ]
