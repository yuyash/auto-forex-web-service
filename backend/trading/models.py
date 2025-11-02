"""
Trading models for strategy management and trading operations.

This module contains models for:
- Strategy: Trading strategy configuration
- StrategyState: Runtime state for active strategies
- Order: Trading orders
- Position: Open trading positions
- Trade: Completed trade records

Requirements: 5.1, 5.2, 8.1, 8.2, 9.1, 9.2, 18.1
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from accounts.models import OandaAccount

# Import backtest models to make them discoverable by Django
# pylint: disable=unused-import
from .backtest_models import Backtest, BacktestResult  # noqa: F401
from .event_models import Event, Notification  # noqa: F401

User = get_user_model()


class Strategy(models.Model):
    """
    Trading strategy configuration.

    Requirements: 5.1, 5.2
    """

    account = models.ForeignKey(
        OandaAccount,
        on_delete=models.CASCADE,
        related_name="strategies",
        help_text="OANDA account associated with this strategy",
    )
    strategy_type = models.CharField(
        max_length=50,
        help_text="Type of strategy (e.g., 'floor', 'trend_following')",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Whether the strategy is currently active",
    )
    config = models.JSONField(
        default=dict,
        help_text="Strategy-specific configuration parameters",
    )
    instruments = models.JSONField(
        default=list,
        help_text="List of currency pairs to trade (e.g., ['EUR_USD', 'GBP_USD'])",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the strategy was started",
    )
    stopped_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the strategy was stopped",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the strategy was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the strategy was last updated",
    )

    class Meta:
        db_table = "strategies"
        verbose_name = "Strategy"
        verbose_name_plural = "Strategies"
        indexes = [
            models.Index(fields=["account", "is_active"]),
            models.Index(fields=["strategy_type"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status = "Active" if self.is_active else "Inactive"
        return f"{self.strategy_type} - {self.account.account_id} ({status})"

    def start(self) -> None:
        """Start the strategy."""
        self.is_active = True
        self.started_at = timezone.now()
        self.stopped_at = None
        self.save(update_fields=["is_active", "started_at", "stopped_at", "updated_at"])

    def stop(self) -> None:
        """Stop the strategy."""
        self.is_active = False
        self.stopped_at = timezone.now()
        self.save(update_fields=["is_active", "stopped_at", "updated_at"])

    def update_config(self, config: dict) -> None:
        """
        Update strategy configuration.

        Args:
            config: New configuration parameters
        """
        self.config = config
        self.save(update_fields=["config", "updated_at"])


class StrategyState(models.Model):
    """
    Runtime state for active strategy.

    Requirements: 5.1, 5.2
    """

    strategy = models.OneToOneField(
        Strategy,
        on_delete=models.CASCADE,
        related_name="state",
        help_text="Strategy associated with this state",
    )
    current_layer = models.IntegerField(
        default=1,
        help_text="Current layer number (for multi-layer strategies)",
    )
    layer_states = models.JSONField(
        default=dict,
        help_text="State for each layer (e.g., position counts, entry prices)",
    )
    atr_values = models.JSONField(
        default=dict,
        help_text="ATR history for volatility monitoring",
    )
    normal_atr = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Normal ATR baseline value",
    )
    last_tick_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last processed tick",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the state was last updated",
    )

    class Meta:
        db_table = "strategy_states"
        verbose_name = "Strategy State"
        verbose_name_plural = "Strategy States"

    def __str__(self) -> str:
        return f"State for {self.strategy.strategy_type} - Layer {self.current_layer}"

    def update_layer_state(self, layer: int, state: dict) -> None:
        """
        Update state for a specific layer.

        Args:
            layer: Layer number
            state: Layer state data
        """
        if not isinstance(self.layer_states, dict):
            self.layer_states = {}
        self.layer_states[str(layer)] = state
        self.save(update_fields=["layer_states", "updated_at"])

    def update_atr(self, instrument: str, atr_value: Decimal) -> None:
        """
        Update ATR value for an instrument.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            atr_value: ATR value
        """
        if not isinstance(self.atr_values, dict):
            self.atr_values = {}
        self.atr_values[instrument] = str(atr_value)
        self.save(update_fields=["atr_values", "updated_at"])


class Order(models.Model):
    """
    Trading order.

    Requirements: 8.1, 8.2
    """

    ORDER_TYPE_CHOICES = [
        ("market", "Market"),
        ("limit", "Limit"),
        ("stop", "Stop"),
        ("oco", "OCO"),
    ]

    DIRECTION_CHOICES = [
        ("long", "Long"),
        ("short", "Short"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("filled", "Filled"),
        ("cancelled", "Cancelled"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    account = models.ForeignKey(
        OandaAccount,
        on_delete=models.CASCADE,
        related_name="orders",
        help_text="OANDA account associated with this order",
    )
    strategy = models.ForeignKey(
        Strategy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        help_text="Strategy that generated this order",
    )
    order_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="OANDA order ID",
    )
    instrument = models.CharField(
        max_length=10,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
        help_text="Type of order",
    )
    direction = models.CharField(
        max_length=5,
        choices=DIRECTION_CHOICES,
        help_text="Trade direction (long or short)",
    )
    units = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Number of units to trade",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Order price (for limit/stop orders)",
    )
    take_profit = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Take-profit price",
    )
    stop_loss = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Stop-loss price",
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=STATUS_CHOICES,
        help_text="Current order status",
    )
    filled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the order was filled",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the order was created",
    )

    class Meta:
        db_table = "orders"
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        indexes = [
            models.Index(fields=["account", "status"]),
            models.Index(fields=["order_id"]),
            models.Index(fields=["instrument"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"{self.order_type} {self.direction} {self.units} "
            f"{self.instrument} - {self.status}"  # noqa: E501
        )

    def mark_filled(self) -> None:
        """Mark the order as filled."""
        self.status = "filled"
        self.filled_at = timezone.now()
        self.save(update_fields=["status", "filled_at"])

    def mark_cancelled(self) -> None:
        """Mark the order as cancelled."""
        self.status = "cancelled"
        self.save(update_fields=["status"])

    def mark_rejected(self) -> None:
        """Mark the order as rejected."""
        self.status = "rejected"
        self.save(update_fields=["status"])


class Position(models.Model):
    """
    Open trading position.

    Requirements: 9.1, 9.2
    """

    DIRECTION_CHOICES = [
        ("long", "Long"),
        ("short", "Short"),
    ]

    account = models.ForeignKey(
        OandaAccount,
        on_delete=models.CASCADE,
        related_name="positions",
        help_text="OANDA account associated with this position",
    )
    strategy = models.ForeignKey(
        Strategy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions",
        help_text="Strategy that opened this position",
    )
    position_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="OANDA position ID",
    )
    instrument = models.CharField(
        max_length=10,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    direction = models.CharField(
        max_length=5,
        choices=DIRECTION_CHOICES,
        help_text="Position direction (long or short)",
    )
    units = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Number of units in the position",
    )
    entry_price = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Entry price for the position",
    )
    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Current market price",
    )
    unrealized_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Unrealized profit/loss",
    )
    layer_number = models.IntegerField(
        default=1,
        help_text="Layer number (for multi-layer strategies)",
    )
    is_first_lot = models.BooleanField(
        default=False,
        help_text="Whether this is the first lot of a layer",
    )
    opened_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the position was opened",
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the position was closed",
    )
    realized_pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Realized profit/loss (when closed)",
    )

    class Meta:
        db_table = "positions"
        verbose_name = "Position"
        verbose_name_plural = "Positions"
        indexes = [
            models.Index(fields=["account", "closed_at"]),
            models.Index(fields=["position_id"]),
            models.Index(fields=["instrument"]),
            models.Index(fields=["opened_at"]),
        ]
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        status = "Open" if self.closed_at is None else "Closed"
        return (
            f"{self.direction} {self.units} {self.instrument} "
            f"@ {self.entry_price} - {status}"  # noqa: E501
        )

    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """
        Calculate unrealized P&L based on current price.

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L
        """
        self.current_price = current_price
        price_diff = current_price - self.entry_price

        if self.direction == "short":
            price_diff = -price_diff

        self.unrealized_pnl = price_diff * self.units
        return self.unrealized_pnl

    def update_price(self, current_price: Decimal) -> None:
        """
        Update current price and recalculate unrealized P&L.

        Args:
            current_price: Current market price
        """
        self.calculate_unrealized_pnl(current_price)
        self.save(update_fields=["current_price", "unrealized_pnl"])

    def close(self, exit_price: Decimal) -> Decimal:
        """
        Close the position and calculate realized P&L.

        Args:
            exit_price: Exit price for the position

        Returns:
            Realized P&L
        """
        price_diff = exit_price - self.entry_price

        if self.direction == "short":
            price_diff = -price_diff

        self.realized_pnl = price_diff * self.units
        self.closed_at = timezone.now()
        self.current_price = exit_price
        self.save(update_fields=["realized_pnl", "closed_at", "current_price"])
        return self.realized_pnl


class Trade(models.Model):
    """
    Completed trade record.

    Requirements: 18.1
    """

    DIRECTION_CHOICES = [
        ("long", "Long"),
        ("short", "Short"),
    ]

    account = models.ForeignKey(
        OandaAccount,
        on_delete=models.CASCADE,
        related_name="trades",
        help_text="OANDA account associated with this trade",
    )
    strategy = models.ForeignKey(
        Strategy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trades",
        help_text="Strategy that executed this trade",
    )
    instrument = models.CharField(
        max_length=10,
        help_text="Currency pair (e.g., 'EUR_USD')",
    )
    direction = models.CharField(
        max_length=5,
        choices=DIRECTION_CHOICES,
        help_text="Trade direction (long or short)",
    )
    units = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Number of units traded",
    )
    entry_price = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Entry price",
    )
    exit_price = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        help_text="Exit price",
    )
    pnl = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Profit/loss for the trade",
    )
    commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Commission paid for the trade",
    )
    opened_at = models.DateTimeField(
        help_text="Timestamp when the trade was opened",
    )
    closed_at = models.DateTimeField(
        help_text="Timestamp when the trade was closed",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the trade record was created",
    )

    class Meta:
        db_table = "trades"
        verbose_name = "Trade"
        verbose_name_plural = "Trades"
        indexes = [
            models.Index(fields=["account", "closed_at"]),
            models.Index(fields=["instrument"]),
            models.Index(fields=["opened_at"]),
            models.Index(fields=["closed_at"]),
        ]
        ordering = ["-closed_at"]

    def __str__(self) -> str:
        return f"{self.direction} {self.units} {self.instrument} - P&L: {self.pnl}"

    @property
    def duration(self) -> str:
        """
        Calculate trade duration.

        Returns:
            Duration as a formatted string
        """
        if self.opened_at and self.closed_at:
            delta = self.closed_at - self.opened_at
            hours = delta.total_seconds() / 3600
            if hours < 1:
                minutes = delta.total_seconds() / 60
                return f"{minutes:.0f}m"
            if hours < 24:
                return f"{hours:.1f}h"
            days = hours / 24
            return f"{days:.1f}d"
        return "N/A"

    @property
    def net_pnl(self) -> Decimal:
        """
        Calculate net P&L after commission.

        Returns:
            Net profit/loss
        """
        return self.pnl - self.commission
