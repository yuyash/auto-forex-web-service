"""Remove close_price and close_timestamp fields from Trade model.

Trades are append-only event records. Position open/close status is
tracked in the positions table instead.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0012_add_celery_task_id_to_position"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="trade",
            name="close_price",
        ),
        migrations.RemoveField(
            model_name="trade",
            name="close_timestamp",
        ),
    ]
