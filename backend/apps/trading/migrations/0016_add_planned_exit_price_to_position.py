"""Add planned_exit_price field to Position model."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0015_add_layer_retracement_to_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="planned_exit_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=10,
                help_text="Planned exit price calculated at order time (e.g. take-profit target)",
                max_digits=20,
                null=True,
            ),
        ),
    ]
