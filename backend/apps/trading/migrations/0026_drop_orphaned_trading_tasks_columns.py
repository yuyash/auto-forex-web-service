"""Drop orphaned columns from trading_tasks table.

The columns retry_count, max_retries, result_data, and
result_data_external_ref exist in the database but are not defined
in the TradingTask model. retry_count has a NOT NULL constraint
that causes inserts to fail.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0025_drop_floor_strategy_task_states"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE trading_tasks DROP COLUMN IF EXISTS retry_count;",
                "ALTER TABLE trading_tasks DROP COLUMN IF EXISTS max_retries;",
                "ALTER TABLE trading_tasks DROP COLUMN IF EXISTS result_data;",
                "ALTER TABLE trading_tasks DROP COLUMN IF EXISTS result_data_external_ref;",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
