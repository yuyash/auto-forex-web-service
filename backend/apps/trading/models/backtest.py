"""Backtest task model."""

from decimal import Decimal
from typing import Any

from django.db import models

from apps.trading.enums import DataSource, TaskStatus
from apps.trading.models.base import ExecutableTaskModel


class BacktestTaskManager(models.Manager["BacktestTask"]):
    """Custom manager for BacktestTask model."""

    def for_user(self, user: Any) -> models.QuerySet["BacktestTask"]:
        """Get backtest tasks for a specific user."""
        return self.filter(user=user)

    def running(self) -> models.QuerySet["BacktestTask"]:
        """Get all running backtest tasks."""
        return self.filter(status=TaskStatus.RUNNING)

    def completed(self) -> models.QuerySet["BacktestTask"]:
        """Get all completed backtest tasks."""
        return self.filter(status=TaskStatus.COMPLETED)

    def by_config(self, config: Any) -> models.QuerySet["BacktestTask"]:
        """Get backtest tasks using a specific strategy configuration."""
        return self.filter(config=config)


class BacktestTask(ExecutableTaskModel):
    """
    Persistent backtesting task with reusable configuration.

    A BacktestTask represents a backtesting operation with specific configuration,
    data source, and time range. Tasks can be started, stopped, and rerun multiple
    times, with each execution tracked separately.

    Inherits UUID primary key and timestamps from UUIDModel.
    """

    class TickGranularity(models.TextChoices):
        """Replay granularity for historical tick streams."""

        TICK = "tick", "All Ticks"
        SECOND_1 = "1s", "1 Second"
        SECOND_10 = "10s", "10 Seconds"
        SECOND_15 = "15s", "15 Seconds"
        SECOND_30 = "30s", "30 Seconds"
        MINUTE_1 = "1m", "1 Minute"
        MINUTE_5 = "5m", "5 Minutes"
        MINUTE_15 = "15m", "15 Minutes"
        MINUTE_30 = "30m", "30 Minutes"
        HOUR_1 = "1h", "1 Hour"

    class TickWindowValueMode(models.TextChoices):
        """Representative value used for aggregated tick windows."""

        FIRST = "first", "First Tick"
        LAST = "last", "Last Tick"
        AVERAGE = "average", "Average"
        MEDIAN = "median", "Median"

    objects = BacktestTaskManager()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="backtest_tasks",
        help_text="User who created this backtest task",
    )
    config = models.ForeignKey(
        "StrategyConfiguration",
        on_delete=models.PROTECT,
        related_name="backtest_tasks",
        help_text="Strategy configuration used by this task",
    )
    data_source = models.CharField(
        max_length=20,
        choices=DataSource.choices,
        default=DataSource.POSTGRESQL,
        help_text="Data source for historical tick data",
    )
    start_time = models.DateTimeField(
        help_text="Start time for backtest period",
    )
    end_time = models.DateTimeField(
        help_text="End time for backtest period",
    )
    account_currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Account base currency (e.g., USD, JPY)",
    )
    display_currency = models.CharField(
        max_length=3,
        blank=True,
        default="",
        help_text="Preferred currency for displaying balances and PnL. Empty uses account currency.",
    )
    initial_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("10000"),
        help_text="Initial account balance for backtest",
    )
    commission_per_trade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Commission to apply per trade",
    )
    instrument = models.CharField(
        max_length=20,
        default="USD_JPY",
        help_text="Trading instrument (e.g., EUR_USD, USD_JPY)",
    )
    pip_size = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        default=None,
        help_text="Pip size for the instrument (e.g., 0.0001 for EUR_USD, 0.01 for USD_JPY). If not provided, will be fetched from OANDA account.",
    )
    hedging_enabled = models.BooleanField(
        default=True,
        help_text="Allow simultaneous long and short positions (hedging) during backtest.",
    )
    tick_granularity = models.CharField(
        max_length=8,
        choices=TickGranularity.choices,
        default=TickGranularity.TICK,
        help_text=(
            "Tick replay granularity for backtests. "
            "Use 'tick' for full tick-by-tick replay, or a time bucket such as '1s' or '1m'."
        ),
    )
    tick_window_value_mode = models.CharField(
        max_length=16,
        choices=TickWindowValueMode.choices,
        default=TickWindowValueMode.LAST,
        help_text=(
            "Representative value to use when replay granularity is aggregated. "
            "Ignored when tick_granularity='tick'."
        ),
    )
    # Market close schedule applied to backtests when evaluating market-idle
    # thresholds.  When ``market_close_enabled`` is False the replay ignores
    # market-closed windows (pre_close / resume_delay become no-ops) and the
    # strategy receives every tick regardless of day of week.  The weekly
    # close and open are specified as (weekday, UTC hour) pairs using
    # ``datetime.weekday()`` semantics: 0 = Monday … 6 = Sunday.  Defaults
    # reproduce the historical hard-coded forex schedule (Fri 21:00 UTC
    # close, Sun 21:00 UTC open).
    market_close_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Apply a weekly market-close window during the backtest. "
            "When disabled, market-idle thresholds are ignored."
        ),
    )
    market_close_weekday = models.PositiveSmallIntegerField(
        default=4,  # Friday
        help_text=("Weekday the market closes (0 = Monday, 6 = Sunday). Default: 4 (Friday)."),
    )
    market_close_hour_utc = models.PositiveSmallIntegerField(
        default=21,
        help_text="Hour (UTC) at which the market closes on close weekday. 0–23.",
    )
    market_open_weekday = models.PositiveSmallIntegerField(
        default=6,  # Sunday
        help_text=("Weekday the market reopens (0 = Monday, 6 = Sunday). Default: 6 (Sunday)."),
    )
    market_open_hour_utc = models.PositiveSmallIntegerField(
        default=21,
        help_text="Hour (UTC) at which the market reopens on open weekday. 0–23.",
    )
    max_tick_gap_hours = models.PositiveIntegerField(
        default=120,
        help_text=(
            "Maximum forward gap between replayed ticks, in hours, before the backtest "
            "is failed as suspicious. Default: 120 (5 days)."
        ),
    )
    holidays_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Treat days where two or more major FX centres (US, UK, Germany) are "
            "observing a public holiday as market-closed during the backtest. "
            "Useful for suppressing trading on Christmas, Good Friday, New Year's Day, etc."
        ),
    )
    excluded_dates = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Additional UTC calendar dates (ISO-8601 'YYYY-MM-DD') on which the backtest "
            "should treat the market as closed. Merged with the auto-detected holiday set "
            "when ``holidays_enabled`` is True; honoured on its own when it is False."
        ),
    )
    initial_positions_enabled = models.BooleanField(
        default=False,
        help_text="Create Snowball initial cycles/positions before starting the backtest.",
    )
    initial_position_cycles = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Requested Snowball initial cycle/position structure. "
            "Positions, trades, orders, and strategy state are generated from this data."
        ),
    )
    in_memory_mode = models.BooleanField(
        default=False,
        help_text=(
            "Run the backtest with in-memory execution records. "
            "Orders, positions, trades, and strategy events are not persisted; "
            "only task state, metrics, and terminal snapshots are stored."
        ),
    )

    class Meta:
        db_table = "backtest_tasks"
        verbose_name = "Backtest Task"
        verbose_name_plural = "Backtest Tasks"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "config"]),
            models.Index(fields=["execution_id"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(
                fields=["instrument", "tick_granularity", "tick_window_value_mode"],
                name="backtest_ta_instrum_e42678_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_backtest_task_name",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.config.strategy_type})"

    @property
    def effective_display_currency(self) -> str:
        """Return the currency used for presenting backtest balances and PnL."""
        return str(self.display_currency or self.account_currency or "").strip().upper()

    def validate_configuration(self) -> tuple[bool, str | None]:
        """Validate task configuration before execution."""
        if self.end_time <= self.start_time:
            return False, "End time must be after start time"

        is_valid, error_message = self.config.validate_parameters()
        if not is_valid:
            return False, f"Configuration validation failed: {error_message}"

        return True, None

    def copy(self, new_name: str) -> "BacktestTask":
        """Create a copy of this backtest task with a new name."""
        if new_name == self.name:
            raise ValueError("New name must be different from current name")

        if BacktestTask.objects.filter(user=self.user, name=new_name).exists():
            raise ValueError(f"A backtest task with name '{new_name}' already exists")

        copy_values = self.copy_values()
        copy_values.update(name=new_name, status=TaskStatus.CREATED)
        return BacktestTask.objects.create(**copy_values)

    def can_resume(self) -> bool:
        """Whether the current execution can resume from persisted state."""
        if self.in_memory_mode:
            return False
        return (
            self.status in (TaskStatus.PAUSED, TaskStatus.STOPPED) and self.execution_id is not None
        )
