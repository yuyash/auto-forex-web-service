# Generated migration for adding external storage reference fields

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0002_refactor_task_execution_architecture"),
    ]

    operations = [
        migrations.AddField(
            model_name="backtesttasks",
            name="result_data_external_ref",
            field=models.CharField(
                blank=True,
                help_text="Reference to externally stored result data (e.g., fs://path or s3://bucket/key)",
                max_length=500,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tradingtasks",
            name="result_data_external_ref",
            field=models.CharField(
                blank=True,
                help_text="Reference to externally stored result data (e.g., fs://path or s3://bucket/key)",
                max_length=500,
                null=True,
            ),
        ),
    ]
