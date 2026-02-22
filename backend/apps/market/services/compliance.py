"""apps.market.services.compliance

Regulatory compliance checks for order submission.

This module is market-owned and should not depend on trading/accounts event mechanisms.
It is also designed to be resilient when the trading app (and its models) are not
installed in a given runtime (e.g., certain test configurations).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.apps import apps as django_apps

from apps.market.models import OandaAccounts


class ComplianceViolationError(Exception):
    """Raised when an order violates regulatory compliance rules."""


class ComplianceService:
    """Validate orders against jurisdiction-specific compliance rules."""

    # Jurisdiction constants
    JURISDICTION_US = "US"
    JURISDICTION_JP = "JP"
    JURISDICTION_EU = "EU"
    JURISDICTION_UK = "UK"
    JURISDICTION_AU = "AU"
    JURISDICTION_OTHER = "OTHER"

    # Leverage limits by jurisdiction
    LEVERAGE_LIMITS = {
        JURISDICTION_US: {"major_pairs": 50, "minor_pairs": 20},
        JURISDICTION_JP: {"all_pairs": 25},
        JURISDICTION_EU: {
            "major_pairs": 30,
            "minor_pairs": 20,
            "gold": 20,
            "commodities": 10,
            "indices": 20,
            "crypto": 2,
        },
        JURISDICTION_UK: {
            "major_pairs": 30,
            "minor_pairs": 20,
            "gold": 20,
            "commodities": 10,
            "indices": 20,
            "crypto": 2,
        },
        JURISDICTION_AU: {"major_pairs": 30, "minor_pairs": 20},
        JURISDICTION_OTHER: {"all_pairs": 100},
    }

    MAJOR_PAIRS = [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "USD_CHF",
        "USD_CAD",
        "AUD_USD",
        "NZD_USD",
    ]

    def __init__(self, account: OandaAccounts) -> None:
        self.account = account
        self.jurisdiction = getattr(account, "jurisdiction", self.JURISDICTION_OTHER)

    def validate_order(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
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

    # ------------------------------------------------------------------
    # Jurisdiction entrypoints
    # ------------------------------------------------------------------

    def _validate_us_order(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        instrument = str(order_request.get("instrument", ""))
        units = int(order_request.get("units", 0) or 0)

        if self._would_create_hedge(instrument, units):
            return (
                False,
                "Hedging is not allowed for US accounts (NFA Rule 2-43b). "
                "This order would create opposing positions in the same instrument.",
            )

        leverage_valid, leverage_error = self._check_us_leverage(order_request)
        if not leverage_valid:
            return False, leverage_error

        return True, None

    def _validate_jp_order(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        leverage_valid, leverage_error = self._check_jp_leverage(order_request)
        if not leverage_valid:
            return False, leverage_error

        size_valid, size_error = self._check_jp_position_size(order_request)
        if not size_valid:
            return False, size_error

        return True, None

    def _validate_eu_order(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        leverage_valid, leverage_error = self._check_eu_leverage(order_request)
        if not leverage_valid:
            return False, leverage_error

        balance_valid, balance_error = self._check_negative_balance(order_request)
        if not balance_valid:
            return False, balance_error

        return True, None

    def _validate_uk_order(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        return self._validate_eu_order(order_request)

    def _validate_au_order(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        leverage_valid, leverage_error = self._check_au_leverage(order_request)
        if not leverage_valid:
            return False, leverage_error
        return True, None

    def _validate_other_order(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        _ = order_request
        return True, None

    # ------------------------------------------------------------------
    # Trading-model-dependent helpers (best-effort)
    # ------------------------------------------------------------------

    def _get_position_model(self) -> type[Any] | None:
        try:
            return django_apps.get_model("trading", "Position")
        except Exception:
            return None

    def _would_create_hedge(self, instrument: str, units: int) -> bool:
        position_model = self._get_position_model()
        if position_model is None:
            return False

        existing_positions = position_model.objects.filter(
            instrument=instrument,
            is_open=True,
        )

        if not existing_positions.exists():
            return False

        order_direction = "long" if units > 0 else "short"
        return any(position.direction != order_direction for position in existing_positions)

    def should_reduce_position_instead(
        self, instrument: str, units: int
    ) -> tuple[bool, int | None]:
        if self.jurisdiction != self.JURISDICTION_US:
            return False, None

        position_model = self._get_position_model()
        if position_model is None:
            return False, None

        if not self._would_create_hedge(instrument, units):
            return False, None

        order_direction = "long" if units > 0 else "short"
        opposite_direction = "short" if order_direction == "long" else "long"

        opposite_positions = position_model.objects.filter(
            instrument=instrument,
            direction=opposite_direction,
            is_open=True,
        )

        total_opposite_units = sum(abs(pos.units) for pos in opposite_positions)
        order_units = abs(units)
        units_to_reduce = int(min(order_units, total_opposite_units))

        return True, units_to_reduce

    def get_fifo_position_to_close(self, instrument: str, units: int) -> Any | None:
        _ = units
        if self.jurisdiction != self.JURISDICTION_US:
            return None

        position_model = self._get_position_model()
        if position_model is None:
            return None

        positions = position_model.objects.filter(
            instrument=instrument,
            is_open=True,
        ).order_by("entry_time")

        first_position = positions.first()
        return first_position if first_position is not None else None

    # ------------------------------------------------------------------
    # Rule checks
    # ------------------------------------------------------------------

    def _check_us_leverage(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        instrument = str(order_request.get("instrument", ""))
        units = abs(int(order_request.get("units", 0) or 0))

        if instrument in self.MAJOR_PAIRS:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_US]["major_pairs"]
        else:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_US]["minor_pairs"]

        required_margin = Decimal(units) / Decimal(max_leverage)

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

    def _check_jp_leverage(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        units = abs(int(order_request.get("units", 0) or 0))
        max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_JP]["all_pairs"]

        required_margin = Decimal(units) / Decimal(max_leverage)

        if required_margin > self.account.margin_available:
            return (
                False,
                "Order exceeds maximum leverage limit for Japan accounts (25:1). "
                f"Required margin: {required_margin:.2f}, "
                f"Available: {self.account.margin_available:.2f}",
            )

        return True, None

    def _check_jp_position_size(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        units = abs(int(order_request.get("units", 0) or 0))

        max_position_size = Decimal(str(self.account.balance)) * Decimal(25)

        if Decimal(units) > max_position_size:
            return (
                False,
                "Order exceeds maximum position size for Japan accounts. "
                f"Maximum: {max_position_size:.0f} units, Requested: {units} units",
            )

        return True, None

    def _check_eu_leverage(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        instrument = str(order_request.get("instrument", ""))
        units = abs(int(order_request.get("units", 0) or 0))

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

    def _check_au_leverage(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        instrument = str(order_request.get("instrument", ""))
        units = abs(int(order_request.get("units", 0) or 0))

        if instrument in self.MAJOR_PAIRS:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_AU]["major_pairs"]
        else:
            max_leverage = self.LEVERAGE_LIMITS[self.JURISDICTION_AU]["minor_pairs"]

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

    def _check_negative_balance(self, order_request: dict[str, Any]) -> tuple[bool, str | None]:
        _ = order_request
        if self.account.balance + self.account.unrealized_pnl <= 0:
            return (
                False,
                "Order rejected: Negative balance protection. Account balance is at or below zero.",
            )

        return True, None

    def should_trigger_margin_closeout(self) -> bool:
        if self.jurisdiction not in [self.JURISDICTION_EU, self.JURISDICTION_UK]:
            return False

        if self.account.margin_used <= 0:
            return False

        margin_level = (
            self.account.margin_used + self.account.unrealized_pnl
        ) / self.account.margin_used
        return margin_level <= Decimal("0.5")

    def get_jurisdiction_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
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


# Back-compat alias (old name used elsewhere historically)
RegulatoryComplianceManager = ComplianceService
