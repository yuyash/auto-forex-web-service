"""Drop legacy floor_strategy_task_states and floor_strategy_layer_states tables.

These tables were replaced by the ExecutionState model and are no longer
referenced by any code. Both are empty.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0024_fix_trading_tasks_id_bigint_to_uuid"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS floor_strategy_layer_states;",
                "DROP TABLE IF EXISTS floor_strategy_task_states;",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
