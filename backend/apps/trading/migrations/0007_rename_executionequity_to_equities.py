# Generated migration for renaming ExecutionEquity to Equities

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0006_rename_executiontrade_to_trades'),
    ]

    operations = [
        # Rename the model
        migrations.RenameModel(
            old_name='ExecutionEquity',
            new_name='Equities',
        ),

        # Rename the table
        migrations.AlterModelTable(
            name='equities',
            table='equities',
        ),

        # Update verbose names
        migrations.AlterModelOptions(
            name='equities',
            options={
                'ordering': ['timestamp'],
                'verbose_name': 'Equity',
                'verbose_name_plural': 'Equities',
            },
        ),

        # Add task_type field (temporary nullable)
        migrations.AddField(
            model_name='equities',
            name='task_type',
            field=models.CharField(
                db_index=True,
                help_text='Type of task (backtest or trading)',
                max_length=32,
                null=True,
            ),
        ),

        # Add new task_id field (temporary nullable)
        migrations.AddField(
            model_name='equities',
            name='new_task_id',
            field=models.UUIDField(
                db_index=True,
                help_text='UUID of the task this equity point belongs to',
                null=True,
            ),
        ),

        # Populate task_type and new_task_id from existing task ForeignKey
        migrations.RunSQL(
            sql="""
                UPDATE equities
                SET task_type = 'backtest',
                    new_task_id = task_id
                WHERE task_id IS NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # Make fields non-nullable
        migrations.AlterField(
            model_name='equities',
            name='task_type',
            field=models.CharField(
                db_index=True,
                help_text='Type of task (backtest or trading)',
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name='equities',
            name='new_task_id',
            field=models.UUIDField(
                db_index=True,
                help_text='UUID of the task this equity point belongs to',
            ),
        ),

        # Remove old task ForeignKey
        migrations.RemoveField(
            model_name='equities',
            name='task',
        ),

        # Rename new_task_id to task_id
        migrations.RenameField(
            model_name='equities',
            old_name='new_task_id',
            new_name='task_id',
        ),

        # Remove old indexes
        migrations.RemoveIndex(
            model_name='equities',
            name='execution_e_task_id_d4f41c_idx',
        ),
        migrations.RemoveIndex(
            model_name='equities',
            name='execution_e_task_id_5aa924_idx',
        ),

        # Remove old constraint
        migrations.RemoveConstraint(
            model_name='equities',
            name='unique_task_execution_equity_timestamp',
        ),

        # Add new indexes (using shorter names to comply with database limits)
        migrations.AddIndex(
            model_name='equities',
            index=models.Index(
                fields=['task_type', 'task_id', 'timestamp'],
                name='equities_task_ty_4915f3_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='equities',
            index=models.Index(
                fields=['task_type', 'task_id', 'celery_task_id'],
                name='equities_task_ty_acb8b3_idx',
            ),
        ),

        # Add new constraint
        migrations.AddConstraint(
            model_name='equities',
            constraint=models.UniqueConstraint(
                fields=['task_type', 'task_id', 'celery_task_id', 'timestamp'],
                name='unique_task_execution_equity_timestamp',
            ),
        ),
    ]
