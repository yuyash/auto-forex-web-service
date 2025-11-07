"""
Register all trading strategies with the strategy registry.

This module imports all available trading strategies so they can be
discovered and used by the trading system. The strategies self-register
using the @register_strategy decorator in their respective files.
"""

# Import strategy classes - they self-register on import
# pylint: disable=unused-import
from .arbitrage_strategy import ArbitrageStrategy  # noqa: F401
from .floor_strategy import FloorStrategy  # noqa: F401
from .macd_strategy import MACDStrategy  # noqa: F401
from .mean_reversion_strategy import MeanReversionStrategy  # noqa: F401
from .rsi_strategy import RSIStrategy  # noqa: F401
from .scalping_strategy import ScalpingStrategy  # noqa: F401
from .stochastic_strategy import StochasticStrategy  # noqa: F401
from .swing_trading_strategy import SwingTradingStrategy  # noqa: F401


def register_all_strategies() -> None:
    """
    Import all strategy modules to trigger their self-registration.

    This function is called by the Django app's ready() method.
    Each strategy class uses the @register_strategy decorator to
    register itself with the strategy registry when imported.

    The imports at the module level ensure strategies are registered
    when this module is imported.
    """
