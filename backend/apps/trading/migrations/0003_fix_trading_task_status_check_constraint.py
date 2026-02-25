from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0002_add_tick_bid_ask_to_execution_state"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="tradingtask",
            name="valid_trading_task_status",
        ),
        migrations.AddConstraint(
            model_name="tradingtask",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "status__in",
                        [
                            "created",
                            "starting",
                            "running",
                            "paused",
                            "stopping",
                            "stopped",
                            "completed",
                            "failed",
                        ],
                    )
                ),
                name="valid_trading_task_status",
            ),
        ),
    ]
