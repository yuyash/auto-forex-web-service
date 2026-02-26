"""Repair trading schema drift for legacy local databases.

This command is intentionally idempotent and only adds missing columns/tables.
It helps local environments where historical migration graphs diverged.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "Repair legacy trading DB schema by creating missing tables/columns "
        "required by the current code."
    )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("repair_trading_schema currently supports PostgreSQL only.")

        statements = [
            # backtest_tasks
            "ALTER TABLE backtest_tasks ADD COLUMN IF NOT EXISTS account_currency VARCHAR(3) NOT NULL DEFAULT 'USD'",
            "ALTER TABLE backtest_tasks ADD COLUMN IF NOT EXISTS execution_run_id INTEGER NOT NULL DEFAULT 0",
            # trading_tasks
            "ALTER TABLE trading_tasks ADD COLUMN IF NOT EXISTS execution_run_id INTEGER NOT NULL DEFAULT 0",
            # execution_state
            "ALTER TABLE execution_state ADD COLUMN IF NOT EXISTS execution_run_id INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE execution_state ADD COLUMN IF NOT EXISTS last_tick_price NUMERIC(20, 10)",
            "ALTER TABLE execution_state ADD COLUMN IF NOT EXISTS last_tick_bid NUMERIC(20, 10)",
            "ALTER TABLE execution_state ADD COLUMN IF NOT EXISTS last_tick_ask NUMERIC(20, 10)",
            # task_logs
            "ALTER TABLE task_logs ADD COLUMN IF NOT EXISTS execution_run_id INTEGER NOT NULL DEFAULT 0",
            # trades
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS execution_run_id INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS retracement_count INTEGER",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS position_id UUID",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS order_id UUID",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS oanda_trade_id VARCHAR(64)",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            "ALTER TABLE trades ALTER COLUMN direction DROP NOT NULL",
            # positions
            "ALTER TABLE positions ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR(255)",
            "ALTER TABLE positions ADD COLUMN IF NOT EXISTS execution_run_id INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE positions ADD COLUMN IF NOT EXISTS retracement_count INTEGER",
            "ALTER TABLE positions ADD COLUMN IF NOT EXISTS oanda_trade_id VARCHAR(64)",
            # orders
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR(255)",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS execution_run_id INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS oanda_trade_id VARCHAR(64)",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS position_id UUID",
            "ALTER TABLE orders ALTER COLUMN direction DROP NOT NULL",
            # trading_events
            "ALTER TABLE trading_events ADD COLUMN IF NOT EXISTS execution_run_id INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE trading_events ADD COLUMN IF NOT EXISTS is_processed BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE trading_events ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ",
            "ALTER TABLE trading_events ADD COLUMN IF NOT EXISTS processing_error TEXT NOT NULL DEFAULT ''",
            # metrics table
            (
                "CREATE TABLE IF NOT EXISTS metrics ("
                "id UUID PRIMARY KEY, "
                "task_type VARCHAR(32) NOT NULL, "
                "task_id UUID NOT NULL, "
                "celery_task_id VARCHAR(255), "
                "execution_run_id INTEGER NOT NULL DEFAULT 0, "
                "timestamp TIMESTAMPTZ NOT NULL, "
                "margin_ratio NUMERIC(10, 6), "
                "current_atr NUMERIC(20, 10), "
                "baseline_atr NUMERIC(20, 10), "
                "volatility_threshold NUMERIC(20, 10), "
                "metrics JSONB NOT NULL DEFAULT '{}'::jsonb"
                ")"
            ),
            "CREATE INDEX IF NOT EXISTS metrics_task_id_idx ON metrics (task_type, task_id, execution_run_id, timestamp)",
        ]

        with connection.cursor() as cursor:
            for sql in statements:
                cursor.execute(sql)
        connection.commit()

        self.stdout.write(self.style.SUCCESS("Trading schema repair completed successfully."))
