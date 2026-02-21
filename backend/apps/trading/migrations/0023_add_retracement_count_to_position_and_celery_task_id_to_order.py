"""Add retracement_count to Position and celery_task_id to Order."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0022_update_order_trade_for_trade_id_close"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="retracement_count",
            field=models.IntegerField(
                blank=True,
                help_text="Number of retracements for this position",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="celery_task_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Celery task ID for tracking which execution run created this order",
                max_length=255,
                null=True,
            ),
        ),
    ]
