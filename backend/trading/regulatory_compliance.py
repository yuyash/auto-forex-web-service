"""
Regulatory compliance management for forex trading.

This module implements jurisdiction-specific compliance rules for:
- United States (NFA/CFTC): FIFO, no hedging, leverage limits
- Japan (FSA): Leverage limits, hedging allowed
- European Union (ESMA): Leverage limits, negative balance protection, margin close-out
- United Kingdom (FCA): Similar to EU rules
- Australia (ASIC): Leverage limits
- Other/International: Default rules

Requirements: 8.1, 8.2, 9.1, 11.1, 11.2
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from trading.models import Position

if TYPE_CHECKING:
    from accounts.models import OandaAccount


class ComplianceViolationError(Exception):
    """Exception raised when an order violates regulatory compliance rules."""


class RegulatoryComplianceManager:
    """
    Manages regulatory compliance checks for different jurisdictions.

    This class validates orders against jurisdiction-specific rules before
    submission to the broker.
    """

    # Jurisdiction constants
    JURISDICTION_US = "US"
    JURISDICTION_JP = "JP"
    JURISDICTION_EU = "EU"
    JURISDICTION_UK = "UK"
    JURISDICTION_AU = "AU"
    JURISDICTION_OTHER = "OTHER"

    # Leverage limits by jurisdiction
    LEVERAGE_LIMITS = {
        JURISDICTION_US: {
            "major_pairs": 50,  # 50:1
            "minor_pairs": 20,  # 20:1
        },
        JURISDICTION_JP: {
            "all_pairs": 25,  # 25:1
        },
        JURISDICTION_EU: {
            "major_pairs": 30,  # 30:1
            "minor_pairs": 20,  # 20:1
            "gold": 20,  # 20:1
            "commodities": 10,  # 10:1
            "indices": 20,  # 20:1
            "crypto": 2,  # 2:1
        },
        JURISDICTION_UK: {
            "major_pairs": 30,  # 30:1
            "minor_pairs": 20,  # 20:1
            "gold": 20,  # 20:1
            "commodities": 10,  # 10:1
            "indices": 20,  # 20:1
            "crypto": 2,  # 2:1
        },
        JURISDICTION_AU: {
            "major_pairs": 30,  # 30:1
            "minor_pairs": 20,  # 20:1
        },
        JURISDICTION_OTHER: {
            "all_pairs": 100,  # 100:1 (default)
        },
    }

    # Major currency pairs
    MAJOR_PAIRS = [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "USD_CHF",
        "USD_CAD",
        "AUD_USD",
        "NZD_USD",
    ]

    def __init__(self, account: "OandaAccount") -> None:
        """
        Initialize the compliance manager for a specific account.

        Args:
            account: OandaAccount instance with jurisdiction information
        """
        self.account = account
        self.jurisdiction = getattr(account, "jurisdiction", self.JURISDICTION_OTHER)

    def validate_order(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate order against jurisdiction-specific rules.

        Args:
            order_request: Dictionary containing order details
                - instrument: Currency pair (e.g., "EUR_USD")
                - units: Number of units (positive for buy, negative for sell)
                - order_type: Type of order (market, limit, stop, etc.)

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if order passes all compliance checks
            - error_message: None if valid, error description if invalid
        """
        if self.jurisdiction == self.JURISDICTION_US:
            return self._validate_us_order(order_request)
        if self.jurisdiction == self.JURISDICTION_JP:
            return self._validate_jp_order(order_request)
        if self.jurisdiction == self.JURISDICTION_EU:
            return self._validate_eu_order(order_request)
        if self.jurisdiction == self.JURISDICTION_UK:
            return self._validate_uk_order(order_request)
        if self.jurisdiction == self.JURISDICTION_AU:
            return self._validate_au_order(order_request)
        return self._validate_other_order(order_request)

    def _validate_us_order(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate order against US NFA/CFTC rules.

        Rules:
        - No hedging (NFA Rule 2-43b)
        - FIFO position closing
        - Leverage limits: 50:1 major pairs, 20:1 minor pairs

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        instrument = str(order_request.get("instrument", ""))
        units = int(order_request.get("units", 0))

        # Check for hedging
        if self._would_create_hedge(instrument, units):
            return (
                False,
                "Hedging is not allowed for US accounts (NFA Rule 2-43b). "
                "This order would create opposing positions in the same instrument.",
            )

        # Check leverage limits
        leverage_valid, leverage_error = self._check_us_leverage(order_request)
        if not leverage_valid:
            return False, leverage_error

        return True, None

    def _validate_jp_order(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate order against Japan FSA rules.

        Rules:
        - Maximum 25:1 leverage
        - Hedging allowed
        - Position size limits based on account equity

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check leverage limits (25:1 for all pairs)
        leverage_valid, leverage_error = self._check_jp_leverage(order_request)
        if not leverage_valid:
            return False, leverage_error

        # Check position size limits
        size_valid, size_error = self._check_jp_position_size(order_request)
        if not size_valid:
            return False, size_error

        return True, None

    def _validate_eu_order(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate order against EU ESMA rules.

        Rules:
        - Leverage limits: 30:1 major, 20:1 minor, 10:1 commodities, 2:1 crypto
        - Negative balance protection
        - Margin close-out at 50%

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check leverage limits
        leverage_valid, leverage_error = self._check_eu_leverage(order_request)
        if not leverage_valid:
            return False, leverage_error

        # Check negative balance protection
        balance_valid, balance_error = self._check_negative_balance(order_request)
        if not balance_valid:
            return False, balance_error

        return True, None

    def _validate_uk_order(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate order against UK FCA rules.

        Rules are similar to EU ESMA rules.

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        # UK rules are similar to EU
        return self._validate_eu_order(order_request)

    def _validate_au_order(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate order against Australia ASIC rules.

        Rules:
        - Leverage limits: 30:1 major pairs, 20:1 minor pairs

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check leverage limits
        leverage_valid, leverage_error = self._check_au_leverage(order_request)
        if not leverage_valid:
            return False, leverage_error

        return True, None

    def _validate_other_order(
        self, order_request: Dict  # pylint: disable=unused-argument
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate order against default/international rules.

        Args:
            order_request: Order details (unused for default rules)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Default rules - minimal restrictions
        return True, None

    def _would_create_hedge(self, instrument: str, units: int) -> bool:
        """
        Check if order would create a hedge (opposing positions).

        Args:
            instrument: Currency pair
            units: Order units (positive for buy, negative for sell)

        Returns:
            True if order would create a hedge, False otherwise
        """
        # Get existing open positions for this instrument
        existing_positions = Position.objects.filter(
            account=self.account,
            instrument=instrument,
            closed_at__isnull=True,
        )

        if not existing_positions.exists():
            return False

        # Check if any existing position has opposite direction
        order_direction = "long" if units > 0 else "short"

        return any(position.direction != order_direction for position in existing_positions)

    def should_reduce_position_instead(
        self, instrument: str, units: int
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if order should reduce existing position instead of creating hedge.

        For US accounts, opposing orders should reduce positions in FIFO order
        rather than creating a hedge.

        Args:
            instrument: Currency pair
            units: Order units (positive for buy, negative for sell)

        Returns:
            Tuple of (should_reduce, units_to_reduce)
            - should_reduce: True if order should reduce existing position
            - units_to_reduce: Number of units to reduce (None if not reducing)
        """
        if self.jurisdiction != self.JURISDICTION_US:
            return False, None

        # Check if this would create a hedge
        if not self._would_create_hedge(instrument, units):
            return False, None

        # Get total units in opposite direction
        order_direction = "long" if units > 0 else "short"
        opposite_direction = "short" if order_direction == "long" else "long"

        opposite_positions = Position.objects.filter(
            account=self.account,
            instrument=instrument,
            direction=opposite_direction,
            closed_at__isnull=True,
        )

        total_opposite_units = sum(abs(pos.units) for pos in opposite_positions)

        # Calculate units to reduce
        order_units = abs(units)
        units_to_reduce = int(min(order_units, total_opposite_units))

        return True, units_to_reduce

    def _check_us_leverage(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check US leverage limits (50:1 major, 20:1 minor).

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        instrument = str(order_request.get("instrument", ""))
        units = abs(int(order_request.get("units", 0)))

        # Determine leverage limit based on instrument
        if instrument in self.MAJOR_PAIRS:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_US]["major_pairs"]
        else:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_US]["minor_pairs"]

        # Calculate required margin (simplified - actual calculation would use current price)
        # For now, we'll use a placeholder calculation
        # In production, this would fetch current price and calculate actual margin
        required_margin = Decimal(units) / Decimal(max_leverage)

        # Check if account has sufficient margin
        if required_margin > self.account.margin_available:
            pair_type = "major" if instrument in self.MAJOR_PAIRS else "minor"
            return (
                False,
                f"Order exceeds maximum leverage limits for US accounts "
                f"({max_leverage}:1 for {pair_type} pairs). "
                f"Required margin: {required_margin:.2f}, "
                f"Available: {self.account.margin_available:.2f}",
            )

        return True, None

    def _check_jp_leverage(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check Japan leverage limits (25:1 for all pairs).

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        units = abs(order_request.get("units", 0))
        max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_JP]["all_pairs"]

        # Calculate required margin
        required_margin = Decimal(units) / Decimal(max_leverage)

        if required_margin > self.account.margin_available:
            return (
                False,
                f"Order exceeds maximum leverage limit for Japan accounts (25:1). "
                f"Required margin: {required_margin:.2f}, "
                f"Available: {self.account.margin_available:.2f}",
            )

        return True, None

    def _check_jp_position_size(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check Japan position size limits (based on account equity).

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        units = abs(order_request.get("units", 0))

        # Maximum position size = Account Equity × 25
        max_position_size = self.account.balance * Decimal(25)

        if Decimal(units) > max_position_size:
            return (
                False,
                f"Order exceeds maximum position size for Japan accounts. "
                f"Maximum: {max_position_size:.0f} units, Requested: {units} units",
            )

        return True, None

    def _check_eu_leverage(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check EU leverage limits (instrument-specific).

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        instrument = str(order_request.get("instrument", ""))
        units = abs(int(order_request.get("units", 0)))

        # Determine leverage limit based on instrument type
        if instrument in self.MAJOR_PAIRS:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_EU]["major_pairs"]
            instrument_type = "major pairs"
        elif "XAU" in instrument or "GOLD" in instrument:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_EU]["gold"]
            instrument_type = "gold"
        elif "BTC" in instrument or "ETH" in instrument:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_EU]["crypto"]
            instrument_type = "cryptocurrencies"
        else:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_EU]["minor_pairs"]
            instrument_type = "minor pairs"

        # Calculate required margin
        required_margin = Decimal(units) / Decimal(max_leverage)

        if required_margin > self.account.margin_available:
            return (
                False,
                f"Order exceeds maximum leverage limit for EU accounts "
                f"({max_leverage}:1 for {instrument_type}). "
                f"Required margin: {required_margin:.2f}, "
                f"Available: {self.account.margin_available:.2f}",
            )

        return True, None

    def _check_au_leverage(self, order_request: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check Australia leverage limits (30:1 major, 20:1 minor).

        Args:
            order_request: Order details

        Returns:
            Tuple of (is_valid, error_message)
        """
        instrument = order_request.get("instrument")
        units = abs(order_request.get("units", 0))

        # Determine leverage limit
        if instrument in self.MAJOR_PAIRS:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_AU]["major_pairs"]
        else:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_AU]["minor_pairs"]

        # Calculate required margin
        required_margin = Decimal(units) / Decimal(max_leverage)

        if required_margin > self.account.margin_available:
            pair_type = "major" if instrument in self.MAJOR_PAIRS else "minor"
            return (
                False,
                f"Order exceeds maximum leverage limit for Australia accounts "
                f"({max_leverage}:1 for {pair_type} pairs). "
                f"Required margin: {required_margin:.2f}, "
                f"Available: {self.account.margin_available:.2f}",
            )

        return True, None

    def _check_negative_balance(
        self, order_request: Dict  # pylint: disable=unused-argument
    ) -> Tuple[bool, Optional[str]]:
        """
        Check negative balance protection (EU/UK requirement).

        Args:
            order_request: Order details (unused for balance check)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if order could result in negative balance
        # This is a simplified check - actual implementation would be more sophisticated
        if self.account.balance + self.account.unrealized_pnl <= 0:
            return (
                False,
                "Order rejected: Negative balance protection. "
                "Account balance is at or below zero.",
            )

        return True, None

    def get_fifo_position_to_close(
        self, instrument: str, units: int  # pylint: disable=unused-argument
    ) -> Optional[Position]:
        """
        Get the oldest position to close for FIFO compliance (US requirement).

        Args:
            instrument: Currency pair
            units: Number of units to close (unused, for future use)

        Returns:
            Position object to close, or None if no positions exist
        """
        # Get all open positions for this instrument, ordered by opening time
        positions = Position.objects.filter(
            account=self.account,
            instrument=instrument,
            closed_at__isnull=True,
        ).order_by("opened_at")

        first_position = positions.first()
        return first_position if first_position is not None else None

    def should_trigger_margin_closeout(self) -> bool:
        """
        Check if margin close-out should be triggered (EU/UK requirement).

        Margin close-out at 50% of required margin.

        Returns:
            True if margin close-out should be triggered
        """
        if self.jurisdiction not in [self.JURISDICTION_EU, self.JURISDICTION_UK]:
            return False

        # Calculate margin level
        if self.account.margin_used <= 0:
            return False

        margin_level = (
            self.account.margin_used + self.account.unrealized_pnl
        ) / self.account.margin_used

        # Trigger close-out at 50% (0.5)
        return margin_level <= Decimal("0.5")

    def get_jurisdiction_info(self) -> Dict:
        """
        Get information about the current jurisdiction's rules.

        Returns:
            Dictionary with jurisdiction information
        """
        info = {
            "jurisdiction": self.jurisdiction,
            "hedging_allowed": self.jurisdiction != self.JURISDICTION_US,
            "fifo_required": self.jurisdiction == self.JURISDICTION_US,
            "leverage_limits": self.LEVERAGE_LIMITS.get(
                self.jurisdiction, self.LEVERAGE_LIMITS[self.JURISDICTION_OTHER]
            ),
        }

        if self.jurisdiction in [self.JURISDICTION_EU, self.JURISDICTION_UK]:
            info["negative_balance_protection"] = True
            info["margin_closeout_level"] = "50%"

        return info
