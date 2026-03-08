from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procurement', '0003_alter_bomheader_options_alter_bommark_options_and_more'),
    ]

    operations = [
        
        migrations.AddField(
            model_name='bomcomponent',
            name='grade_raw',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='bomcomponent',
            name='item_part_quantity',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='bomcomponent',
            name='width_mm',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='bomcomponent',
            name='length_mm',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='bomcomponent',
            name='line_weight_kg',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True),
        ),
    ]