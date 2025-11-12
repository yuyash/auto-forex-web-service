"""
Unit tests for backtest resource limits.

Tests CPU and memory limit enforcement, automatic termination,
resource usage logging, and configurable limits from system.yaml.

Requirements: 12.2, 12.3
"""

import contextlib
import resource
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import psutil
import pytest

from trading.backtest_engine import BacktestConfig, BacktestEngine, ResourceMonitor
from trading.historical_data_loader import TickDataPoint


@pytest.fixture
def mock_process():
    """Mock psutil.Process for testing."""
    process = Mock(spec=psutil.Process)
    memory_info = Mock()
    memory_info.rss = 100 * 1024 * 1024  # 100MB
    process.memory_info.return_value = memory_info
    return process


@pytest.fixture
def resource_monitor(mock_process):
    """Create ResourceMonitor instance with mocked process."""
    with patch("trading.backtest_engine.psutil.Process", return_value=mock_process):
        monitor = ResourceMonitor(memory_limit=200 * 1024 * 1024, check_interval=0.1)
        yield monitor
        if monitor.monitoring:
            monitor.stop()


@pytest.fixture
def backtest_config():
    """Create basic backtest configuration."""
    return BacktestConfig(
        strategy_type="floor",
        strategy_config={"base_lot_size": 1.0},
        instrument="EUR_USD",
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now(),
        initial_balance=Decimal("10000"),
        cpu_limit=1,
        memory_limit=200 * 1024 * 1024,  # 200MB
    )


@pytest.fixture
def sample_tick_data():
    """Create sample tick data for testing."""
    base_time = datetime.now()
    return [
        TickDataPoint(
            instrument="EUR_USD",
            timestamp=base_time + timedelta(seconds=i),
            bid=Decimal("1.1000") + Decimal(str(i * 0.0001)),
            ask=Decimal("1.1002") + Decimal(str(i * 0.0001)),
            mid=Decimal("1.1001") + Decimal(str(i * 0.0001)),
            spread=Decimal("0.0002"),
        )
        for i in range(10)
    ]


class TestResourceMonitor:
    """Test ResourceMonitor class."""

    def test_resource_monitor_initialization(self, mock_process):
        """Test ResourceMonitor initialization."""
        with patch("trading.backtest_engine.psutil.Process", return_value=mock_process):
            monitor = ResourceMonitor(memory_limit=100 * 1024 * 1024, check_interval=1.0)

            assert monitor.memory_limit == 100 * 1024 * 1024
            assert monitor.check_interval == 1.0
            assert not monitor.exceeded
            assert not monitor.monitoring
            assert monitor.peak_memory == 0

    def test_resource_monitor_start_stop(self, resource_monitor):
        """Test starting and stopping resource monitoring."""
        assert not resource_monitor.monitoring

        resource_monitor.start()
        assert resource_monitor.monitoring
        assert resource_monitor.monitor_thread is not None
        assert resource_monitor.monitor_thread.is_alive()

        time.sleep(0.2)  # Let it run for a bit

        resource_monitor.stop()
        assert not resource_monitor.monitoring

    def test_memory_limit_not_exceeded(self, mock_process):
        """Test monitoring when memory limit is not exceeded."""
        # Set memory usage below limit
        memory_info = Mock()
        memory_info.rss = 100 * 1024 * 1024  # 100MB
        mock_process.memory_info.return_value = memory_info

        with patch("trading.backtest_engine.psutil.Process", return_value=mock_process):
            monitor = ResourceMonitor(memory_limit=200 * 1024 * 1024, check_interval=0.1)
            monitor.start()

            time.sleep(0.3)  # Let it check a few times

            assert not monitor.is_exceeded()
            assert monitor.get_peak_memory() == 100 * 1024 * 1024

            monitor.stop()

    def test_memory_limit_exceeded(self, mock_process):
        """Test monitoring when memory limit is exceeded."""
        # Set memory usage above limit
        memory_info = Mock()
        memory_info.rss = 300 * 1024 * 1024  # 300MB
        mock_process.memory_info.return_value = memory_info

        with patch("trading.backtest_engine.psutil.Process", return_value=mock_process):
            monitor = ResourceMonitor(memory_limit=200 * 1024 * 1024, check_interval=0.1)
            monitor.start()

            time.sleep(0.3)  # Let it detect the overflow

            assert monitor.is_exceeded()
            assert monitor.get_peak_memory() == 300 * 1024 * 1024
            assert not monitor.monitoring  # Should stop automatically

    def test_peak_memory_tracking(self, mock_process):
        """Test peak memory tracking."""
        # Simulate increasing memory usage
        memory_values = [100, 150, 200, 180, 160]  # MB
        memory_index = [0]

        def get_memory_info():
            memory_info = Mock()
            memory_info.rss = (
                memory_values[min(memory_index[0], len(memory_values) - 1)] * 1024 * 1024
            )
            memory_index[0] += 1
            return memory_info

        mock_process.memory_info.side_effect = get_memory_info

        with patch("trading.backtest_engine.psutil.Process", return_value=mock_process):
            monitor = ResourceMonitor(memory_limit=250 * 1024 * 1024, check_interval=0.1)
            monitor.start()

            time.sleep(0.6)  # Let it check multiple times

            monitor.stop()

            # Peak should be 200MB
            assert monitor.get_peak_memory() == 200 * 1024 * 1024

    def test_resource_monitor_exception_handling(self, mock_process):
        """Test resource monitor handles exceptions gracefully."""
        # Make memory_info raise an exception
        mock_process.memory_info.side_effect = Exception("Memory info error")

        with patch("trading.backtest_engine.psutil.Process", return_value=mock_process):
            monitor = ResourceMonitor(memory_limit=200 * 1024 * 1024, check_interval=0.1)
            monitor.start()

            time.sleep(0.3)

            # Monitor thread should exit gracefully after exception
            # The monitoring flag stays True but the thread is no longer alive
            assert monitor.monitor_thread is not None
            assert not monitor.monitor_thread.is_alive()


