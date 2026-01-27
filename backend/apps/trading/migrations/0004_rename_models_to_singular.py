# Generated migration for renaming models to singular

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0003_remove_task_metric_model'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='BacktestTasks',
            new_name='BacktestTask',
        ),
        migrations.RenameModel(
            old_name='TradingTasks',
            new_name='TradingTask',
        ),
        migrations.RenameModel(
            old_name='StrategyConfigurations',
            new_name='StrategyConfiguration',
        ),
        migrations.RenameModel(
            old_name='TradingEvents',
            new_name='TradingEvent',
        ),
        migrations.RenameModel(
            old_name='Trades',
            new_name='Trade',
        ),
        migrations.RenameModel(
            old_name='Equities',
            new_name='Equity',
        ),
    ]
