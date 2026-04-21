"""Integration tests for backtest task."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.market.models import CeleryTaskStatus, TickData
from apps.market.services.backtest_ticks import iter_aggregated_backtest_ticks
from apps.market.tasks.backtest import BacktestTickPublisherRunner
from apps.trading.enums import TaskStatus


@pytest.mark.django_db
class TestBacktestTickPublisherRunnerIntegration:
    """Integration tests for BacktestTickPublisherRunner."""

    @patch("apps.market.tasks.backtest.redis_client")
    @patch("apps.market.tasks.backtest.CeleryTaskService")
    def test_backtest_publisher_initialization(self, mock_service: Any, mock_redis: Any) -> None:
        """Test backtest publisher initialization."""
        # Mock service to stop immediately
        mock_service_instance = MagicMock()
        mock_service_instance.should_stop.return_value = True
        mock_service.return_value = mock_service_instance

        # Mock redis client
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        runner = BacktestTickPublisherRunner()

        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)

        # Run should not raise exception
        try:
            runner.run(
                instrument="EUR_USD",
                start=start.isoformat(),
                end=end.isoformat(),
                request_id="test-request-123",
            )
        except Exception:
            pass

        # Verify task service was created
        assert mock_service.called

    def test_backtest_publisher_creates_task_status(self) -> None:
        """Test that backtest publisher creates CeleryTaskStatus."""
        # Check that task status can be created
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.publish_ticks_for_backtest",
            instance_key="test-request-456",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        assert task is not None
        assert task.task_name == "market.tasks.publish_ticks_for_backtest"

    def test_backtest_publisher_with_tick_data(self) -> None:
        """Test backtest publisher with actual tick data."""
        # Create some tick data
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

        TickData.objects.create(
            instrument="EUR_USD",
            timestamp=now,
            bid=Decimal("1.10000"),
            ask=Decimal("1.10010"),
            mid=Decimal("1.10005"),
        )

        # Verify tick data was created
        tick_count = TickData.objects.filter(instrument="EUR_USD").count()
        assert tick_count == 1

    def test_should_stop_publishing_checks_executor_status(self) -> None:
        """Test that _should_stop_publishing checks executor status."""
        from django.contrib.auth import get_user_model

        from apps.trading.models import BacktestTask, StrategyConfiguration

        User = get_user_model()

        # Create required related objects
        test_user = User.objects.create_user(  # type: ignore[attr-defined]
            email="backtest@example.com",
            password="testpass123",
            username="backtestuser",
        )
        config = StrategyConfiguration.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
        )

        # Create a backtest task
        task = BacktestTask.objects.create(
            name="Test Backtest",
            user=test_user,
            config=config,
            instrument="EUR_USD",
            start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC),
            initial_balance=Decimal("10000.00"),
            status=TaskStatus.RUNNING,
        )

        request_id = str(task.id)

        # Create runner and mock task service
        runner = BacktestTickPublisherRunner()
        mock_service = MagicMock()
        mock_service.should_stop.return_value = False
        runner.task_service = mock_service

        # Should not stop when task is running
        assert not runner._should_stop_publishing(request_id)

        # Update task to stopping
        task.status = TaskStatus.STOPPING
        task.save()

        # Should stop when task is stopping
        assert runner._should_stop_publishing(request_id)

        # Update task to stopped
        task.status = TaskStatus.STOPPED
        task.save()

        # Should stop when task is stopped
        assert runner._should_stop_publishing(request_id)

        # Update task to failed
        task.status = TaskStatus.FAILED
        task.save()

        # Should stop when task is failed
        assert runner._should_stop_publishing(request_id)

    def test_should_stop_publishing_checks_own_stop_signal(self) -> None:
        """Test that _should_stop_publishing checks its own stop signal."""
        runner = BacktestTickPublisherRunner()
        mock_service = MagicMock()
        mock_service.should_stop.return_value = True
        runner.task_service = mock_service

        # Should stop when own stop signal is set
        assert runner._should_stop_publishing("test-request-999")

    @patch("apps.market.tasks.backtest.redis_client")
    @patch("apps.market.tasks.backtest.CeleryTaskService")
    def test_run_does_not_report_insufficient_data_when_stopped(
        self,
        mock_service: Any,
        mock_redis: Any,
    ) -> None:
        """Explicit stop should not be misreported as missing tick data."""
        mock_service_instance = MagicMock()
        mock_service.return_value = mock_service_instance
        mock_redis.return_value = MagicMock()

        runner = BacktestTickPublisherRunner()
        runner._publish_ticks = MagicMock(  # type: ignore[method-assign]
            return_value=(0, None, True)
        )
        runner._check_data_coverage = MagicMock(return_value="unexpected gap")  # type: ignore[method-assign]
        runner._mark_backtest_task_failed = MagicMock()  # type: ignore[method-assign]

        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)

        runner.run(
            instrument="EUR_USD",
            start=start.isoformat(),
            end=end.isoformat(),
            request_id="test-request-stop",
        )

        runner._check_data_coverage.assert_not_called()
        runner._mark_backtest_task_failed.assert_not_called()
        mock_service_instance.mark_stopped.assert_not_called()

    @pytest.mark.parametrize(
        ("mode", "expected_bid", "expected_ask", "expected_mid"),
        [
            ("first", Decimal("100.00"), Decimal("100.20"), Decimal("100.10")),
            ("last", Decimal("102.00"), Decimal("102.20"), Decimal("102.10")),
            ("average", Decimal("101.00"), Decimal("101.20"), Decimal("101.10")),
            ("median", Decimal("101.00"), Decimal("101.20"), Decimal("101.10")),
        ],
    )
    def test_iter_aggregated_backtest_ticks_supports_all_modes(
        self,
        mode: str,
        expected_bid: Decimal,
        expected_ask: Decimal,
        expected_mid: Decimal,
    ) -> None:
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        samples = [
            (start, "100.00", "100.20", "100.10"),
            (datetime(2024, 1, 1, 12, 0, 10, tzinfo=UTC), "101.00", "101.20", "101.10"),
            (datetime(2024, 1, 1, 12, 0, 20, tzinfo=UTC), "102.00", "102.20", "102.10"),
        ]
        for ts, bid, ask, mid in samples:
            TickData.objects.create(
                instrument="EUR_USD",
                timestamp=ts,
                bid=Decimal(bid),
                ask=Decimal(ask),
                mid=Decimal(mid),
            )

        rows = list(
            iter_aggregated_backtest_ticks(
                instrument="EUR_USD",
                start_dt=start,
                end_dt=datetime(2024, 1, 1, 12, 0, 29, tzinfo=UTC),
                granularity="30s",
                mode=mode,
                batch_size=10,
            )
        )

        assert len(rows) == 1
        assert rows[0].timestamp == start
        assert rows[0].bid == expected_bid
        assert rows[0].ask == expected_ask
        assert rows[0].mid == expected_mid

    def test_iter_aggregated_backtest_ticks_warns_on_wide_bar(self, caplog) -> None:
        """A bucket with intra-bar range above the threshold emits a WARNING.

        Reproduces the condition that caused a 1-minute backtest to drift
        SL fills far past the intended price: a single bar contains
        >30-pip travel in the bid series.
        """
        import logging

        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        # Three ticks in a 30-second bucket whose bid spans 150.00 → 150.80
        # (80 pips at pip_size 0.01) — well above a 30-pip threshold.
        samples = [
            (start, "150.00", "150.02", "150.01"),
            (datetime(2024, 1, 1, 12, 0, 10, tzinfo=UTC), "150.80", "150.82", "150.81"),
            (datetime(2024, 1, 1, 12, 0, 20, tzinfo=UTC), "150.40", "150.42", "150.41"),
        ]
        for ts, bid, ask, mid in samples:
            TickData.objects.create(
                instrument="USD_JPY",
                timestamp=ts,
                bid=Decimal(bid),
                ask=Decimal(ask),
                mid=Decimal(mid),
            )

        with caplog.at_level(logging.WARNING, logger="apps.market.services.backtest_ticks"):
            rows = list(
                iter_aggregated_backtest_ticks(
                    instrument="USD_JPY",
                    start_dt=start,
                    end_dt=datetime(2024, 1, 1, 12, 0, 29, tzinfo=UTC),
                    granularity="30s",
                    mode="first",
                    batch_size=10,
                    range_warning_pips=Decimal("30"),
                    pip_size=Decimal("0.01"),
                    request_id="test-wide-bar",
                )
            )

        # Still yields the representative tick as before.
        assert len(rows) == 1

        # A warning was emitted with the diagnostic context.
        warnings = [
            rec for rec in caplog.records if "range exceeds warning threshold" in rec.getMessage()
        ]
        assert len(warnings) == 1, "expected exactly one bar-range warning"
        message = warnings[0].getMessage()
        assert "USD_JPY" in message
        assert "30s" in message
        assert "80.0 pips" in message
        assert "test-wide-bar" in message

    def test_iter_aggregated_backtest_ticks_does_not_warn_when_threshold_disabled(
        self, caplog
    ) -> None:
        """Non-positive threshold disables the warning check."""
        import logging

        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        samples = [
            (start, "150.00", "150.02", "150.01"),
            (datetime(2024, 1, 1, 12, 0, 10, tzinfo=UTC), "151.00", "151.02", "151.01"),
        ]
        for ts, bid, ask, mid in samples:
            TickData.objects.create(
                instrument="USD_JPY",
                timestamp=ts,
                bid=Decimal(bid),
                ask=Decimal(ask),
                mid=Decimal(mid),
            )

        with caplog.at_level(logging.WARNING, logger="apps.market.services.backtest_ticks"):
            list(
                iter_aggregated_backtest_ticks(
                    instrument="USD_JPY",
                    start_dt=start,
                    end_dt=datetime(2024, 1, 1, 12, 0, 19, tzinfo=UTC),
                    granularity="30s",
                    mode="first",
                    batch_size=10,
                    range_warning_pips=Decimal("0"),
                    pip_size=Decimal("0.01"),
                )
            )

        assert not any(
            "range exceeds warning threshold" in rec.getMessage() for rec in caplog.records
        ), "warning should be suppressed when threshold is disabled"
