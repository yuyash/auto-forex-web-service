"""Change broker_order_id from CharField(255) to TextField to handle long OANDA order IDs."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0020_add_planned_exit_price_formula_to_position"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="broker_order_id",
            field=models.TextField(
                null=True,
                blank=True,
                db_index=True,
                help_text="Order ID from the broker (OANDA)",
            ),
        ),
    ]
