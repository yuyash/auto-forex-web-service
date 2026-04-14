"""Add replay markers to positions, orders, and trades."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0039_alter_celerytaskstatus_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="replayed_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="When this position was created or updated by resumed event replay.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="replayed_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="When this order was created or updated by resumed event replay.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="trade",
            name="replayed_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="When this trade was recorded by resumed event replay.",
                null=True,
            ),
        ),
    ]