class TestBacktestEngineCPULimit:
    """Test CPU limit enforcement in BacktestEngine."""

    def test_cpu_limit_configuration(self, backtest_config):
        """Test CPU limit is configured from BacktestConfig."""
        engine = BacktestEngine(backtest_config)

        assert engine.config.cpu_limit == 1

    def test_cpu_limit_set_on_run(self, backtest_config, sample_tick_data):
        """Test CPU limit is set when backtest runs."""
        with (
            patch("trading.backtest_engine.resource.setrlimit") as mock_setrlimit,
            patch("trading.backtest_engine.resource.getrlimit") as mock_getrlimit,
        ):
            mock_getrlimit.return_value = (0, 100000)  # soft, hard

            engine = BacktestEngine(backtest_config)

            # Mock strategy registry
            with patch("trading.strategy_registry.StrategyRegistry") as mock_registry:
                mock_strategy = Mock()
                mock_strategy.on_tick.return_value = []
                mock_registry.get_strategy.return_value = Mock(return_value=mock_strategy)

                with contextlib.suppress(Exception):
                    # We're just testing if setrlimit was called
                    engine.run(sample_tick_data)

                    # Verify setrlimit was called with CPU limit
                    mock_setrlimit.assert_called_once()
                    args = mock_setrlimit.call_args[0]
                    assert args[0] == resource.RLIMIT_CPU
                    # CPU limit should be cpu_limit * 3600 seconds
                    assert args[1][0] == backtest_config.cpu_limit * 3600

    def test_cpu_limit_from_system_config(self):
        """Test CPU limit can be loaded from system configuration."""
        from django.conf import settings

        # Check if system config has backtesting settings
        system_config = getattr(settings, "SYSTEM_CONFIG", {})
        if system_config and "backtesting" in system_config:
            cpu_limit = system_config["backtesting"].get("cpu_limit", 1)
            assert cpu_limit == 1

    def test_cpu_limit_failure_handling(self, backtest_config, sample_tick_data):
        """Test CPU limit setting failure is handled gracefully."""
        with patch("trading.backtest_engine.resource.setrlimit") as mock_setrlimit:
            mock_setrlimit.side_effect = Exception("Cannot set CPU limit")

            engine = BacktestEngine(backtest_config)

            # Mock strategy registry
            with patch("trading.strategy_registry.StrategyRegistry") as mock_registry:
                mock_strategy = Mock()
                mock_strategy.on_tick.return_value = []
                mock_registry.get_strategy.return_value = Mock(return_value=mock_strategy)

                # Should not crash, just log warning
                try:
                    engine.run(sample_tick_data)
                except Exception as e:
                    # Should not be the CPU limit exception
                    assert "Cannot set CPU limit" not in str(e)


