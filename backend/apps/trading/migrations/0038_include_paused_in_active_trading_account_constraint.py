from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0037_add_backtest_tick_replay_settings"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="tradingtask",
            name="uniq_active_trading_task_per_account",
        ),
        migrations.AddConstraint(
            model_name="tradingtask",
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=["starting", "running", "paused", "stopping"]),
                fields=("oanda_account",),
                name="uniq_active_trading_task_per_account",
            ),
        ),
    ]
