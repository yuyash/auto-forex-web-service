# Generated migration for adding strategy_events field to ExecutionMetrics model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0019_add_strategy_events_to_backtest"),
    ]

    operations = [
        migrations.AddField(
            model_name="executionmetrics",
            name="strategy_events",
            field=models.JSONField(
                default=list,
                help_text="Strategy events log (for floor strategy markers and debugging)",
            ),
        ),
    ]
