"""Add created_at and updated_at to Trade model."""

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0018_remove_position_realized_pnl"),
    ]

    operations = [
        migrations.AddField(
            model_name="trade",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                help_text="Timestamp when this record was created",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="trade",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                help_text="Timestamp when this record was last updated",
            ),
        ),
    ]
