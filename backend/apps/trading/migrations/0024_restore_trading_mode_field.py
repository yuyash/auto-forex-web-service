from django.db import migrations, models


def restore_trading_mode_column(apps, schema_editor):
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, "trading_tasks"
            )
        }

    if "trading_mode" not in existing_columns:
        schema_editor.execute(
            """
            ALTER TABLE trading_tasks
            ADD COLUMN trading_mode varchar(20) NOT NULL DEFAULT 'netting'
            """
        )
        return

    schema_editor.execute(
        """
        UPDATE trading_tasks
        SET trading_mode = CASE
            WHEN hedging_enabled THEN 'hedging'
            ELSE 'netting'
        END
        WHERE trading_mode IS NULL
        """
    )

    if connection.vendor == "postgresql":
        schema_editor.execute(
            """
            ALTER TABLE trading_tasks
            ALTER COLUMN trading_mode SET DEFAULT 'netting'
            """
        )
        schema_editor.execute(
            """
            ALTER TABLE trading_tasks
            ALTER COLUMN trading_mode SET NOT NULL
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0023_alter_metrics_execution_id_alter_metrics_metrics_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    restore_trading_mode_column,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="tradingtask",
                    name="trading_mode",
                    field=models.CharField(
                        choices=[("netting", "Netting Mode"), ("hedging", "Hedging Mode")],
                        default="netting",
                        help_text=(
                            "Trading mode: netting (aggregated positions) "
                            "or hedging (independent trades)."
                        ),
                        max_length=20,
                    ),
                ),
            ],
        ),
    ]
