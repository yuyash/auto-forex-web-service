"""Add planned_exit_price_formula field to Position model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0019_remove_executionstate_unique_task_run_execution_state_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="planned_exit_price_formula",
            field=models.CharField(
                blank=True,
                help_text="Human-readable formula used to calculate planned_exit_price (e.g. '1.12345 + 0.00500')",
                max_length=255,
                null=True,
            ),
        ),
    ]
