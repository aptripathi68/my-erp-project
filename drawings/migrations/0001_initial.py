from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('procurement', '0006_fabricationjob_fabricationjobcomponent_and_more'),
    ]

    operations = [

        migrations.CreateModel(
            name='Drawing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('drawing_no', models.CharField(max_length=100)),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'drawings_drawing',
                'ordering': ['drawing_no'],
                'unique_together': {('drawing_no',)},
            },
        ),

        migrations.AddIndex(
            model_name='drawing',
            index=models.Index(fields=['drawing_no'], name='drawings_dr_drawing_idx'),
        ),

        migrations.CreateModel(
            name='DrawingSheet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sheet_no', models.IntegerField()),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
                ('drawing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sheets', to='drawings.drawing')),
            ],
            options={
                'db_table': 'drawings_sheet',
                'ordering': ['drawing', 'sheet_no'],
                'unique_together': {('drawing', 'sheet_no')},
            },
        ),

        migrations.AddIndex(
            model_name='drawingsheet',
            index=models.Index(fields=['sheet_no'], name='drawings_dr_sheet_idx'),
        ),

        migrations.CreateModel(
            name='DrawingSheetRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision_no', models.CharField(max_length=20)),
                ('file_path', models.CharField(max_length=500)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('is_current', models.BooleanField(default=True)),
                ('sheet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='drawings.drawingsheet')),
            ],
            options={
                'db_table': 'drawings_sheet_revision',
                'ordering': ['sheet', '-revision_no'],
                'unique_together': {('sheet', 'revision_no')},
            },
        ),

        migrations.AddIndex(
            model_name='drawingsheetrevision',
            index=models.Index(fields=['revision_no'], name='drawings_dr_revision_idx'),
        ),

        migrations.AddIndex(
            model_name='drawingsheetrevision',
            index=models.Index(fields=['is_current'], name='drawings_dr_current_idx'),
        ),

    ]