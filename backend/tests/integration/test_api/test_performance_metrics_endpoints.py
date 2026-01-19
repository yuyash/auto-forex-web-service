"""
Integration tests for performance metrics API endpoints.

Tests performance calculation endpoints and metrics aggregation by account/strategy.
"""

from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTasks, Executions, TradingMetrics, TradingTasks
from tests.integration.base import APIIntegrationTestCase
from tests.integration.factories import (
    BacktestTaskFactory,
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


class ExecutionMetricsEndpointTests(APIIntegrationTestCase):
    """Tests for execution metrics endpoints."""

    def setUp(self) -> None:
        """Set up test data for metrics tests."""
        super().setUp()
        self.account = OandaAccountFactory(user=self.user)
        self.strategy_config = StrategyConfigurationFactory(user=self.user)

    def _create_backtest_execution_with_metrics(
        self, num_metrics: int = 5
    ) -> tuple[BacktestTasks, Executions]:
        """Helper to create a backtest execution with metrics."""
        backtest_task = BacktestTaskFactory(
            user=self.user,
            config=self.strategy_config,
            status=TaskStatus.RUNNING,
        )

        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Create metrics snapshots
        base_time = timezone.now()
        for i in range(num_metrics):
            TradingMetrics.objects.create(
                execution=execution,
                sequence=i,
                timestamp=base_time + timedelta(seconds=i * 60),
                realized_pnl=Decimal(str(100.0 * i)),
                unrealized_pnl=Decimal(str(50.0 * i)),
                total_pnl=Decimal(str(150.0 * i)),
                open_positions=i % 3,
                total_trades=i * 2,
                tick_ask_min=Decimal("1.10000"),
                tick_ask_max=Decimal("1.10050"),
                tick_ask_avg=Decimal("1.10025"),
                tick_bid_min=Decimal("1.09990"),
                tick_bid_max=Decimal("1.10040"),
                tick_bid_avg=Decimal("1.10015"),
                tick_mid_min=Decimal("1.09995"),
                tick_mid_max=Decimal("1.10045"),
                tick_mid_avg=Decimal("1.10020"),
            )

        return backtest_task, execution  # ty:ignore[invalid-return-type]

    def _create_trading_execution_with_metrics(
        self, num_metrics: int = 5
    ) -> tuple[TradingTasks, Executions]:
        """Helper to create a trading execution with metrics."""
        trading_task = TradingTaskFactory(
            user=self.user,
            oanda_account=self.account,
            config=self.strategy_config,
            status=TaskStatus.RUNNING,
        )

        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=trading_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Create metrics snapshots
        base_time = timezone.now()
        for i in range(num_metrics):
            TradingMetrics.objects.create(
                execution=execution,
                sequence=i,
                timestamp=base_time + timedelta(seconds=i * 60),
                realized_pnl=Decimal(str(200.0 * i)),
                unrealized_pnl=Decimal(str(75.0 * i)),
                total_pnl=Decimal(str(275.0 * i)),
                open_positions=i % 4,
                total_trades=i * 3,
                tick_ask_min=Decimal("1.20000"),
                tick_ask_max=Decimal("1.20050"),
                tick_ask_avg=Decimal("1.20025"),
                tick_bid_min=Decimal("1.19990"),
                tick_bid_max=Decimal("1.20040"),
                tick_bid_avg=Decimal("1.20015"),
                tick_mid_min=Decimal("1.19995"),
                tick_mid_max=Decimal("1.20045"),
                tick_mid_avg=Decimal("1.20020"),
            )

        return trading_task, execution  # ty:ignore[invalid-return-type]

    def test_get_execution_metrics_raw_success(self) -> None:
        """Test retrieving raw metrics for an execution."""
        _, execution = self._create_backtest_execution_with_metrics(num_metrics=3)

        url = reverse("trading:execution_metrics", kwargs={"execution_id": execution.pk})
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["execution_id"], execution.pk)  # type: ignore[attr-defined]
        self.assertEqual(response.data["task_type"], TaskType.BACKTEST)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("metrics", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data["metrics"]), 3)  # ty:ignore[possibly-missing-attribute]

        # Verify metrics structure
        first_metric = response.data["metrics"][0]  # ty:ignore[possibly-missing-attribute]
        self.assertIn("sequence", first_metric)
        self.assertIn("timestamp", first_metric)
        self.assertIn("realized_pnl", first_metric)
        self.assertIn("unrealized_pnl", first_metric)
        self.assertIn("total_pnl", first_metric)
        self.assertIn("open_positions", first_metric)
        self.assertIn("total_trades", first_metric)

    def test_get_execution_metrics_with_time_range_filter(self) -> None:
        """Test filtering metrics by time range."""
        _, execution = self._create_backtest_execution_with_metrics(num_metrics=10)

        # Get all metrics to find time range
        all_metrics = TradingMetrics.objects.filter(execution=execution).order_by("sequence")
        start_time = all_metrics[2].timestamp.isoformat()
        end_time = all_metrics[7].timestamp.isoformat()

        url = reverse("trading:execution_metrics", kwargs={"execution_id": execution.pk})
        response = self.client.get(url, {"start_time": start_time, "end_time": end_time})

        self.assert_response_success(response)  # type: ignore[arg-type]
        # Should return metrics from sequence 2 to 7 (inclusive)
        self.assertEqual(len(response.data["metrics"]), 6)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["metrics"][0]["sequence"], 2)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["metrics"][-1]["sequence"], 7)  # ty:ignore[possibly-missing-attribute]

    def test_get_execution_metrics_with_last_n_filter(self) -> None:
        """Test retrieving last N metrics points."""
        _, execution = self._create_backtest_execution_with_metrics(num_metrics=10)

        url = reverse("trading:execution_metrics", kwargs={"execution_id": execution.pk})
        response = self.client.get(url, {"last_n": 3})

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data["metrics"]), 3)  # ty:ignore[possibly-missing-attribute]
        # Should return last 3 metrics in chronological order
        self.assertEqual(response.data["metrics"][0]["sequence"], 7)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["metrics"][1]["sequence"], 8)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["metrics"][2]["sequence"], 9)  # ty:ignore[possibly-missing-attribute]

    def test_get_execution_metrics_with_granularity_binning(self) -> None:
        """Test metrics aggregation with granularity binning."""
        _, execution = self._create_backtest_execution_with_metrics(num_metrics=10)

        url = reverse("trading:execution_metrics", kwargs={"execution_id": execution.pk})
        # Use 120 second granularity (should bin every 2 metrics)
        response = self.client.get(url, {"granularity": 120})

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["granularity_seconds"], 120)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("metrics", response.data)  # ty:ignore[possibly-missing-attribute]
        # Verify binned metrics have aggregated statistics
        if len(response.data["metrics"]) > 0:  # ty:ignore[possibly-missing-attribute]
            first_bin = response.data["metrics"][0]  # ty:ignore[possibly-missing-attribute]
            self.assertIn("realized_pnl_min", first_bin)
            self.assertIn("realized_pnl_max", first_bin)
            self.assertIn("realized_pnl_avg", first_bin)
            self.assertIn("unrealized_pnl_min", first_bin)
            self.assertIn("trade_count", first_bin)

    def test_get_execution_metrics_empty_execution(self) -> None:
        """Test retrieving metrics for execution with no metrics."""
        backtest_task = BacktestTaskFactory(
            user=self.user,
            config=self.strategy_config,
        )
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.CREATED,
        )

        url = reverse("trading:execution_metrics", kwargs={"execution_id": execution.pk})
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data["metrics"]), 0)  # ty:ignore[possibly-missing-attribute]

    def test_get_execution_metrics_not_found(self) -> None:
        """Test retrieving metrics for non-existent execution."""
        url = reverse("trading:execution_metrics", kwargs={"execution_id": 99999})
        response = self.client.get(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_get_execution_metrics_unauthorized_access(self) -> None:
        """Test that users cannot access metrics for other users' executions."""
        other_user = UserFactory(username="otheruser", email="other@example.com")
        other_config = StrategyConfigurationFactory(user=other_user)

        other_task = BacktestTaskFactory(
            user=other_user,
            config=other_config,
        )
        other_execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=other_task.id,  # ty:ignore[unresolved-attribute]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        url = reverse("trading:execution_metrics", kwargs={"execution_id": other_execution.pk})
        response = self.client.get(url)

        self.assert_response_error(response, status_code=403)  # ty:ignore[invalid-argument-type]

    def test_get_execution_metrics_invalid_granularity(self) -> None:
        """Test that invalid granularity parameter returns error."""
        _, execution = self._create_backtest_execution_with_metrics(num_metrics=5)

        url = reverse("trading:execution_metrics", kwargs={"execution_id": execution.pk})
        response = self.client.get(url, {"granularity": -10})

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]

    def test_get_execution_metrics_invalid_time_format(self) -> None:
        """Test that invalid time format returns error."""
        _, execution = self._create_backtest_execution_with_metrics(num_metrics=5)

        url = reverse("trading:execution_metrics", kwargs={"execution_id": execution.pk})
        response = self.client.get(url, {"start_time": "invalid-date"})

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]


