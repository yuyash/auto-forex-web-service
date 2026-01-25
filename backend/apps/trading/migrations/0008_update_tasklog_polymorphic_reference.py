# Generated migration for polymorphic task reference in TaskLog and TaskMetric

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0007_rename_executionequity_to_equities'),
    ]

    operations = [
        # Step 1: Add task_type field
        migrations.AddField(
            model_name='tasklog',
            name='task_type',
            field=models.CharField(
                max_length=32,
                choices=[('backtest', 'Backtest'), ('trading', 'Trading')],
                db_index=True,
                help_text='Type of task (backtest or trading)',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='tasklog',
            name='details',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Additional structured log details',
            ),
        ),
        migrations.AddField(
            model_name='taskmetric',
            name='task_type',
            field=models.CharField(
                max_length=32,
                choices=[('backtest', 'Backtest'), ('trading', 'Trading')],
                db_index=True,
                help_text='Type of task (backtest or trading)',
                null=True,
            ),
        ),

        # Step 2: Rename existing task FK to task_old (field name is 'task', db column is 'task_id')
        migrations.RenameField(
            model_name='tasklog',
            old_name='task',
            new_name='task_old',
        ),
        migrations.RenameField(
            model_name='taskmetric',
            old_name='task',
            new_name='task_old',
        ),

        # Step 3: Add new task_id as UUID field
        migrations.AddField(
            model_name='tasklog',
            name='task_id',
            field=models.UUIDField(
                db_index=True,
                help_text='UUID of the task this log entry belongs to',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='taskmetric',
            name='task_id',
            field=models.UUIDField(
                db_index=True,
                help_text='UUID of the task this metric belongs to',
                null=True,
            ),
        ),

        # Step 4: Set default values for existing records
        # Note: Existing task_old_id values are bigint pointing to old integer IDs
        # that no longer exist after BacktestTasks migrated to UUID.
        # We'll set a default UUID and task_type for existing records.
        migrations.RunSQL(
            sql="""
                UPDATE task_logs
                SET task_id = gen_random_uuid(), task_type = 'backtest'
                WHERE task_type IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                UPDATE task_metrics
                SET task_id = gen_random_uuid(), task_type = 'backtest'
                WHERE task_type IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # Step 5: Make new fields non-nullable
        migrations.AlterField(
            model_name='tasklog',
            name='task_type',
            field=models.CharField(
                max_length=32,
                choices=[('backtest', 'Backtest'), ('trading', 'Trading')],
                db_index=True,
                help_text='Type of task (backtest or trading)',
            ),
        ),
        migrations.AlterField(
            model_name='tasklog',
            name='task_id',
            field=models.UUIDField(
                db_index=True,
                help_text='UUID of the task this log entry belongs to',
            ),
        ),
        migrations.AlterField(
            model_name='taskmetric',
            name='task_type',
            field=models.CharField(
                max_length=32,
                choices=[('backtest', 'Backtest'), ('trading', 'Trading')],
                db_index=True,
                help_text='Type of task (backtest or trading)',
            ),
        ),
        migrations.AlterField(
            model_name='taskmetric',
            name='task_id',
            field=models.UUIDField(
                db_index=True,
                help_text='UUID of the task this metric belongs to',
            ),
        ),

        # Step 6: Remove old indexes
        migrations.RemoveIndex(
            model_name='tasklog',
            name='task_logs_task_id_0d6ce6_idx',
        ),
        migrations.RemoveIndex(
            model_name='tasklog',
            name='task_logs_task_id_8914fc_idx',
        ),
        migrations.RemoveIndex(
            model_name='tasklog',
            name='task_logs_task_id_153ad2_idx',
        ),
        migrations.RemoveIndex(
            model_name='taskmetric',
            name='task_metric_task_id_e392a9_idx',
        ),
        migrations.RemoveIndex(
            model_name='taskmetric',
            name='task_metric_task_id_4760f3_idx',
        ),

        # Step 7: Add new indexes
        migrations.AddIndex(
            model_name='tasklog',
            index=models.Index(fields=['task_type', 'task_id', 'timestamp'], name='task_logs_task_ty_3c3c3c_idx'),
        ),
        migrations.AddIndex(
            model_name='tasklog',
            index=models.Index(fields=['task_type', 'task_id', 'level'], name='task_logs_task_ty_4d4d4d_idx'),
        ),
        migrations.AddIndex(
            model_name='tasklog',
            index=models.Index(fields=['celery_task_id'], name='task_logs_celery__5e5e5e_idx'),
        ),
        migrations.AddIndex(
            model_name='taskmetric',
            index=models.Index(fields=['task_type', 'task_id', 'metric_name', 'timestamp'], name='task_metric_task_ty_6f6f6f_idx'),
        ),
        migrations.AddIndex(
            model_name='taskmetric',
            index=models.Index(fields=['celery_task_id'], name='task_metric_celery__7a7a7a_idx'),
        ),

        # Step 8: Remove old foreign key field
        migrations.RemoveField(
            model_name='tasklog',
            name='task_old',
        ),
        migrations.RemoveField(
            model_name='taskmetric',
            name='task_old',
        ),
    ]
