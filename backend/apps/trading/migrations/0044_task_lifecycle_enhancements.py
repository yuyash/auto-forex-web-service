"""Add broker retry, drain, and market-idle task settings plus new statuses.

This migration introduces:

* TradingTask fields for OANDA API retry/backoff configuration and the new
  drain-on-stop and market-aware idle modes.
* BacktestTask field for drain-on-stop.
* Updated CheckConstraint + UniqueConstraint on TradingTask to recognise the
  new DRAINING and IDLE statuses.
"""

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0043_add_notes_to_execution_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="tradingtask",
            name="api_retry_max_attempts",
            field=models.PositiveIntegerField(
                default=50,
                help_text=(
                    "Maximum number of retry attempts for OANDA API calls before the task "
                    "fails. Uses exponential backoff between attempts."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tradingtask",
            name="api_retry_backoff_base_seconds",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1.0"),
                max_digits=6,
                help_text=(
                    "Initial delay between OANDA API retries (seconds). Doubled on each "
                    "attempt."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tradingtask",
            name="api_retry_backoff_max_seconds",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("60.0"),
                max_digits=7,
                help_text="Cap on the backoff delay between retries (seconds).",
            ),
        ),
        migrations.AddField(
            model_name="tradingtask",
            name="drain_duration_hours",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Maximum duration in hours for drain-on-stop before forcing a stop. "
                    "Set to 0 to wait indefinitely for positions to reach breakeven."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tradingtask",
            name="market_idle_pre_close_minutes",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Switch to IDLE this many minutes before the market closes. "
                    "0 disables pre-close idling."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tradingtask",
            name="market_idle_resume_delay_minutes",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Wait this many minutes after the market reopens before resuming "
                    "trading. 0 disables the resume delay."
                ),
            ),
        ),
        migrations.AddField(
            model_name="backtesttask",
            name="drain_duration_hours",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Maximum duration in hours for drain-on-stop before forcing a stop. "
                    "Set to 0 to wait indefinitely for positions to reach breakeven."
                ),
            ),
        ),
        migrations.RemoveConstraint(
            model_name="tradingtask",
            name="uniq_active_trading_task_per_account",
        ),
        migrations.RemoveConstraint(
            model_name="tradingtask",
            name="valid_trading_task_status",
        ),
        migrations.AddConstraint(
            model_name="tradingtask",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    status__in=[
                        "starting",
                        "running",
                        "paused",
                        "idle",
                        "draining",
                        "stopping",
                    ]
                ),
                fields=("oanda_account",),
                name="uniq_active_trading_task_per_account",
            ),
        ),
        migrations.AddConstraint(
            model_name="tradingtask",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "created",
                        "starting",
                        "running",
                        "paused",
                        "idle",
                        "draining",
                        "stopping",
                        "stopped",
                        "completed",
                        "failed",
                    ]
                ),
                name="valid_trading_task_status",
            ),
        ),
    ]
