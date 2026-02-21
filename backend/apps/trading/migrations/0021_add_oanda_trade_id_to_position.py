"""Add oanda_trade_id field to Position model."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0020_change_trading_mode_default_to_hedging"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="oanda_trade_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="OANDA trade ID for trade-based close operations",
                max_length=64,
                null=True,
            ),
        ),
    ]
