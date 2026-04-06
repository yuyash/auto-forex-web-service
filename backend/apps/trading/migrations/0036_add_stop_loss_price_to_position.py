"""Add stop_loss_price and is_rebuild fields to Position and Trade models."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0035_alter_position_layer_index_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="stop_loss_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=10,
                help_text="Stop-loss price calculated at entry time. Position is closed if market reaches this price.",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="position",
            name="is_rebuild",
            field=models.BooleanField(
                default=False,
                help_text="Whether this position was rebuilt after a stop-loss close.",
            ),
        ),
        migrations.AddField(
            model_name="trade",
            name="is_rebuild",
            field=models.BooleanField(
                default=False,
                help_text="Whether this trade is for a position rebuilt after a stop-loss close.",
            ),
        ),
    ]
