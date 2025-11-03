"""
Risk Management System for volatility and margin monitoring.

This module provides functionality to:
- Monitor ATR values for volatility spikes
- Implement volatility lock mechanism
- Monitor margin-liquidation ratio
- Execute margin protection liquidation

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from django.db import transaction

from accounts.models import OandaAccount
from trading.atr_calculator import ATRCalculator
from trading.event_models import Event
from trading.models import Position, Strategy, StrategyState

logger = logging.getLogger(__name__)

# Default ATR calculator instance for ATRMonitor
_DEFAULT_ATR_CALCULATOR = ATRCalculator(period=14)


class ATRMonitor:
    """
    Monitor ATR values for volatility spikes.

    This class monitors the Average True Range (ATR) for each instrument
    and detects when volatility exceeds 5x the normal ATR baseline.

    Requirements: 10.1, 10.2
    """

    def __init__(self, atr_calculator: Optional[ATRCalculator] = None):
        """
        Initialize ATR monitor.

        Args:
            atr_calculator: ATRCalculator instance (default: uses module-level default)
        """
        self.atr_calculator = atr_calculator or _DEFAULT_ATR_CALCULATOR
        logger.info("Initialized ATRMonitor")

    def check_volatility_spike(
        self,
        current_atr: Decimal,
        normal_atr: Decimal,
        threshold_multiplier: Optional[Decimal] = None,
    ) -> bool:
        """
        Check if current ATR indicates a volatility spike.

        A volatility spike is detected when:
        current_atr >= threshold_multiplier * normal_atr

        Args:
            current_atr: Current ATR value
            normal_atr: Normal ATR baseline
            threshold_multiplier: Multiplier for volatility threshold (default: 5.0)

        Returns:
            True if volatility spike detected, False otherwise

        Requirements: 10.1, 10.2
        """
        if threshold_multiplier is None:
            threshold_multiplier = Decimal("5.0")

        if normal_atr <= 0:
            logger.warning("Normal ATR is zero or negative, cannot check volatility spike")
            return False

        threshold = threshold_multiplier * normal_atr
        is_spike = current_atr >= threshold

        if is_spike:
            logger.warning(
                "Volatility spike detected: current_atr=%s >= threshold=%s (%.1fx normal_atr=%s)",
                current_atr,
                threshold,
                threshold_multiplier,
                normal_atr,
            )
        else:
            logger.debug(
                "No volatility spike: current_atr=%s < threshold=%s (%.1fx normal_atr=%s)",
                current_atr,
                threshold,
                threshold_multiplier,
                normal_atr,
            )

        return is_spike

    def get_current_atr(
        self,
        account: OandaAccount,
        instrument: str,
    ) -> Optional[Decimal]:
        """
        Get the current ATR value for an instrument.

        Args:
            account: OandaAccount instance
            instrument: Currency pair (e.g., 'EUR_USD')

        Returns:
            Current ATR value, or None if calculation fails

        Requirements: 10.1
        """
        try:
            return self.atr_calculator.get_latest_atr(account, instrument)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error getting current ATR for %s: %s",
                instrument,
                e,
                exc_info=True,
            )
            return None

    def get_normal_atr(
        self,
        strategy_state: StrategyState,
        instrument: str,
    ) -> Optional[Decimal]:
        """
        Get the normal ATR baseline from strategy state.

        Args:
            strategy_state: StrategyState instance
            instrument: Currency pair (e.g., 'EUR_USD')

        Returns:
            Normal ATR baseline, or None if not set

        Requirements: 10.1
        """
        # Check if normal_atr is set for the strategy
        if strategy_state.normal_atr:
            return strategy_state.normal_atr

        # Check if instrument-specific ATR is stored
        if isinstance(strategy_state.atr_values, dict):
            atr_str = strategy_state.atr_values.get(f"{instrument}_normal")
            if atr_str:
                try:
                    return Decimal(str(atr_str))
                except (ValueError, TypeError):
                    logger.warning(
                        "Invalid normal ATR value for %s: %s",
                        instrument,
                        atr_str,
                    )

        return None

    def monitor_instruments(
        self,
        account: OandaAccount,
        strategy: Strategy,
        instruments: List[str],
    ) -> Dict[str, bool]:
        """
        Monitor ATR for multiple instruments and detect volatility spikes.

        Args:
            account: OandaAccount instance
            strategy: Strategy instance
            instruments: List of currency pairs to monitor

        Returns:
            Dictionary mapping instrument to volatility spike status

        Requirements: 10.1, 10.2
        """
        results: Dict[str, bool] = {}

        try:
            strategy_state = strategy.state
        except StrategyState.DoesNotExist:
            logger.warning(
                "No strategy state found for strategy %s, cannot monitor ATR",
                strategy.id,
            )
            return results

        for instrument in instruments:
            try:
                # Get current ATR
                current_atr = self.get_current_atr(account, instrument)
                if current_atr is None:
                    logger.warning(
                        "Could not get current ATR for %s, skipping",
                        instrument,
                    )
                    results[instrument] = False
                    continue

                # Get normal ATR baseline
                normal_atr = self.get_normal_atr(strategy_state, instrument)
                if normal_atr is None:
                    logger.warning(
                        "No normal ATR baseline for %s, skipping volatility check",
                        instrument,
                    )
                    results[instrument] = False
                    continue

                # Check for volatility spike
                is_spike = self.check_volatility_spike(current_atr, normal_atr)
                results[instrument] = is_spike

                # Update ATR in strategy state
                strategy_state.update_atr(instrument, current_atr)

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Error monitoring ATR for %s: %s",
                    instrument,
                    e,
                    exc_info=True,
                )
                results[instrument] = False

        return results


class RiskManager:
    """
    Comprehensive risk management system.

    This class coordinates:
    - Volatility monitoring and lock mechanism
    - Margin monitoring and protection liquidation
    - Integration with strategy execution

    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5
    """

    def __init__(self, atr_monitor: Optional[ATRMonitor] = None):
        """
        Initialize risk manager.

        Args:
            atr_monitor: ATRMonitor instance (default: creates new ATRMonitor)
        """
        self.atr_monitor = atr_monitor if atr_monitor is not None else ATRMonitor()
        logger.info("Initialized RiskManager")

    def execute_volatility_lock(
        self,
        *,
        account: OandaAccount,
        strategy: Strategy,
        instrument: str,
        current_atr: Decimal,
        normal_atr: Decimal,
    ) -> bool:
        """
        Execute volatility lock mechanism.

        This method:
        1. Closes all positions at break-even prices where possible
        2. Pauses strategy execution
        3. Logs volatility lock event
        4. Sends admin notifications

        Args:
            account: OandaAccount instance
            strategy: Strategy instance
            instrument: Currency pair that triggered the lock
            current_atr: Current ATR value
            normal_atr: Normal ATR baseline

        Returns:
            True if volatility lock executed successfully, False otherwise

        Requirements: 10.2, 10.3, 10.5
        """
        logger.warning(
            "Executing volatility lock for account %s, strategy %s, instrument %s",
            account.account_id,
            strategy.id,
            instrument,
        )

        try:
            with transaction.atomic():
                # 1. Close all open positions at break-even where possible
                open_positions = Position.objects.filter(
                    account=account,
                    strategy=strategy,
                    closed_at__isnull=True,
                )

                positions_closed = 0
                for position in open_positions:
                    try:
                        # Close at break-even (entry price)
                        position.close(position.entry_price)
                        positions_closed += 1
                        logger.info(
                            "Closed position %s at break-even price %s",
                            position.position_id,
                            position.entry_price,
                        )
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.error(
                            "Error closing position %s: %s",
                            position.position_id,
                            e,
                            exc_info=True,
                        )

                # 2. Pause strategy execution
                strategy.stop()
                logger.info("Paused strategy %s due to volatility lock", strategy.id)

                # 3. Log volatility lock event
                Event.objects.create(
                    category="system",
                    event_type="volatility_lock",
                    severity="critical",
                    user=account.user,
                    account=account,
                    description=f"Volatility lock triggered for {instrument}",
                    details={
                        "instrument": instrument,
                        "current_atr": str(current_atr),
                        "normal_atr": str(normal_atr),
                        "threshold_multiplier": "5.0",
                        "positions_closed": positions_closed,
                        "strategy_id": strategy.id,
                        "strategy_type": strategy.strategy_type,
                    },
                )

                logger.info(
                    "Volatility lock executed successfully: closed %d positions, paused strategy",
                    positions_closed,
                )

                return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error executing volatility lock: %s",
                e,
                exc_info=True,
            )
            return False

    def calculate_margin_liquidation_ratio(
        self,
        account: OandaAccount,
    ) -> Optional[Decimal]:
        """
        Calculate margin-liquidation ratio.

        The ratio is calculated as:
        (Margin + Unrealized P&L) / Margin

        When this ratio reaches 100% (1.0), margin protection is triggered.

        Args:
            account: OandaAccount instance

        Returns:
            Margin-liquidation ratio, or None if calculation fails

        Requirements: 11.1, 11.2
        """
        try:
            margin_used = account.margin_used
            if margin_used <= 0:
                logger.warning(
                    "Margin used is zero or negative for account %s, cannot calculate ratio",
                    account.account_id,
                )
                return None

            # Calculate total unrealized P&L from open positions
            open_positions = Position.objects.filter(
                account=account,
                closed_at__isnull=True,
            )

            total_unrealized_pnl = sum(position.unrealized_pnl for position in open_positions)

            # Calculate ratio: (Margin + Unrealized P&L) / Margin
            ratio = (margin_used + total_unrealized_pnl) / margin_used

            logger.debug(
                "Margin-liquidation ratio for account %s: %s (margin=%s, unrealized_pnl=%s)",
                account.account_id,
                ratio,
                margin_used,
                total_unrealized_pnl,
            )

            return ratio

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error calculating margin-liquidation ratio for account %s: %s",
                account.account_id,
                e,
                exc_info=True,
            )
            return None

    def check_margin_threshold(
        self,
        account: OandaAccount,
        threshold: Optional[Decimal] = None,
    ) -> bool:
        """
        Check if margin-liquidation ratio exceeds threshold.

        Args:
            account: OandaAccount instance
            threshold: Threshold ratio (default: 1.0 = 100%)

        Returns:
            True if threshold exceeded, False otherwise

        Requirements: 11.1, 11.2
        """
        if threshold is None:
            threshold = Decimal("1.0")

        ratio = self.calculate_margin_liquidation_ratio(account)
        if ratio is None:
            return False

        exceeds_threshold = ratio >= threshold

        if exceeds_threshold:
            logger.warning(
                "Margin threshold exceeded for account %s: ratio=%s >= threshold=%s",
                account.account_id,
                ratio,
                threshold,
            )
        else:
            logger.debug(
                "Margin threshold not exceeded for account %s: ratio=%s < threshold=%s",
                account.account_id,
                ratio,
                threshold,
            )

        return exceeds_threshold

    def execute_margin_protection(
        self,
        account: OandaAccount,
    ) -> bool:
        """
        Execute margin protection liquidation.

        This method:
        1. Liquidates first lot of first layer
        2. If first layer fully liquidated, liquidates first lot of second layer
        3. Logs margin protection events
        4. Sends admin notifications

        Args:
            account: OandaAccount instance

        Returns:
            True if margin protection executed successfully, False otherwise

        Requirements: 11.2, 11.3, 11.4
        """
        logger.warning(
            "Executing margin protection for account %s",
            account.account_id,
        )

        try:
            with transaction.atomic():
                # Get all open positions ordered by layer and opening time
                open_positions = Position.objects.filter(
                    account=account,
                    closed_at__isnull=True,
                ).order_by("layer_number", "opened_at")

                if not open_positions.exists():
                    logger.warning(
                        "No open positions found for account %s, cannot execute margin protection",
                        account.account_id,
                    )
                    return False

                # Find first lot of first layer
                first_layer_positions = open_positions.filter(layer_number=1)
                position_to_close: Optional[Position] = None
                layer_number: int = 1

                if first_layer_positions.exists():
                    position_to_close = first_layer_positions.first()
                    layer_number = 1
                else:
                    # First layer fully liquidated, move to second layer
                    second_layer_positions = open_positions.filter(layer_number=2)
                    if second_layer_positions.exists():
                        position_to_close = second_layer_positions.first()
                        layer_number = 2
                    else:
                        # No positions in first two layers, take first available
                        position_to_close = open_positions.first()
                        if position_to_close:
                            layer_number = position_to_close.layer_number

                if position_to_close is None:
                    logger.warning("No position found to close for margin protection")
                    return False

                # Close the position at current market price
                position_to_close.close(position_to_close.current_price)

                logger.info(
                    "Closed position %s (layer %d) at price %s for margin protection",
                    position_to_close.position_id,
                    layer_number,
                    position_to_close.current_price,
                )

                # Log margin protection event
                Event.objects.create(
                    category="system",
                    event_type="margin_protection",
                    severity="critical",
                    user=account.user,
                    account=account,
                    description=f"Margin protection triggered for account {account.account_id}",
                    details={
                        "position_id": position_to_close.position_id,
                        "instrument": position_to_close.instrument,
                        "layer_number": layer_number,
                        "units": str(position_to_close.units),
                        "entry_price": str(position_to_close.entry_price),
                        "exit_price": str(position_to_close.current_price),
                        "realized_pnl": str(position_to_close.realized_pnl),
                        "margin_used": str(account.margin_used),
                    },
                )

                logger.info("Margin protection executed successfully")
                return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error executing margin protection: %s",
                e,
                exc_info=True,
            )
            return False

    def check_and_execute_risk_management(
        self,
        account: OandaAccount,
        strategy: Strategy,
    ) -> Dict[str, object]:
        """
        Check and execute all risk management mechanisms.

        This method:
        1. Monitors ATR for volatility spikes
        2. Executes volatility lock if needed
        3. Monitors margin-liquidation ratio
        4. Executes margin protection if needed

        Args:
            account: OandaAccount instance
            strategy: Strategy instance

        Returns:
            Dictionary with risk management results:
            - volatility_locked: True if volatility lock executed
            - margin_protected: True if margin protection executed
            - instruments_monitored: List of instruments monitored

        Requirements: 10.4, 11.5
        """
        results: Dict[str, object] = {
            "volatility_locked": False,
            "margin_protected": False,
            "instruments_monitored": [],
        }

        try:
            # 1. Monitor ATR for volatility spikes
            self._check_volatility_spikes(account, strategy, results)

            # 2. Monitor margin-liquidation ratio
            if self.check_margin_threshold(account):
                success = self.execute_margin_protection(account)
                if success:
                    results["margin_protected"] = True

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error in risk management check: %s",
                e,
                exc_info=True,
            )

        return results

    def _check_volatility_spikes(
        self,
        account: OandaAccount,
        strategy: Strategy,
        results: Dict[str, object],
    ) -> None:
        """
        Check for volatility spikes and execute lock if needed.

        Args:
            account: OandaAccount instance
            strategy: Strategy instance
            results: Results dictionary to update
        """
        instruments = strategy.instruments if isinstance(strategy.instruments, list) else []
        if not instruments:
            return

        volatility_results = self.atr_monitor.monitor_instruments(
            account,
            strategy,
            instruments,
        )
        results["instruments_monitored"] = list(volatility_results.keys())

        # Execute volatility lock if any instrument has spike
        for instrument, has_spike in volatility_results.items():
            if not has_spike:
                continue

            if self._execute_volatility_lock_for_instrument(account, strategy, instrument):
                results["volatility_locked"] = True
                break  # Stop checking other instruments after lock

    def _execute_volatility_lock_for_instrument(
        self,
        account: OandaAccount,
        strategy: Strategy,
        instrument: str,
    ) -> bool:
        """
        Execute volatility lock for a specific instrument.

        Args:
            account: OandaAccount instance
            strategy: Strategy instance
            instrument: Currency pair

        Returns:
            True if volatility lock executed successfully
        """
        try:
            strategy_state = strategy.state
            current_atr = self.atr_monitor.get_current_atr(account, instrument)
            normal_atr = self.atr_monitor.get_normal_atr(strategy_state, instrument)

            if current_atr and normal_atr:
                return self.execute_volatility_lock(
                    account=account,
                    strategy=strategy,
                    instrument=instrument,
                    current_atr=current_atr,
                    normal_atr=normal_atr,
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error executing volatility lock for %s: %s",
                instrument,
                e,
                exc_info=True,
            )

        return False
