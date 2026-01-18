"""Unit tests for trading app migrations.

Tests that migrations apply successfully and create the correct schema.
"""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db
class TestMigrations:
    """Test trading app migrations."""

    def test_migrations_apply_successfully(self):
        """Test that all migrations apply without errors."""
        executor = MigrationExecutor(connection)

        # Get all migrations for the trading app
        app_label = "trading"
        migrations = executor.loader.graph.leaf_nodes(app_label)

        # Verify migrations exist
        assert len(migrations) > 0, "No migrations found for trading app"

        # Apply all migrations (this will raise an exception if any fail)
        executor.migrate(migrations)

        # Verify we're at the latest migration
        applied = executor.loader.applied_migrations
        for migration in migrations:
            assert migration in applied, f"Migration {migration} was not applied"

    def test_old_tables_are_dropped(self):
        """Test that old metrics tables are dropped."""
        with connection.cursor() as cursor:
            # Check that old tables don't exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN (
                    'execution_metrics',
                    'execution_metrics_checkpoints',
                    'execution_equity_points'
                )
            """)
            old_tables = cursor.fetchall()

            assert len(old_tables) == 0, f"Old tables still exist: {[t[0] for t in old_tables]}"

    def test_new_tables_are_created(self):
        """Test that new tables are created with correct schema."""
        with connection.cursor() as cursor:
            # Check that new tables exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN (
                    'trading_metrics',
                    'strategy_events',
                    'trade_logs',
                    'executions',
                    'backtest_tasks',
                    'trading_tasks',
                    'strategy_configurations'
                )
            """)
            new_tables = cursor.fetchall()
            table_names = [t[0] for t in new_tables]

            expected_tables = [
                "trading_metrics",
                "strategy_events",
                "trade_logs",
                "executions",
                "backtest_tasks",
                "trading_tasks",
                "strategy_configurations",
            ]

            for table in expected_tables:
                assert table in table_names, f"Table {table} was not created"

    def test_trading_metrics_schema(self):
        """Test that trading_metrics table has correct schema."""
        with connection.cursor() as cursor:
            # Get column information for trading_metrics
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'trading_metrics'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            column_dict = {col[0]: (col[1], col[2]) for col in columns}

            # Verify required columns exist
            required_columns = [
                "id",
                "execution_id",
                "sequence",
                "timestamp",
                "realized_pnl",
                "unrealized_pnl",
                "total_pnl",
                "open_positions",
                "total_trades",
                "tick_ask_min",
                "tick_ask_max",
                "tick_ask_avg",
                "tick_bid_min",
                "tick_bid_max",
                "tick_bid_avg",
                "tick_mid_min",
                "tick_mid_max",
                "tick_mid_avg",
                "created_at",
                "updated_at",
            ]

            for col in required_columns:
                assert col in column_dict, f"Column {col} not found in trading_metrics"

            # Verify PnL columns are numeric
            pnl_columns = [
                "realized_pnl",
                "unrealized_pnl",
                "total_pnl",
                "tick_ask_min",
                "tick_ask_max",
                "tick_ask_avg",
                "tick_bid_min",
                "tick_bid_max",
                "tick_bid_avg",
                "tick_mid_min",
                "tick_mid_max",
                "tick_mid_avg",
            ]

            for col in pnl_columns:
                assert column_dict[col][0] == "numeric", (
                    f"Column {col} should be numeric, got {column_dict[col][0]}"
                )

    def test_indexes_are_created(self):
        """Test that indexes are created on trading_metrics."""
        with connection.cursor() as cursor:
            # Get index information for trading_metrics
            cursor.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'trading_metrics'
            """)
            indexes = cursor.fetchall()
            index_defs = [idx[1] for idx in indexes]  # Get index definitions

            # Verify required indexes exist by checking index definitions
            # Check for index on (execution, sequence)
            assert any("execution" in idx and "sequence" in idx for idx in index_defs), (
                "Index on (execution, sequence) not found"
            )
            # Check for index on (execution, timestamp)
            assert any("execution" in idx and "timestamp" in idx for idx in index_defs), (
                "Index on (execution, timestamp) not found"
            )

    def test_unique_constraint_on_trading_metrics(self):
        """Test that unique constraint exists on (execution, sequence)."""
        with connection.cursor() as cursor:
            # Get constraint information
            cursor.execute("""
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints
                WHERE table_schema = 'public'
                AND table_name = 'trading_metrics'
                AND constraint_type = 'UNIQUE'
            """)
            constraints = cursor.fetchall()

            # Verify unique constraint exists
            assert len(constraints) > 0, "No unique constraint found on trading_metrics"

    def test_renamed_models_tables_exist(self):
        """Test that renamed model tables exist with correct names."""
        with connection.cursor() as cursor:
            # Check that renamed tables exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN (
                    'executions',
                    'backtest_tasks',
                    'trading_tasks',
                    'strategy_configurations',
                    'strategy_events',
                    'trade_logs'
                )
            """)
            tables = cursor.fetchall()
            table_names = [t[0] for t in tables]

            expected_tables = [
                "executions",
                "backtest_tasks",
                "trading_tasks",
                "strategy_configurations",
                "strategy_events",
                "trade_logs",
            ]

            for table in expected_tables:
                assert table in table_names, f"Renamed table {table} not found"

    def test_old_model_tables_do_not_exist(self):
        """Test that old model tables no longer exist."""
        with connection.cursor() as cursor:
            # Check that old tables don't exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN (
                    'task_executions',
                    'backtest_task',
                    'trading_task',
                    'strategy_config',
                    'execution_strategy_events',
                    'execution_trade_logs'
                )
            """)
            result = cursor.fetchall()

            # Note: Some old table names may not have existed, so we just verify
            # that if they did exist, they've been renamed
            # The key is that the new tables exist (tested above)
            assert len(result) == 0, f"Old tables still exist: {[t[0] for t in result]}"
