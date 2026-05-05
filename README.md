# Auto Forex Trader

A full-stack web application for managing algorithmic forex trading operations across multiple OANDA accounts with real-time market data streaming, strategy execution, position tracking, and comprehensive risk management.

## Features

- **Multi-Account Management**: Manage multiple OANDA accounts independently
- **Real-Time Market Data**: Live streaming of forex market data via OANDA v20 API
- **Modular Trading Strategies**: Plug-and-play strategy framework with Floor Strategy implementation
- **Risk Management**: ATR-based volatility protection and automatic margin monitoring
- **Position Tracking**: Real-time P&L calculation and position management
- **Backtesting Engine**: Test strategies against historical data from AWS S3/Athena
- **Event Logging**: Complete audit trail of all trading and system events

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed local development setup instructions.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the steps to deploy the application.
Production releases are managed through GitHub Actions workflows.

## License

This project is licensed under the Apache-2.0 License - see the LICENSE file for details.
