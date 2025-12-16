"""
Market data app for market data, streaming, and historical data.

This app provides:
- Tick data models and storage
- Market data streaming from OANDA
- Historical data loading (PostgreSQL, Athena, S3)
- Candle/OHLC data views
- Market configuration (instruments, granularities)
"""

default_app_config = "apps.market.apps.MarketConfig"
