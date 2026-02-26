from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0011_relax_orders_direction_nullability"),
    ]

    operations = [
        migrations.AlterField(
            model_name="trade",
            name="direction",
            field=models.CharField(
                blank=True,
                help_text="Trade direction (LONG/SHORT). Null for close-only trades.",
                max_length=10,
                null=True,
            ),
        ),
    ]
