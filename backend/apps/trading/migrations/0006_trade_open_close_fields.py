"""Add open/close price and timestamp fields to Trade model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0005_remove_backtest_orphaned_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="trade",
            name="open_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=10,
                help_text="Entry price when position was opened (populated on close trades)",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="trade",
            name="open_timestamp",
            field=models.DateTimeField(
                blank=True,
                help_text="When the position was originally opened (populated on close trades)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="trade",
            name="close_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=10,
                help_text="Exit price when position was closed (populated on close trades)",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="trade",
            name="close_timestamp",
            field=models.DateTimeField(
                blank=True,
                help_text="When the position was closed (populated on close trades)",
                null=True,
            ),
        ),
    ]
