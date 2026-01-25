# Generated migration for task execution architecture refactor

from django.db import migrations, models
import django.db.models.deletion
from uuid import uuid4


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0001_initial'),
    ]

    operations = [
        # Step 1: Add new execution fields to BacktestTasks
        migrations.AddField(
            model_name='backtesttasks',
            name='celery_task_id',
            field=models.CharField(
                max_length=255,
                null=True,
                blank=True,
                db_index=True,
                help_text='Celery task ID for tracking execution',
            ),
        ),
        migrations.AddField(
            model_name='backtesttasks',
            name='started_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp when the task execution started',
            ),
        ),
        migrations.AddField(
            model_name='backtesttasks',
            name='completed_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp when the task execution completed',
            ),
        ),
        migrations.AddField(
            model_name='backtesttasks',
            name='error_message',
            field=models.TextField(
                null=True,
                blank=True,
                help_text='Error message if task failed',
            ),
        ),
        migrations.AddField(
            model_name='backtesttasks',
            name='error_traceback',
            field=models.TextField(
                null=True,
                blank=True,
                help_text='Full error traceback if task failed',
            ),
        ),
        migrations.AddField(
            model_name='backtesttasks',
            name='retry_count',
            field=models.IntegerField(
                default=0,
                help_text='Number of times this task has been retried',
            ),
        ),
        migrations.AddField(
            model_name='backtesttasks',
            name='max_retries',
            field=models.IntegerField(
                default=3,
                help_text='Maximum number of retries allowed',
            ),
        ),
        migrations.AddField(
            model_name='backtesttasks',
            name='result_data',
            field=models.JSONField(
                null=True,
                blank=True,
                help_text='Execution results data',
            ),
        ),

        # Step 2: Add new execution fields to TradingTasks
        migrations.AddField(
            model_name='tradingtasks',
            name='celery_task_id',
            field=models.CharField(
                max_length=255,
                null=True,
                blank=True,
                db_index=True,
                help_text='Celery task ID for tracking execution',
            ),
        ),
        migrations.AddField(
            model_name='tradingtasks',
            name='started_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp when the task execution started',
            ),
        ),
        migrations.AddField(
            model_name='tradingtasks',
            name='completed_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp when the task execution completed',
            ),
        ),
        migrations.AddField(
            model_name='tradingtasks',
            name='error_message',
            field=models.TextField(
                null=True,
                blank=True,
                help_text='Error message if task failed',
            ),
        ),
        migrations.AddField(
            model_name='tradingtasks',
            name='error_traceback',
            field=models.TextField(
                null=True,
                blank=True,
                help_text='Full error traceback if task failed',
            ),
        ),
        migrations.AddField(
            model_name='tradingtasks',
            name='retry_count',
            field=models.IntegerField(
                default=0,
                help_text='Number of times this task has been retried',
            ),
        ),
        migrations.AddField(
            model_name='tradingtasks',
            name='max_retries',
            field=models.IntegerField(
                default=3,
                help_text='Maximum number of retries allowed',
            ),
        ),
        migrations.AddField(
            model_name='tradingtasks',
            name='result_data',
            field=models.JSONField(
                null=True,
                blank=True,
                help_text='Execution results data',
            ),
        ),

        # Step 3: Update TaskStatus choices to include new statuses
        migrations.AlterField(
            model_name='backtesttasks',
            name='status',
            field=models.CharField(
                max_length=20,
                default='created',
                choices=[
                    ('created', 'Created'),
                    ('pending', 'Pending'),
                    ('running', 'Running'),
                    ('stopped', 'Stopped'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                help_text='Current task status',
            ),
        ),
        migrations.AlterField(
            model_name='tradingtasks',
            name='status',
            field=models.CharField(
                max_length=20,
                default='created',
                choices=[
                    ('created', 'Created'),
                    ('pending', 'Pending'),
                    ('running', 'Running'),
                    ('stopped', 'Stopped'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                help_text='Current task status',
            ),
        ),

        # Step 4: Add indexes for new fields
        migrations.AddIndex(
            model_name='backtesttasks',
            index=models.Index(fields=['celery_task_id'], name='backtest_ta_celery__idx'),
        ),
        migrations.AddIndex(
            model_name='backtesttasks',
            index=models.Index(fields=['status', 'created_at'], name='backtest_ta_status__idx'),
        ),
        migrations.AddIndex(
            model_name='tradingtasks',
            index=models.Index(fields=['celery_task_id'], name='trading_tas_celery__idx'),
        ),
        migrations.AddIndex(
            model_name='tradingtasks',
            index=models.Index(fields=['status', 'created_at'], name='trading_tas_status__idx'),
        ),

        # Step 5: Create TaskLog model
        migrations.CreateModel(
            name='TaskLog',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True,
                    default=uuid4,
                    editable=False,
                    help_text='Unique identifier for this log entry',
                )),
                ('timestamp', models.DateTimeField(
                    auto_now_add=True,
                    help_text='When this log entry was created',
                )),
                ('level', models.CharField(
                    max_length=20,
                    choices=[
                        ('debug', 'Debug'),
                        ('info', 'Info'),
                        ('warning', 'Warning'),
                        ('error', 'Error'),
                    ],
                    default='info',
                    help_text='Log severity level',
                )),
                ('message', models.TextField(
                    help_text='Log message content',
                )),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='logs',
                    to='trading.backtesttasks',
                    help_text='Task this log entry belongs to',
                )),
            ],
            options={
                'db_table': 'task_logs',
                'verbose_name': 'Task Log',
                'verbose_name_plural': 'Task Logs',
                'ordering': ['timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='tasklog',
            index=models.Index(fields=['task', 'timestamp'], name='task_logs_task_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='tasklog',
            index=models.Index(fields=['task', 'level'], name='task_logs_task_level_idx'),
        ),

        # Step 6: Create TaskMetric model
        migrations.CreateModel(
            name='TaskMetric',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True,
                    default=uuid4,
                    editable=False,
                    help_text='Unique identifier for this metric entry',
                )),
                ('metric_name', models.CharField(
                    max_length=255,
                    help_text='Name of the metric (e.g., "equity", "drawdown", "trades_count")',
                )),
                ('metric_value', models.FloatField(
                    help_text='Numeric value of the metric',
                )),
                ('timestamp', models.DateTimeField(
                    auto_now_add=True,
                    help_text='When this metric was recorded',
                )),
                ('metadata', models.JSONField(
                    null=True,
                    blank=True,
                    help_text='Optional additional metadata for this metric',
                )),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='metrics',
                    to='trading.backtesttasks',
                    help_text='Task this metric belongs to',
                )),
            ],
            options={
                'db_table': 'task_metrics',
                'verbose_name': 'Task Metric',
                'verbose_name_plural': 'Task Metrics',
                'ordering': ['timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='taskmetric',
            index=models.Index(fields=['task', 'metric_name', 'timestamp'], name='task_metrics_task_name_ts_idx'),
        ),

        # Step 7: Remove execution field from TradingEvent
        migrations.RemoveField(
            model_name='tradingevent',
            name='execution',
        ),

        # Step 8: Delete models that reference Executions
        migrations.DeleteModel(
            name='StrategyEvents',
        ),
        migrations.DeleteModel(
            name='TradeLogs',
        ),
        migrations.DeleteModel(
            name='TradingMetrics',
        ),
        migrations.DeleteModel(
            name='ExecutionStateSnapshot',
        ),
        migrations.DeleteModel(
            name='TaskExecutionResult',
        ),

        # Step 9: Delete Executions model
        migrations.DeleteModel(
            name='Executions',
        ),

        # Step 10: Update TradingTasks constraint to include new statuses
        migrations.RemoveConstraint(
            model_name='tradingtasks',
            name='valid_trading_task_status',
        ),
        migrations.AddConstraint(
            model_name='tradingtasks',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        'created',
                        'pending',
                        'running',
                        'stopped',
                        'completed',
                        'failed',
                        'cancelled',
                    ]
                ),
                name='valid_trading_task_status',
            ),
        ),
    ]