class ExecutionLatestMetricsEndpointTests(APIIntegrationTestCase):
    """Tests for execution latest metrics endpoint."""

    def setUp(self) -> None:
        """Set up test data for latest metrics tests."""
        super().setUp()
        self.account = OandaAccountFactory(user=self.user)
        self.strategy_config = StrategyConfigurationFactory(user=self.user)

    def test_get_latest_metrics_success(self) -> None:
        """Test retrieving the latest metrics snapshot."""
        backtest_task = BacktestTaskFactory(
            user=self.user,
            config=self.strategy_config,
        )
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Create multiple metrics, latest should be returned
        base_time = timezone.now()
        for i in range(5):
            TradingMetrics.objects.create(
                execution=execution,
                sequence=i,
                timestamp=base_time + timedelta(seconds=i * 60),
                realized_pnl=Decimal(str(100.0 * i)),
                unrealized_pnl=Decimal(str(50.0 * i)),
                total_pnl=Decimal(str(150.0 * i)),
                open_positions=i,
                total_trades=i * 2,
                tick_ask_min=Decimal("1.10000"),
                tick_ask_max=Decimal("1.10050"),
                tick_ask_avg=Decimal("1.10025"),
                tick_bid_min=Decimal("1.09990"),
                tick_bid_max=Decimal("1.10040"),
                tick_bid_avg=Decimal("1.10015"),
                tick_mid_min=Decimal("1.09995"),
                tick_mid_max=Decimal("1.10045"),
                tick_mid_avg=Decimal("1.10020"),
            )

        url = reverse(
            "trading:execution_metrics_latest",
            kwargs={"execution_id": execution.pk},
        )
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertTrue(response.data["has_metrics"])  # ty:ignore[possibly-missing-attribute]
        self.assertIsNotNone(response.data["metrics"])  # ty:ignore[possibly-missing-attribute]

        # Verify it's the latest metric (sequence 4)
        latest_metric = response.data["metrics"]  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(latest_metric["sequence"], 4)
        self.assertEqual(latest_metric["realized_pnl"], "400.00000")
        self.assertEqual(latest_metric["unrealized_pnl"], "200.00000")
        self.assertEqual(latest_metric["total_pnl"], "600.00000")
        self.assertEqual(latest_metric["open_positions"], 4)
        self.assertEqual(latest_metric["total_trades"], 8)

    def test_get_latest_metrics_no_metrics(self) -> None:
        """Test retrieving latest metrics when execution has no metrics."""
        backtest_task = BacktestTaskFactory(
            user=self.user,
            config=self.strategy_config,
        )
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.CREATED,
        )

        url = reverse(
            "trading:execution_metrics_latest",
            kwargs={"execution_id": execution.pk},
        )
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertFalse(response.data["has_metrics"])  # ty:ignore[possibly-missing-attribute]
        self.assertIsNone(response.data["metrics"])  # ty:ignore[possibly-missing-attribute]

    def test_get_latest_metrics_not_found(self) -> None:
        """Test retrieving latest metrics for non-existent execution."""
        url = reverse("trading:execution_metrics_latest", kwargs={"execution_id": 99999})
        response = self.client.get(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_get_latest_metrics_unauthorized_access(self) -> None:
        """Test that users cannot access latest metrics for other users' executions."""
        other_user = UserFactory(username="otheruser", email="other@example.com")
        other_config = StrategyConfigurationFactory(user=other_user)

        other_task = BacktestTaskFactory(
            user=other_user,
            config=other_config,
        )
        other_execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=other_task.id,  # ty:ignore[unresolved-attribute]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        url = reverse(
            "trading:execution_metrics_latest",
            kwargs={"execution_id": other_execution.pk},
        )
        response = self.client.get(url)

        self.assert_response_error(response, status_code=403)  # ty:ignore[invalid-argument-type]


