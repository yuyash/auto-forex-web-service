"""Event and log models for executions."""

from django.db import models


class StrategyEvents(models.Model):
    """Incrementally persisted strategy events during an execution.

    These rows enable live strategy markers/timelines while an execution is RUNNING.
    The final immutable `ExecutionMetrics.strategy_events` remains the canonical
    completed payload.
    """

    execution = models.ForeignKey(
        "trading.Executions",
        on_delete=models.CASCADE,
        related_name="strategy_events",
        help_text="Owning task execution",
    )
    sequence = models.PositiveIntegerField(help_text="Monotonic per-execution sequence")
    event_type = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Best-effort event['type'] for filtering/debug",
    )
    strategy_type = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Strategy type identifier (e.g., 'floor', 'momentum') for filtering and registry lookup",
    )
    timestamp = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Event timestamp parsed from event data, used for chronological ordering",
    )
    event = models.JSONField(default=dict, help_text="Raw strategy event payload")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "strategy_events"
        verbose_name = "Strategy Event"
        verbose_name_plural = "Strategy Events"
        indexes = [
            models.Index(fields=["execution", "sequence"]),
            models.Index(fields=["execution", "created_at"]),
            models.Index(fields=["execution", "strategy_type"]),
            models.Index(fields=["execution", "timestamp"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "sequence"],
                name="uniq_execution_strategy_event_sequence",
            )
        ]
        ordering = ["sequence", "id"]

    def __str__(self) -> str:
        return (
            f"StrategyEvents(exec={self.execution_id}, seq={self.sequence}, type={self.event_type})"  # type: ignore[attr-defined]
        )


class TradeLogs(models.Model):
    """Incrementally persisted trade log entries during an execution."""

    execution = models.ForeignKey(
        "trading.Executions",
        on_delete=models.CASCADE,
        related_name="trade_logs",
        help_text="Owning task execution",
    )
    sequence = models.PositiveIntegerField(help_text="Monotonic per-execution sequence")
    trade = models.JSONField(default=dict, help_text="Raw trade payload")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "trade_logs"
        verbose_name = "Trade Log"
        verbose_name_plural = "Trade Logs"
        indexes = [
            models.Index(fields=["execution", "sequence"]),
            models.Index(fields=["execution", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "sequence"],
                name="uniq_execution_trade_log_sequence",
            )
        ]
        ordering = ["sequence", "id"]

    def __str__(self) -> str:
        return f"TradeLogs(exec={self.execution_id}, seq={self.sequence})"  # type: ignore[attr-defined]


class TradingEvent(models.Model):
    """Persistent event log for the trading app.

    This is intentionally independent from any market/accounts event mechanisms.
    """

    event_type = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=16, default="info", db_index=True)
    description = models.TextField()

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trading_events",
    )
    account = models.ForeignKey(
        "market.OandaAccounts",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trading_events",
    )
    instrument = models.CharField(max_length=32, null=True, blank=True, db_index=True)

    task_type = models.CharField(max_length=32, blank=True, default="", db_index=True)
    task_id = models.IntegerField(null=True, blank=True, db_index=True)
    execution = models.ForeignKey(
        "trading.Executions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trading_events",
    )

    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "trading_events"
        verbose_name = "Trading Event"
        verbose_name_plural = "Trading Events"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.created_at.isoformat()} [{self.severity}] {self.event_type}"
