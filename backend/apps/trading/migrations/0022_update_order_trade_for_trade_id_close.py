"""Update Order and Trade models for trade ID-based close.

- Add oanda_trade_id to Order and Trade models
- Remove take_profit from Order model
- Make direction nullable on Order and Trade models
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0021_add_oanda_trade_id_to_position"),
    ]

    operations = [
        # Order model changes
        migrations.AddField(
            model_name="order",
            name="oanda_trade_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="OANDA trade ID associated with this order",
                max_length=64,
                null=True,
            ),
        ),
        migrations.RemoveField(
            model_name="order",
            name="take_profit",
        ),
        migrations.AlterField(
            model_name="order",
            name="direction",
            field=models.CharField(
                blank=True,
                choices=[("LONG", "Long"), ("SHORT", "Short")],
                help_text="Order direction (LONG/SHORT). Null for trade-close orders (e.g. take profit).",
                max_length=10,
                null=True,
            ),
        ),
        # Trade model changes
        migrations.AddField(
            model_name="trade",
            name="oanda_trade_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="OANDA trade ID associated with this trade",
                max_length=64,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="trade",
            name="direction",
            field=models.CharField(
                blank=True,
                help_text="Trade direction (LONG/SHORT). Null for close-only trades (e.g. take profit).",
                max_length=10,
                null=True,
            ),
        ),
    ]
