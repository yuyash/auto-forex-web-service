"""Remove legacy Strategy/StrategyState models.

User-requested cleanup: drop the legacy Strategy model and all FK references,
plus StrategyState which depended on Strategy.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0029_rename_trading_celery_tasks_table"),
    ]

    operations = [
        migrations.DeleteModel(
            name="StrategyState",
        ),
        migrations.RemoveField(
            model_name="position",
            name="strategy",
        ),
        migrations.RemoveField(
            model_name="order",
            name="strategy",
        ),
        migrations.RemoveField(
            model_name="trade",
            name="strategy",
        ),
        migrations.DeleteModel(
            name="Strategy",
        ),
    ]