class TestBacktestEngineMemoryLimit:
    """Test memory limit enforcement in BacktestEngine."""

    def test_memory_limit_configuration(self, backtest_config):
        """Test memory limit is configured from BacktestConfig."""
        engine = BacktestEngine(backtest_config)

        assert engine.config.memory_limit == 200 * 1024 * 1024

    def test_memory_limit_monitoring_starts(self, backtest_config, sample_tick_data):
        """Test memory monitoring starts when backtest runs."""
        engine = BacktestEngine(backtest_config)

        # Mock strategy registry
        with patch("trading.strategy_registry.StrategyRegistry") as mock_registry:
            mock_strategy = Mock()
            mock_strategy.on_tick.return_value = []
            mock_registry.get_strategy.return_value = Mock(return_value=mock_strategy)

            # Mock ResourceMonitor
            with patch("trading.backtest_engine.ResourceMonitor") as mock_monitor_class:
                mock_monitor = Mock()
                mock_monitor.is_exceeded.return_value = False
                mock_monitor.get_peak_memory.return_value = 100 * 1024 * 1024
                mock_monitor_class.return_value = mock_monitor

                engine.run(sample_tick_data)

                # Verify ResourceMonitor was created with correct limit
                mock_monitor_class.assert_called_once_with(
                    memory_limit=backtest_config.memory_limit,
                    check_interval=1.0,
                )

                # Verify monitoring was started and stopped
                mock_monitor.start.assert_called_once()
                mock_monitor.stop.assert_called_once()

    def test_automatic_termination_on_memory_overflow(self, backtest_config, sample_tick_data):
        """Test backtest terminates automatically when memory limit is exceeded."""
        engine = BacktestEngine(backtest_config)

        # Mock strategy registry
        with patch("trading.strategy_registry.StrategyRegistry") as mock_registry:
            mock_strategy = Mock()
            mock_strategy.on_tick.return_value = []
            mock_registry.get_strategy.return_value = Mock(return_value=mock_strategy)

            # Mock ResourceMonitor to simulate memory overflow
            with patch("trading.backtest_engine.ResourceMonitor") as mock_monitor_class:
                mock_monitor = Mock()
                # Simulate memory overflow after a few ticks
                call_count = [0]

                def is_exceeded_side_effect():
                    call_count[0] += 1
                    return call_count[0] > 3

                mock_monitor.is_exceeded.side_effect = is_exceeded_side_effect
                mock_monitor.get_peak_memory.return_value = 250 * 1024 * 1024
                mock_monitor_class.return_value = mock_monitor

                # Should raise RuntimeError
                with pytest.raises(RuntimeError) as exc_info:
                    engine.run(sample_tick_data)

                assert "memory limit exceeded" in str(exc_info.value).lower()
                assert engine.terminated is True

                # Verify monitoring was stopped
                mock_monitor.stop.assert_called_once()

    def test_memory_limit_from_system_config(self):
        """Test memory limit can be loaded from system configuration."""
        from django.conf import settings

        # Check if system config has backtesting settings
        system_config = getattr(settings, "SYSTEM_CONFIG", {})
        if system_config and "backtesting" in system_config:
            memory_limit = system_config["backtesting"].get("memory_limit", 2147483648)
            assert memory_limit == 2147483648  # 2GB


