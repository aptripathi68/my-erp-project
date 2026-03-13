from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("procurement", "0008_add_drawing_link_to_bommark"),
    ]

    operations = [
        migrations.AddField(
            model_name="bommark",
            name="production_status",
            field=models.CharField(
                max_length=40,
                choices=[
                    ("PLANNING_PENDING", "Planning Pending"),
                    ("RELEASED_TO_PRODUCTION", "Released to Production"),
                    ("IN_FABRICATION", "In Fabrication"),
                    ("FABRICATION_DONE", "Fabrication Done"),
                    ("IN_PAINTING", "In Painting"),
                    ("PAINTING_DONE", "Painting Done"),
                    ("DISPATCH_READY", "Dispatch Ready"),
                    ("DISPATCHED", "Dispatched"),
                ],
                default="PLANNING_PENDING",
            ),
        ),
    ]