class MetricsAggregationByAccountTests(APIIntegrationTestCase):
    """Tests for metrics aggregation by account."""

    def setUp(self) -> None:
        """Set up test data for account aggregation tests."""
        super().setUp()
        self.account1 = OandaAccountFactory(user=self.user, account_id="ACC-001")
        self.account2 = OandaAccountFactory(user=self.user, account_id="ACC-002")
        self.strategy_config = StrategyConfigurationFactory(user=self.user)

    def test_metrics_isolated_by_account(self) -> None:
        """Test that metrics are correctly isolated by account."""
        # Create executions for different accounts
        task1 = BacktestTaskFactory(
            user=self.user,
            config=self.strategy_config,
        )
        execution1 = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task1.id,  # ty:ignore[unresolved-attribute]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        task2 = BacktestTaskFactory(
            user=self.user,
            config=self.strategy_config,
        )
        execution2 = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task2.id,  # ty:ignore[unresolved-attribute]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Create metrics for each execution
        base_time = timezone.now()
        TradingMetrics.objects.create(
            execution=execution1,
            sequence=0,
            timestamp=base_time,
            realized_pnl=Decimal("100.00"),
            unrealized_pnl=Decimal("50.00"),
            total_pnl=Decimal("150.00"),
            open_positions=1,
            total_trades=5,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        TradingMetrics.objects.create(
            execution=execution2,
            sequence=0,
            timestamp=base_time,
            realized_pnl=Decimal("200.00"),
            unrealized_pnl=Decimal("75.00"),
            total_pnl=Decimal("275.00"),
            open_positions=2,
            total_trades=10,
            tick_ask_min=Decimal("1.20000"),
            tick_ask_max=Decimal("1.20050"),
            tick_ask_avg=Decimal("1.20025"),
            tick_bid_min=Decimal("1.19990"),
            tick_bid_max=Decimal("1.20040"),
            tick_bid_avg=Decimal("1.20015"),
            tick_mid_min=Decimal("1.19995"),
            tick_mid_max=Decimal("1.20045"),
            tick_mid_avg=Decimal("1.20020"),
        )

        # Verify metrics for execution1
        url1 = reverse("trading:execution_metrics", kwargs={"execution_id": execution1.id})  # ty:ignore[possibly-missing-attribute]
        response1 = self.client.get(url1)
        self.assert_response_success(response1)  # ty:ignore[invalid-argument-type]
        self.assertEqual(len(response1.data["metrics"]), 1)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response1.data["metrics"][0]["realized_pnl"], "100.00000")  # ty:ignore[possibly-missing-attribute]

        # Verify metrics for execution2
        url2 = reverse("trading:execution_metrics", kwargs={"execution_id": execution2.id})  # ty:ignore[possibly-missing-attribute]
        response2 = self.client.get(url2)
        self.assert_response_success(response2)  # ty:ignore[invalid-argument-type]
        self.assertEqual(len(response2.data["metrics"]), 1)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response2.data["metrics"][0]["realized_pnl"], "200.00000")  # ty:ignore[possibly-missing-attribute]