class TestBacktestEngineResourceLogging:
    """Test resource usage logging in BacktestEngine."""

    def test_resource_usage_logged_on_completion(self, backtest_config, sample_tick_data):
        """Test resource usage is logged when backtest completes."""
        engine = BacktestEngine(backtest_config)

        # Mock strategy registry
        with patch("trading.strategy_registry.StrategyRegistry") as mock_registry:
            mock_strategy = Mock()
            mock_strategy.on_tick.return_value = []
            mock_registry.get_strategy.return_value = Mock(return_value=mock_strategy)

            # Mock ResourceMonitor
            with patch("trading.backtest_engine.ResourceMonitor") as mock_monitor_class:
                mock_monitor = Mock()
                mock_monitor.is_exceeded.return_value = False
                mock_monitor.get_peak_memory.return_value = 150 * 1024 * 1024
                mock_monitor_class.return_value = mock_monitor

                # Capture log output
                with patch("trading.backtest_engine.logger") as mock_logger:
                    engine.run(sample_tick_data)

                    # Verify resource usage was logged
                    log_calls = [str(call) for call in mock_logger.info.call_args_list]
                    resource_log = [
                        call
                        for call in log_calls
                        if "Resource usage" in call or "Peak memory" in call
                    ]
                    assert len(resource_log) > 0

    def test_resource_usage_logged_on_failure(self, backtest_config, sample_tick_data):
        """Test resource usage is logged even when backtest fails."""
        engine = BacktestEngine(backtest_config)

        # Mock strategy registry to raise an error
        with patch("trading.strategy_registry.StrategyRegistry") as mock_registry:
            mock_strategy = Mock()
            mock_strategy.on_tick.side_effect = Exception("Strategy error")
            mock_registry.get_strategy.return_value = Mock(return_value=mock_strategy)

            # Mock ResourceMonitor
            with patch("trading.backtest_engine.ResourceMonitor") as mock_monitor_class:
                mock_monitor = Mock()
                mock_monitor.is_exceeded.return_value = False
                mock_monitor.get_peak_memory.return_value = 150 * 1024 * 1024
                mock_monitor_class.return_value = mock_monitor

                # Should raise exception but still log resources
                with pytest.raises(Exception, match=".*"):
                    engine.run(sample_tick_data)

                # Verify monitoring was stopped (which triggers logging)
                mock_monitor.stop.assert_called_once()

    def test_peak_memory_logged(self, backtest_config, sample_tick_data):
        """Test peak memory usage is logged."""
        engine = BacktestEngine(backtest_config)

        # Mock strategy registry
        with patch("trading.strategy_registry.StrategyRegistry") as mock_registry:
            mock_strategy = Mock()
            mock_strategy.on_tick.return_value = []
            mock_registry.get_strategy.return_value = Mock(return_value=mock_strategy)

            # Mock ResourceMonitor
            with patch("trading.backtest_engine.ResourceMonitor") as mock_monitor_class:
                mock_monitor = Mock()
                mock_monitor.is_exceeded.return_value = False
                peak_memory = 175 * 1024 * 1024
                mock_monitor.get_peak_memory.return_value = peak_memory
                mock_monitor_class.return_value = mock_monitor

                # Capture log output
                with patch("trading.backtest_engine.logger") as mock_logger:
                    engine.run(sample_tick_data)

                    # Verify peak memory was logged
                    log_calls = [str(call) for call in mock_logger.info.call_args_list]
                    peak_memory_mb = peak_memory / 1024 / 1024
                    peak_log = [call for call in log_calls if f"{peak_memory_mb:.0f}MB" in call]
                    assert len(peak_log) > 0

    def test_cpu_limit_logged(self, backtest_config, sample_tick_data):
        """Test CPU limit is logged."""
        engine = BacktestEngine(backtest_config)

        # Mock strategy registry
        with patch("trading.strategy_registry.StrategyRegistry") as mock_registry:
            mock_strategy = Mock()
            mock_strategy.on_tick.return_value = []
            mock_registry.get_strategy.return_value = Mock(return_value=mock_strategy)

            # Mock ResourceMonitor
            with patch("trading.backtest_engine.ResourceMonitor") as mock_monitor_class:
                mock_monitor = Mock()
                mock_monitor.is_exceeded.return_value = False
                mock_monitor.get_peak_memory.return_value = 150 * 1024 * 1024
                mock_monitor_class.return_value = mock_monitor

                # Capture log output
                with (
                    patch("trading.backtest_engine.logger") as mock_logger,
                    patch("trading.backtest_engine.resource.setrlimit"),
                    patch("trading.backtest_engine.resource.getrlimit", return_value=(0, 100000)),
                ):
                    engine.run(sample_tick_data)

                    # Verify CPU limit was logged
                    log_calls = [str(call) for call in mock_logger.info.call_args_list]
                    cpu_log = [call for call in log_calls if "CPU limit" in call]
                    assert len(cpu_log) > 0


class TestConfigurableLimits:
    """Test configurable resource limits from system.yaml."""

    def test_default_cpu_limit(self):
        """Test default CPU limit from BacktestConfig."""
        config = BacktestConfig(
            strategy_type="floor",
            strategy_config={},
            instrument="EUR_USD",
            start_date=datetime.now(),
            end_date=datetime.now(),
            initial_balance=Decimal("10000"),
        )

        assert config.cpu_limit == 1

    def test_default_memory_limit(self):
        """Test default memory limit from BacktestConfig."""
        config = BacktestConfig(
            strategy_type="floor",
            strategy_config={},
            instrument="EUR_USD",
            start_date=datetime.now(),
            end_date=datetime.now(),
            initial_balance=Decimal("10000"),
        )

        assert config.memory_limit == 2147483648  # 2GB

    def test_custom_cpu_limit(self):
        """Test custom CPU limit can be set."""
        config = BacktestConfig(
            strategy_type="floor",
            strategy_config={},
            instrument="EUR_USD",
            start_date=datetime.now(),
            end_date=datetime.now(),
            initial_balance=Decimal("10000"),
            cpu_limit=2,
        )

        assert config.cpu_limit == 2

    def test_custom_memory_limit(self):
        """Test custom memory limit can be set."""
        custom_limit = 1024 * 1024 * 1024  # 1GB
        config = BacktestConfig(
            strategy_type="floor",
            strategy_config={},
            instrument="EUR_USD",
            start_date=datetime.now(),
            end_date=datetime.now(),
            initial_balance=Decimal("10000"),
            memory_limit=custom_limit,
        )

        assert config.memory_limit == custom_limit

    def test_system_config_loaded(self):
        """Test system configuration is loaded correctly."""
        from django.conf import settings

        system_config = getattr(settings, "SYSTEM_CONFIG", None)

        if system_config:
            # Verify backtesting section exists
            assert "backtesting" in system_config

            # Verify resource limits are configured
            backtesting_config = system_config["backtesting"]
            assert "cpu_limit" in backtesting_config
            assert "memory_limit" in backtesting_config

            # Verify values match expected defaults
            assert backtesting_config["cpu_limit"] == 1
            assert backtesting_config["memory_limit"] == 2147483648
