# Generated migration for adding strategy_events field to Backtest model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0018_add_execution_logs"),
    ]

    operations = [
        migrations.AddField(
            model_name="backtest",
            name="strategy_events",
            field=models.JSONField(
                default=list,
                help_text="Strategy events log (for floor strategy markers and debugging)",
            ),
        ),
    ]