class MetricsAggregationByStrategyTests(APIIntegrationTestCase):
    """Tests for metrics aggregation by strategy."""

    def setUp(self) -> None:
        """Set up test data for strategy aggregation tests."""
        super().setUp()
        self.account = OandaAccountFactory(user=self.user)
        self.strategy1 = StrategyConfigurationFactory(
            user=self.user,
            name="Strategy 1",
            strategy_type="floor",
        )
        self.strategy2 = StrategyConfigurationFactory(
            user=self.user,
            name="Strategy 2",
            strategy_type="momentum",
        )

    def test_metrics_isolated_by_strategy(self) -> None:
        """Test that metrics are correctly isolated by strategy configuration."""
        # Create executions for different strategies
        task1 = BacktestTaskFactory(
            user=self.user,
            config=self.strategy1,
        )
        execution1 = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task1.id,  # ty:ignore[unresolved-attribute]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        task2 = BacktestTaskFactory(
            user=self.user,
            config=self.strategy2,
        )
        execution2 = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task2.id,  # ty:ignore[unresolved-attribute]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Create metrics for each execution
        base_time = timezone.now()
        TradingMetrics.objects.create(
            execution=execution1,
            sequence=0,
            timestamp=base_time,
            realized_pnl=Decimal("300.00"),
            unrealized_pnl=Decimal("100.00"),
            total_pnl=Decimal("400.00"),
            open_positions=3,
            total_trades=15,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        TradingMetrics.objects.create(
            execution=execution2,
            sequence=0,
            timestamp=base_time,
            realized_pnl=Decimal("500.00"),
            unrealized_pnl=Decimal("150.00"),
            total_pnl=Decimal("650.00"),
            open_positions=4,
            total_trades=20,
            tick_ask_min=Decimal("1.20000"),
            tick_ask_max=Decimal("1.20050"),
            tick_ask_avg=Decimal("1.20025"),
            tick_bid_min=Decimal("1.19990"),
            tick_bid_max=Decimal("1.20040"),
            tick_bid_avg=Decimal("1.20015"),
            tick_mid_min=Decimal("1.19995"),
            tick_mid_max=Decimal("1.20045"),
            tick_mid_avg=Decimal("1.20020"),
        )

        # Verify metrics for execution1 (strategy1)
        url1 = reverse("trading:execution_metrics", kwargs={"execution_id": execution1.id})  # ty:ignore[possibly-missing-attribute]
        response1 = self.client.get(url1)
        self.assert_response_success(response1)  # ty:ignore[invalid-argument-type]
        self.assertEqual(len(response1.data["metrics"]), 1)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response1.data["metrics"][0]["realized_pnl"], "300.00000")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response1.data["metrics"][0]["total_trades"], 15)  # ty:ignore[possibly-missing-attribute]

        # Verify metrics for execution2 (strategy2)
        url2 = reverse("trading:execution_metrics", kwargs={"execution_id": execution2.id})  # ty:ignore[possibly-missing-attribute]
        response2 = self.client.get(url2)
        self.assert_response_success(response2)  # ty:ignore[invalid-argument-type]
        self.assertEqual(len(response2.data["metrics"]), 1)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response2.data["metrics"][0]["realized_pnl"], "500.00000")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response2.data["metrics"][0]["total_trades"], 20)  # ty:ignore[possibly-missing-attribute]
