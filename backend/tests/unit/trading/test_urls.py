"""
Unit tests for trading app URL patterns.

Tests verify that:
- All new execution-based routes resolve correctly
- Task control routes (resume, restart) resolve correctly
- Removed task-specific data routes return 404
"""

from django.test import TestCase
from django.urls import resolve, reverse


class ExecutionURLTests(TestCase):
    """Test execution-based URL patterns."""

    def test_execution_detail_url_resolves(self):
        """Test that execution detail URL resolves correctly."""
        url = reverse("trading:execution_detail", kwargs={"execution_id": 1})
        self.assertEqual(url, "/api/trading/executions/1/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:execution_detail")

    def test_execution_logs_url_resolves(self):
        """Test that execution logs URL resolves correctly."""
        url = reverse("trading:execution_logs", kwargs={"execution_id": 1})
        self.assertEqual(url, "/api/trading/executions/1/logs/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:execution_logs")

    def test_execution_status_url_resolves(self):
        """Test that execution status URL resolves correctly."""
        url = reverse("trading:execution_status", kwargs={"execution_id": 1})
        self.assertEqual(url, "/api/trading/executions/1/status/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:execution_status")

    def test_execution_events_url_resolves(self):
        """Test that execution events URL resolves correctly."""
        url = reverse("trading:execution_events", kwargs={"execution_id": 1})
        self.assertEqual(url, "/api/trading/executions/1/events/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:execution_events")

    def test_execution_trades_url_resolves(self):
        """Test that execution trades URL resolves correctly."""
        url = reverse("trading:execution_trades", kwargs={"execution_id": 1})
        self.assertEqual(url, "/api/trading/executions/1/trades/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:execution_trades")

    def test_execution_equity_url_resolves(self):
        """Test that execution equity URL resolves correctly."""
        url = reverse("trading:execution_equity", kwargs={"execution_id": 1})
        self.assertEqual(url, "/api/trading/executions/1/equity/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:execution_equity")

    def test_execution_metrics_url_resolves(self):
        """Test that execution metrics URL resolves correctly."""
        url = reverse("trading:execution_metrics", kwargs={"execution_id": 1})
        self.assertEqual(url, "/api/trading/executions/1/metrics/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:execution_metrics")

    def test_execution_metrics_latest_url_resolves(self):
        """Test that execution latest metrics URL resolves correctly."""
        url = reverse("trading:execution_metrics_latest", kwargs={"execution_id": 1})
        self.assertEqual(url, "/api/trading/executions/1/metrics/latest/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:execution_metrics_latest")


class TaskControlURLTests(TestCase):
    """Test task control URL patterns."""

    def test_backtest_task_resume_url_resolves(self):
        """Test that backtest task resume URL resolves correctly."""
        url = reverse("trading:backtest_task_resume", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/backtest-tasks/1/resume/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:backtest_task_resume")

    def test_trading_task_resume_url_resolves(self):
        """Test that trading task resume URL resolves correctly."""
        url = reverse("trading:trading_task_resume", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/trading-tasks/1/resume/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:trading_task_resume")

    def test_trading_task_restart_url_resolves(self):
        """Test that trading task restart URL resolves correctly."""
        url = reverse("trading:trading_task_restart", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/trading-tasks/1/restart/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:trading_task_restart")


class RemovedURLTests(TestCase):
    """Test that removed task-specific data URLs no longer exist."""

    def test_backtest_task_logs_url_removed(self):
        """Test that backtest task logs URL is removed."""
        with self.assertRaises(Exception):
            reverse("trading:backtest_task_logs", kwargs={"task_id": 1})

    def test_backtest_task_export_url_removed(self):
        """Test that backtest task export URL is removed."""
        with self.assertRaises(Exception):
            reverse("trading:backtest_task_export", kwargs={"task_id": 1})

    def test_trading_task_logs_url_removed(self):
        """Test that trading task logs URL is removed."""
        with self.assertRaises(Exception):
            reverse("trading:trading_task_logs", kwargs={"task_id": 1})


class ExistingURLTests(TestCase):
    """Test that existing URLs still work correctly."""

    def test_strategy_list_url_resolves(self):
        """Test that strategy list URL resolves correctly."""
        url = reverse("trading:strategy_list")
        self.assertEqual(url, "/api/trading/strategies/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:strategy_list")

    def test_backtest_task_list_url_resolves(self):
        """Test that backtest task list URL resolves correctly."""
        url = reverse("trading:backtest_task_list_create")
        self.assertEqual(url, "/api/trading/backtest-tasks/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:backtest_task_list_create")

    def test_backtest_task_detail_url_resolves(self):
        """Test that backtest task detail URL resolves correctly."""
        url = reverse("trading:backtest_task_detail", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/backtest-tasks/1/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:backtest_task_detail")

    def test_backtest_task_start_url_resolves(self):
        """Test that backtest task start URL resolves correctly."""
        url = reverse("trading:backtest_task_start", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/backtest-tasks/1/start/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:backtest_task_start")

    def test_backtest_task_stop_url_resolves(self):
        """Test that backtest task stop URL resolves correctly."""
        url = reverse("trading:backtest_task_stop", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/backtest-tasks/1/stop/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:backtest_task_stop")

    def test_backtest_task_status_url_resolves(self):
        """Test that backtest task status URL resolves correctly."""
        url = reverse("trading:backtest_task_status", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/backtest-tasks/1/status/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:backtest_task_status")

    def test_trading_task_list_url_resolves(self):
        """Test that trading task list URL resolves correctly."""
        url = reverse("trading:trading_task_list_create")
        self.assertEqual(url, "/api/trading/trading-tasks/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:trading_task_list_create")

    def test_trading_task_detail_url_resolves(self):
        """Test that trading task detail URL resolves correctly."""
        url = reverse("trading:trading_task_detail", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/trading-tasks/1/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:trading_task_detail")

    def test_trading_task_start_url_resolves(self):
        """Test that trading task start URL resolves correctly."""
        url = reverse("trading:trading_task_start", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/trading-tasks/1/start/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:trading_task_start")

    def test_trading_task_stop_url_resolves(self):
        """Test that trading task stop URL resolves correctly."""
        url = reverse("trading:trading_task_stop", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/trading-tasks/1/stop/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:trading_task_stop")

    def test_trading_task_status_url_resolves(self):
        """Test that trading task status URL resolves correctly."""
        url = reverse("trading:trading_task_status", kwargs={"task_id": 1})
        self.assertEqual(url, "/api/trading/trading-tasks/1/status/")
        resolver = resolve(url)
        self.assertEqual(resolver.view_name, "trading:trading_task_status")
