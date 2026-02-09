"""Margin monitoring for Floor strategy."""

from decimal import Decimal
from logging import Logger, getLogger

from apps.trading.strategies.floor.calculators import MarginCalculator, PnLCalculator
from apps.trading.strategies.floor.models import FloorStrategyConfig, FloorStrategyState

logger: Logger = getLogger(__name__)


class MarginMonitor:
    """Monitor margin and trigger protection."""

    def __init__(
        self,
        config: FloorStrategyConfig,
        pip_size: Decimal,
    ) -> None:
        """Initialize margin monitor.

        Args:
            config: Strategy configuration
            pip_size: Pip size for instrument
        """
        self.config = config
        self.margin_calc = MarginCalculator(config.margin_rate)
        self.pnl_calc = PnLCalculator(pip_size)

    def check_margin_ratio(
        self,
        state: FloorStrategyState,
        current_price: Decimal,
        task_id: str,
    ) -> tuple[bool, Decimal, Decimal]:
        """Check if margin ratio exceeds threshold.

        Args:
            state: Strategy state
            current_price: Current market price
            task_id: Task ID to query positions for

        Returns:
            Tuple of (needs_protection, margin_ratio, units_to_close)
        """
        from apps.trading.models import Layer

        # Get all active layers for this task
        layers = Layer.objects.filter(task_id=task_id, is_active=True)

        # Calculate total units across all layers
        total_units = sum((layer.total_units for layer in layers), Decimal("0"))

        if total_units == 0:
            return False, Decimal("0"), Decimal("0")

        # Calculate required margin
        required_margin = self.margin_calc.calculate_required_margin(
            current_price=current_price,
            total_units=total_units,
        )

        # Calculate margin ratio
        margin_ratio = self.margin_calc.calculate_margin_ratio(
            required_margin=required_margin,
            nav=state.account_nav,
        )

        logger.debug(
            f"Margin check: ratio={margin_ratio:.2%}, "
            f"threshold={self.config.margin_closeout_threshold:.2%}, "
            f"required={required_margin}, nav={state.account_nav}"
        )

        # Check if threshold exceeded
        if margin_ratio >= self.config.margin_closeout_threshold:
            # Calculate units to close
            # Target: reduce margin_ratio to 80% of threshold
            target_ratio = self.config.margin_closeout_threshold * Decimal("0.8")
            target_required_margin = target_ratio * state.account_nav
            target_units = target_required_margin / (current_price * self.config.margin_rate)
            units_to_close = total_units - target_units

            # Close at least 10%
            min_close = total_units * Decimal("0.1")
            units_to_close = max(units_to_close, min_close)

            logger.warning(
                f"Margin protection triggered: ratio={margin_ratio:.2%}, "
                f"will close {units_to_close} units"
            )

            return True, margin_ratio, units_to_close

        return False, margin_ratio, Decimal("0")
